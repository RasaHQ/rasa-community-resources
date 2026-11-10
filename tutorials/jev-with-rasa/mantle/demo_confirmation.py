"""Reproduce the previous timestamp-only guard and check the next-turn fix.

Actual UserUttered/BotUttered objects and decorated tools; scripted SDK replies
and fictional records. The previous guard is reconstructed only in memory.
"""
import asyncio
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from rasa.shared.core.events import BotUttered, UserUttered

ROOT = Path(__file__).resolve().parents[1]
NEXT_TURN_CHECK = '''    later_users = [event for event in context.events
                   if isinstance(event, UserUttered) and event.timestamp > created]
    if len(later_users) != 1:
        del PROPOSALS[key]
        await asyncio.to_thread(request_worker, "/cancel",
                                {"owner": owner, "conversation": key, "token": token})
        return ToolResult(llm_response={"status": "proposal_expired"})
'''


async def replay(timestamp_only=False, intervening=True):
    spec = importlib.util.spec_from_file_location('confirmation_fixture', ROOT / 'tests/test_mantle_binding.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fixture = module.MantleBindings('test_same_user_event_cannot_confirm_its_own_proposal')
    await fixture.asyncSetUp()
    try:
        source = (ROOT / 'mantle/skills/recent_transactions/tools.py').read_text()
        if timestamp_only:
            assert source.count(NEXT_TURN_CHECK) == 1
            source = source.replace(NEXT_TURN_CHECK, '')
            variant = ModuleType('previous_timestamp_only_tools')
            exec(compile(source, 'previous_timestamp_only_tools.py', 'exec'), variant.__dict__)
            variant.urlopen = fixture.tools.urlopen
            fixture.tools = variant
        fixture.tool_context.events = [UserUttered('Show my current account transactions', timestamp=1)]
        await fixture.tools.select_demo('111111')
        proposal = await fixture.tools.propose_recent_transactions(context=fixture.tool_context)
        fixture.tool_context.events.append(BotUttered('I can read your current account. Shall I use that account?', timestamp=1.1))
        if intervening:
            fixture.tool_context.events.extend([
                UserUttered('Help me contact support instead', timestamp=2),
                BotUttered('Would you like the support contact details?', timestamp=2.1)])
        fixture.tool_context.events.append(UserUttered('Yes', timestamp=3))
        result = await fixture.tools.read_confirmed_transactions(context=fixture.tool_context)
        events = [{'kind': 'user' if isinstance(e, UserUttered) else 'bot',
                   'text': e.text, 'timestamp': e.timestamp} for e in fixture.tool_context.events]
        return {'control': 'previous_timestamp_only' if timestamp_only else 'next_user_turn',
                'events': events, 'proposal_created_from_event': 1,
                'proposal_status': proposal.llm_response['status'], 'read_status': result.llm_response['status'],
                'account_reads': list(fixture.accounts.reads), 'scripted_sdk_requests': len(fixture.requests),
                'external_provider_requests': 0, 'tool_source_sha256': hashlib.sha256(source.encode()).hexdigest()}
    finally:
        await fixture.asyncTearDown()


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Include complete controlled events and source hashes')
    args = parser.parse_args()
    records = []
    for timestamp_only, intervening in [(True, True), (False, True), (False, False)]:
        records.append(await replay(timestamp_only, intervening))
    if args.json:
        for record in records:
            print(json.dumps(record, sort_keys=True))
    else:
        print('Changed-topic fixture: account request -> account question -> support request -> support question -> Yes')
        for name, record in zip(['previous_timestamp_only', 'next_user_turn', 'next_user_turn_positive'], records):
            if name == 'next_user_turn_positive':
                print('Positive fixture: account request -> account question -> Yes')
            print(f"{name}: {record['read_status']}; account_reads={json.dumps(record['account_reads'])}")


if __name__ == '__main__':
    asyncio.run(main())
