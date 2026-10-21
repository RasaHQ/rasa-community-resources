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
            async def acompletion(self, messages, **kwargs):
                self.count += 1
                if self.count == 1:
                    name, args = 'activate', {'target_id': 'briefing'}
                elif self.count == 2:
                    name, args = 'briefing', {'action': 'start', 'request': 'Replay DEMO101'}
                elif self.count in (3, 6, 9):
                    fixture.assertEqual(len(jobs._jobs), 1)
                    capability, job = next(iter(jobs._jobs.items()))
                    await job.task
                    name, args = 'briefing', {'action': 'get', 'briefing_id': capability}
                elif self.count in (5, 8):
                    capability = next(iter(jobs._jobs))
                    change = 'Replay DEMO101 morning weather' if self.count == 5 else 'Replay DEMO101 later arrival'
                    name, args = 'briefing', {'action': 'revise', 'briefing_id': capability, 'change': change}
                elif self.count in (4, 7, 10):
                    return LLMResponse(id='script-final', choices=['Unchecked model margin 9999 minutes'], created=0)
                else:
                    raise AssertionError('unexpected provider fixture call')
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
                            bootstrap = ModelBootstrap(llm={'model': 'fixture-only'}, skill_catalog=catalog, hooks=hooks)
                            tracker = DialogueStateTracker('fixture-conversation-a', [])
                            handle = make_tracker_handle(tracker, bootstrap)
                            output = CollectingOutputChannel()
                            executor = SkillExecutor(skill_catalog=catalog, mcp_runtime=runtime, hooks=hooks)
                            orchestrator = Orchestrator(executor, PromptConstructor(), bootstrap)
                            async def run_turn(text):
                                turn = IncomingTurn(sender_id='fixture-conversation-a', text=text)
                                tracker.update(UserUttered(text=text, input_channel='fixture'))
                                before = len(output.messages)
                                async with MessageTurnContext(handle, turn, output, turn.sender_id):
                                    result = await orchestrator.run_turn(handle, turn)
                                self.assertIsNone(result.error, result)
                                delivered = '\n\n'.join(message['text'] for message in output.messages[before:])
                                self.assertIn('not bound to this conversation', delivered)
                                self.assertNotIn('9999', delivered)
                                self.assertNotIn(next(iter(jobs._jobs)), delivered)
                                return delivered

                            with patch('rasa.mantle.llm.client.LLMClient.from_bootstrap', return_value=provider):
                                first = await run_turn('Show the constructed Replay DEMO101')
                                self.assertEqual(provider.count, 4)
                                self.assertIn('Margin: 120.0 minutes', first)
                                original = {card['event']['component']: card for card in next(iter(jobs._jobs.values())).cards}
                                weather = await run_turn('Replay DEMO101 morning weather')
                                self.assertEqual(provider.count, 7)
                                self.assertIn('Margin: 120.0 minutes', weather)
                                revised = {card['event']['component']: card for card in next(iter(jobs._jobs.values())).cards}
                                for component in ('flight_status', 'arrival_timeline'):
                                    self.assertEqual(original[component], revised[component])
                                self.assertNotEqual(original['weather_hourly']['event']['request_id'],
                                                    revised['weather_hourly']['event']['request_id'])
                                later = await run_turn('Replay DEMO101 later arrival')
                                self.assertEqual(provider.count, 10)
                                self.assertIn('Margin: 30.0 minutes', later)
                                self.assertNotIn('Margin: 120.0 minutes', later)
                            await runtime.close()
        finally:
            await jobs.close()


if __name__ == '__main__':
    unittest.main()
