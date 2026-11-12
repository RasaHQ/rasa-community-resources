"""Deterministic tool selection; never creates a provider client."""
import json
import os

CARD_KIND = 'image'


def gate_record(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if isinstance(value, dict):
        if value.get('verdict') in ('ACCEPT', 'REJECT', 'NOT_READY'):
            return value
        for key in ('structuredContent', 'content', 'text', 'value'):
            result = gate_record(value.get(key))
            if result:
                return result
    if isinstance(value, list):
        for item in value:
            result = gate_record(item)
            if result:
                return result
    return None


def verdict_text(result):
    verdict = result.get('verdict')
    if verdict not in ('ACCEPT', 'REJECT', 'NOT_READY'):
        return 'NOT_READY: the gate returned no validated verdict.'
    failing = result.get('failing_test') or result.get('failing_tests') or 'none'
    fingerprint = result.get('fingerprint', 'unavailable')
    mode = result.get('mode', 'SCRIPTED')
    if mode == 'LIVE':
        detail = f"LIVE build: gpt-6-astra on the OpenAI Agents API; {result.get('builder_calls', 0)} builder tool calls; {result.get('seconds', 0)} seconds. Expected cost 15 to 150 US cents, an estimate, not a cap."
    else:
        detail = 'SCRIPTED builder: this checks a supplied attempt; zero model calls.'
    return f'{verdict}. Failing test: {failing}. Attempt fingerprint (computed by the tool): {fingerprint}. {detail} Mantle tool selection is SCRIPTED. Nothing was released.'


class ScriptedClient:
    def __init__(self):
        self.count = 0

    async def acompletion(self, messages, **kwargs):
        from rasa.shared.providers.llm.llm_response import LLMResponse, LLMToolCall
        self.count += 1
        users = [i for i, m in enumerate(messages) if m.get('role') == 'user']
        latest = users[-1] if users else len(messages)
        text = str(messages[latest].get('content', '')) if users else ''
        offered = {t.get('function', {}).get('name') for t in kwargs.get('tools') or []}
        results = [gate_record(m.get('content')) for m in messages[latest + 1:] if m.get('role') == 'tool']
        result = next((v for v in reversed(results) if v), None)
        gate_ids = set()
        for message in messages[latest + 1:]:
            for call in message.get('tool_calls') or []:
                if call.get('function', {}).get('name') in ('run_factory', 'mcp/factory:run_factory'):
                    gate_ids.add(call.get('id'))
        received_gate = any(m.get('role') == 'tool' and (
            m.get('name') in ('run_factory', 'mcp/factory:run_factory') or
            m.get('tool_call_id') in gate_ids) for m in messages[latest + 1:])
        if received_gate and result is None:
            return LLMResponse(id='scripted', created=0, choices=['NOT_READY: the tool returned no valid gate record; no automatic retry.'])
        card_shown = any(call.get('function', {}).get('name') in ('show_verdict_card', 'show_verdict_image') for m in messages[latest + 1:] for call in (m.get('tool_calls') or []))
        if result and not card_shown and ('show_verdict_card' in offered or 'show_verdict_image' in offered):
            args = {'request': text, 'verdict': result.get('verdict'),
                    'failing_test': str(result.get('failing_test') or ''),
                    'fingerprint': str(result.get('fingerprint') or ''),
                    'mode': result.get('mode', 'SCRIPTED'),
                    'builder_calls': int(result.get('builder_calls') or 0),
                    'seconds': float(result.get('seconds') or 0),
                    'reason': str(result.get('reason') or '')}
            return LLMResponse(id='scripted', created=0, choices=[], tool_calls=[LLMToolCall(id=f'card-{self.count}', tool_name=('show_verdict_image' if CARD_KIND == 'image' else 'show_verdict_card'), tool_args=args)])
        if result:
            return LLMResponse(id='scripted', created=0, choices=[verdict_text(result)])
        if not text or text.startswith('/session_start'):
            return LLMResponse(id='scripted', created=0, choices=['SCRIPTED tool selection. Ask for at most three currencies, or use the supplied attempt that ignores the limit. The protected gate will judge it.'])
        tool = next((n for n in offered if n in ('run_factory', 'mcp/factory:run_factory')), None)
        if tool:
            notice = ('Mantle tool selection is SCRIPTED. LIVE builder gpt-6-astra on the OpenAI Agents API; expected cost 15 to 150 US cents (estimate, not cap). Waiting, up to five minutes.' if os.environ.get('FACTORY_BUILDER_MODE') == 'LIVE' and 'ignores the limit' not in text.lower() else 'SCRIPTED supplied attempt; running the real protected acceptance gate.')
            return LLMResponse(id='scripted', created=0, choices=[notice], tool_calls=[LLMToolCall(id=f'factory-{self.count}', tool_name=tool, tool_args={'request': text})])
        if 'activate' in offered:
            return LLMResponse(id='scripted', created=0, choices=[], tool_calls=[LLMToolCall(id=f'skill-{self.count}', tool_name='activate', tool_args={'target_id': 'request_change'})])
        return LLMResponse(id='scripted', created=0, choices=['NOT_READY: Request a Change skill is unavailable.'])
