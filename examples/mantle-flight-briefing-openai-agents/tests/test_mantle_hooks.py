"""Actual pinned Mantle hook loader/runner; no model, listener or conversation.

Run with the managed project interpreter. Worker-only environments skip this
qualification because they intentionally do not install the Mantle engine.
"""
from pathlib import Path
import sys
import json
import secrets
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'project')]
try:
    from rasa.mantle.hooks.loader import load_hooks
    from rasa.mantle.hooks.runner import run_modify
    from rasa.mantle.hooks import ToolResultPayload, ModelResponsePayload
    HAS_MANTLE = True
except ModuleNotFoundError as exc:
    if exc.name != 'rasa':
        raise
    HAS_MANTLE = False

from briefing.jobs import Jobs, Owner
from briefing.replay import ReplayRunner


@unittest.skipUnless(HAS_MANTLE, 'run with the managed Mantle project interpreter')
class MantleHookQualification(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.registry = load_hooks(ROOT / 'project')
        runner = ReplayRunner()
        self.jobs = Jobs(runner, replacement_plan=runner.replacement_plan,
                         ownership_mode='capability')
        self.owner = Owner('mantle', 'capability-possession')

    async def asyncTearDown(self):
        await self.jobs.close()

    async def present(self, value, sender='conversation-a', is_error=False):
        result = await run_modify(self.registry, 'tool_result', ToolResultPayload(
            sender_id=sender, tool_name='mcp/briefing:briefing',
            arguments={'action': 'get'}, value=value, is_error=is_error))
        self.assertIsNone(result.control_flow)
        self.assertEqual(result.outcome, "success")
        outgoing = await run_modify(self.registry, 'model_response', ModelResponsePayload(
            sender_id=sender, text='Unchecked model says margin 9999 minutes'))
        return outgoing.payload.text

    async def test_actual_loader_runner_source_cards_and_weather_revision(self):
        self.assertEqual(self.registry.modifier_count, 2)
        first = await self.jobs.briefing(self.owner, action='start', request='Replay DEMO101')
        job_id = first['job_id']
        await self.jobs._jobs[job_id].task
        value = await self.jobs.briefing(self.owner, action='get', job_id=job_id)
        text = await self.present(value)
        self.assertIn('Margin: 120.0 minutes', text)
        self.assertEqual(text.count('[REPLAY]'), 3)
        self.assertIn('not bound to this conversation', text)
        self.assertNotIn('9999', text)
        await self.jobs.briefing(self.owner, action='revise', job_id=job_id,
                                change='Replay DEMO101 morning weather')
        pending = await self.jobs.briefing(self.owner, action='get', job_id=job_id)
        self.assertIn('superseded; replacement pending', await self.present(pending))
        await self.jobs._jobs[job_id].task
        updated = await self.jobs.briefing(self.owner, action='get', job_id=job_id)
        self.assertIn('Margin: 120.0 minutes', await self.present(updated))
        unrelated = await run_modify(self.registry, 'model_response', ModelResponsePayload(
            sender_id='conversation-b', text='No cards here'))
        self.assertEqual(unrelated.payload.text, 'No cards here')

    async def test_engine_adapter_delivery_uses_serialized_tool_result(self):
        from rasa.core.channels.channel import CollectingOutputChannel
        from rasa.shared.core.trackers import DialogueStateTracker
        from rasa.mantle.model_archive.bootstrap import ModelBootstrap
        from rasa.mantle.state.tracker_handle import make_tracker_handle
        from rasa.mantle.state.turn import IncomingTurn
        from rasa.mantle.orchestration.turn_context import MessageTurnContext
        from rasa.mantle.orchestration.hooks import apply_tool_result_hooks, apply_model_response_hooks
        started = await self.jobs.briefing(self.owner, action='start', request='Replay DEMO101')
        await self.jobs._jobs[started['job_id']].task
        value = await self.jobs.briefing(self.owner, action='get', job_id=started['job_id'])
        bootstrap = ModelBootstrap(llm={}, hooks=self.registry)
        tracker = DialogueStateTracker('conversation-a', [])
        handle = make_tracker_handle(tracker, bootstrap)
        output = CollectingOutputChannel()
        async with MessageTurnContext(handle, IncomingTurn(sender_id='conversation-a'),
                                      output, 'conversation-a') as context:
            await apply_tool_result_hooks(self.registry, tool_name='briefing',
                arguments={'action': 'get'}, value=json.dumps(value), is_error=False)
            response = await apply_model_response_hooks(self.registry,
                text='Unchecked model says margin 9999 minutes', tool_calls=[], latency_ms=None)
            await context.send(response.text)
        # The actual collecting channel splits double-newline paragraphs.
        delivered = '\n\n'.join(message['text'] for message in output.messages)
        self.assertIn('Margin: 120.0 minutes', delivered)
        self.assertNotIn('9999', delivered)
        self.assertEqual(tracker.latest_bot_utterance.text, delivered)

    async def test_model_cannot_display_capability_but_tool_arguments_remain_usable(self):
        capability = 'brf_' + secrets.token_urlsafe(32)
        result = await run_modify(self.registry, 'model_response', ModelResponsePayload(
            sender_id='new-conversation', text='Your private identifier is ' + capability,
            tool_calls=[{'id': 'fixture-call', 'tool_name': 'briefing',
                         'tool_args': {'action': 'get', 'briefing_id': capability}}]))
        self.assertNotIn(capability, result.payload.text)
        self.assertIn('redacted', result.payload.text)
        self.assertEqual(result.payload.tool_calls[0]['tool_args']['briefing_id'], capability)

    async def test_missing_input_question_replaces_model_guess(self):
        result = await run_modify(self.registry, 'tool_result', ToolResultPayload(
            sender_id='question-conversation', tool_name='briefing', arguments={'action': 'get'},
            value={'status': 'needs_input', 'needs_input': {'field': 'transfer_minutes',
                   'question': 'What transfer duration in minutes should I assume?'}}))
        self.assertIsNone(result.control_flow)
        answer = await run_modify(self.registry, 'model_response', ModelResponsePayload(
            sender_id='question-conversation', text='I guessed a 90 minute transfer.'))
        self.assertIn('What transfer duration', answer.payload.text)
        self.assertNotIn('REPLAY', answer.payload.text)
        self.assertIn('Briefing needs input', answer.payload.text)
        self.assertNotIn('90', answer.payload.text)

    async def test_running_source_job_gives_a_status_next_step_without_model_values(self):
        text = await self.present({'status': 'running', 'progress': ['Checking sources']})
        self.assertIn('still checking sources', text)
        self.assertIn('say status', text)
        self.assertNotIn('9999', text)
        self.assertNotIn('complete', text)

    async def test_bad_card_stops_unchecked_numeric_model_output(self):
        text = await self.present({'status': 'complete', 'cards': [{'invalid': True}]})
        self.assertIn('could not be validated', text)
        self.assertNotIn('9999', text)

    async def test_error_wrapper_and_empty_results_never_release_model_summary(self):
        cases = [
            ({'error': 'unavailable'}, True),
            ({'result': {'status': 'complete', 'cards': []}}, False),
            ({'status': 'complete', 'cards': []}, False),
            ('not JSON', False),
            ({'status': 'needs_input', 'needs_input': 'invalid'}, False),
        ]
        for value, is_error in cases:
            with self.subTest(value=value, is_error=is_error):
                text = await self.present(value, is_error=is_error)
                self.assertNotIn('9999', text)
                self.assertIn('could not be validated', text)


if __name__ == '__main__':
    unittest.main()
