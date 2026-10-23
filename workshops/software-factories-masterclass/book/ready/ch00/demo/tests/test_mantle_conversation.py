"""Keyless engine conversation fixture, NOT model behavior or live acceptance.

Only the LLM provider factory is replaced by scripted responses. Actual Mantle
orchestration, skill dispatch, MCP ClientSession/server, Core replay, hooks,
tracker and collecting channel run unchanged. HTTP transport stays in-process.
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'project')]
try:
    # Match the normal engine entry-point import order before isolated orchestration.
    from rasa.core.agent import Agent
    from rasa.mantle.orchestration.orchestrator import Orchestrator
    HAS_MANTLE = True
except ModuleNotFoundError as exc:
    if exc.name != 'rasa':
        raise
    HAS_MANTLE = False


@unittest.skipUnless(HAS_MANTLE, 'run with the managed Mantle project interpreter')
class ScriptedMantleConversation(unittest.IsolatedAsyncioTestCase):
    async def test_scripted_provider_drives_real_engine_mcp_and_cards(self):
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        from rasa.agents.schemas.agent_tool_schema import AgentToolSchema
        from rasa.core.channels.channel import CollectingOutputChannel
        from rasa.shared.core.trackers import DialogueStateTracker
        from rasa.shared.core.events import UserUttered
        from rasa.shared.providers.llm.llm_response import LLMResponse, LLMToolCall
        from rasa.mantle.config.integrations import MCPServerSpec
        from rasa.mantle.hooks.loader import load_hooks
        from rasa.mantle.model_archive.bootstrap import ModelBootstrap
        from rasa.mantle.orchestration.skill_executor import SkillExecutor
        from rasa.mantle.orchestration.turn_context import MessageTurnContext
        from rasa.mantle.prompts.constructor import PromptConstructor
        from rasa.mantle.skills.catalog import load_skill_catalog
        from rasa.mantle.state.tracker_handle import make_tracker_handle
        from rasa.mantle.state.turn import IncomingTurn
        from rasa.mantle.tools.mcp_runtime import MCPRuntime
        from briefing.jobs import Jobs
        from briefing.mcp_app import create_app
        from briefing.replay import ReplayRunner

        runner = ReplayRunner()
        jobs = Jobs(runner, replacement_plan=runner.replacement_plan, ownership_mode='capability')
        app = create_app(jobs, transport_token='fixture-only-no-authority-transport-token')
        catalog = load_skill_catalog(ROOT / 'project')
        self.assertEqual(list(catalog.skills), ['briefing'])
        hooks = load_hooks(ROOT / 'project')
        runtime = MCPRuntime()
        fixture = self

        class ProviderFixture:
            count = 0
            plan = []

            async def acompletion(self, messages, **kwargs):
                self.count += 1
                fixture.assertTrue(self.plan, 'unexpected provider fixture call')
                step = self.plan.pop(0)
                if isinstance(step, str):
                    return LLMResponse(id=f'script-final-{self.count}', choices=[step], created=0)
                name, args = step
                args = dict(args)
                offered = {tool['function']['name'] for tool in kwargs.get('tools') or []}
                fixture.assertIn(name, offered, 'fixture attempted a tool the actual engine did not offer')
                if args.get('action') in ('get', 'revise'):
                    # Fixture-only selection; not a claim that a model remembers IDs.
                    capability, job = list(jobs._jobs.items())[-1]
                    if args['action'] == 'get':
                        await job.task
                    args['briefing_id'] = capability
                return LLMResponse(id=f'script-{self.count}', choices=[], created=0,
                    tool_calls=[LLMToolCall(id=f'call-{self.count}', tool_name=name, tool_args=args)])

        provider = ProviderFixture()
        try:
            async with app._app.router.lifespan_context(app._app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                    headers={'Authorization': 'Bearer fixture-only-no-authority-transport-token'}) as http:
                    async with streamable_http_client('http://127.0.0.1:8942/mcp', http_client=http) as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            listed = await session.list_tools()
                            tool = listed.tools[0]
                            self.assertEqual(tool.name, 'briefing')
                            class InProcessConnection:
                                async def ensure_active_session(self):
                                    return session
                                async def close(self):
                                    pass  # ClientSession context owns closure.
                            runtime.shared_connection_pool.add('briefing', InProcessConnection(),
                                MCPServerSpec(name='briefing', url='http://127.0.0.1:8942/mcp'))
                            runtime.tool_to_server = {'briefing': {'briefing': 'briefing'}}
                            runtime.mcp_tool_schemas = {'briefing': {'briefing': AgentToolSchema(
                                name=tool.name, description=tool.description or '',
                                parameters=tool.inputSchema, strict=False)}}
                            from rasa.mantle.config.agent_spec import agent_spec_from_config
                            import yaml
                            agent_spec = agent_spec_from_config(yaml.safe_load((ROOT / 'project/agent.yml').read_text()))
                            bootstrap = ModelBootstrap(agent=agent_spec, llm={'model': 'fixture-only'}, skill_catalog=catalog, hooks=hooks)
                            tracker = DialogueStateTracker('fixture-conversation-a', [])
                            handle = make_tracker_handle(tracker, bootstrap)
                            output = CollectingOutputChannel()
                            executor = SkillExecutor(skill_catalog=catalog, mcp_runtime=runtime, hooks=hooks)
                            orchestrator = Orchestrator(executor, PromptConstructor(), bootstrap)
                            async def run_turn(text, steps, *, cards=True):
                                provider.plan = [*steps, "Unchecked model margin 9999 minutes"]
                                turn = IncomingTurn(sender_id='fixture-conversation-a', text=text)
                                tracker.update(UserUttered(text=text, input_channel='fixture'))
                                before = len(output.messages)
                                async with MessageTurnContext(handle, turn, output, turn.sender_id):
                                    result = await orchestrator.run_turn(handle, turn)
                                self.assertIsNone(result.error, result)
                                delivered = '\n\n'.join(message['text'] for message in output.messages[before:])
                                self.assertEqual(provider.plan, [], 'turn ended before fixture actions completed')
                                if cards:
                                    self.assertIn('panel on the right', delivered)
                                    self.assertLess(len(delivered), 180)
                                    self.assertNotIn('Margin:', delivered)
                                self.assertNotIn('9999', delivered)
                                for capability in jobs._jobs:
                                    self.assertNotIn(capability, delivered)
                                # The facilitator launcher prints these actual
                                # delivered messages, after the same assertions.
                                sink = getattr(self, 'transcript_sink', None)
                                if sink is not None:
                                    sink.append((text, delivered))
                                return delivered

                            def panel_details():
                                from project.lib.card_text import render_cards
                                return render_cards({'cards': list(jobs._jobs.values())[-1].cards})

                            with patch('rasa.mantle.llm.client.LLMClient.from_bootstrap', return_value=provider):
                                first = await run_turn('Show the constructed Replay DEMO101', [
                                    ('activate', {'target_id': 'briefing'}),
                                    ('briefing', {'action': 'start', 'request': 'Replay DEMO101'}),
                                    ('briefing', {'action': 'get'})])
                                self.assertEqual(provider.count, 4)
                                self.assertIn('Margin: 120.0 minutes', panel_details())
                                original = {card['event']['component']: card for card in next(iter(jobs._jobs.values())).cards}
                                weather = await run_turn('Replay DEMO101 morning weather', [
                                    ('briefing', {'action': 'revise', 'change': 'Replay DEMO101 morning weather'}),
                                    ('briefing', {'action': 'get'})])
                                self.assertEqual(provider.count, 7)
                                self.assertIn('Margin: 120.0 minutes', panel_details())
                                revised = {card['event']['component']: card for card in next(iter(jobs._jobs.values())).cards}
                                for component in ('flight_status', 'arrival_timeline'):
                                    self.assertEqual(original[component], revised[component])
                                self.assertNotEqual(original['weather_hourly']['event']['request_id'],
                                                    revised['weather_hourly']['event']['request_id'])
                                later = await run_turn('Replay DEMO101 later arrival', [
                                    ('briefing', {'action': 'revise', 'change': 'Replay DEMO101 later arrival'}),
                                    ('briefing', {'action': 'get'})])
                                self.assertEqual(provider.count, 10)
                                self.assertIn('Margin: 30.0 minutes', panel_details())
                                self.assertNotIn('Margin: 120.0 minutes', panel_details())
                                question = await run_turn('Show the missing-input replay', [
                                    ('briefing', {'action': 'start', 'request': 'Replay DEMO101 missing inputs'}),
                                    ('briefing', {'action': 'get'})], cards=False)
                                self.assertIn('When is your meeting?', question)
                                self.assertNotIn('Margin:', question)
                                capability = list(jobs._jobs)[-1]
                                for reply in ('tomorrow at five', '2026-10-22T21:00:00Z', '45 minutes'):
                                    answer = await run_turn(reply, [
                                        ('briefing', {'action': 'revise', 'change': reply}),
                                        ('briefing', {'action': 'get'})], cards=reply == '45 minutes')
                                    self.assertEqual(list(jobs._jobs)[-1], capability)
                                    if reply == 'tomorrow at five':
                                        self.assertIn('When is your meeting?', answer)
                                    elif reply.endswith('Z'):
                                        self.assertIn('How long should I allow', answer)
                                    else:
                                        self.assertIn('Margin: 165.0 minutes', panel_details())
                                        self.assertIn('Transfer assumption: 45 minutes', panel_details())
                                failure = await run_turn('Show the flight-source failure replay', [
                                    ('briefing', {'action': 'revise', 'change': 'Replay DEMO101 flight unavailable'}),
                                    ('briefing', {'action': 'get'})])
                                self.assertIn('Some briefing sources are unavailable', failure)
                                self.assertIn('Unavailable: Flight source', panel_details())
                                self.assertIn('Weather Hourly', panel_details())
                                self.assertNotIn('Margin:', panel_details())
                                recovered = await run_turn('Recover the named replay', [
                                    ('briefing', {'action': 'revise', 'change': 'Replay DEMO101'}),
                                    ('briefing', {'action': 'get'})])
                                self.assertIn('briefing is ready', recovered)
                                self.assertIn('Margin: 165.0 minutes', panel_details())
                                scheduled = await run_turn('Use the no-estimate replay', [
                                    ('briefing', {'action': 'revise', 'change': 'Replay DEMO101 no estimate'}),
                                    ('briefing', {'action': 'get'})])
                                self.assertIn('Arrival from scheduled_arrival', panel_details())
                                self.assertIn('Estimated arrival: not provided', panel_details())
                                self.assertIn('Margin: 195.0 minutes', panel_details())
                                self.assertEqual(provider.count, 31)
                            await runtime.close()
        finally:
            await jobs.close()


if __name__ == '__main__':
    unittest.main()
