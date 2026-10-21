"""Actual pinned Mantle hook loader/runner; no model, listener or conversation.

Run with the managed project interpreter. Worker-only environments skip this
qualification because they intentionally do not install the Mantle engine.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'project')]
try:
    from rasa.mantle.hooks.loader import load_hooks
    from rasa.mantle.hooks.runner import run_modify
    from rasa.mantle.hooks import ToolResultPayload, OutgoingTextPayload
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

    async def present(self, value, sender='conversation-a'):
        result = await run_modify(self.registry, 'tool_result', ToolResultPayload(
            sender_id=sender, tool_name='mcp/briefing:briefing',
            arguments={'action': 'get'}, value=value))
        self.assertIsNone(result.control_flow)
        self.assertEqual(result.outcome, "success")
        outgoing = await run_modify(self.registry, 'outgoing_text', OutgoingTextPayload(
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
        unrelated = await run_modify(self.registry, 'outgoing_text', OutgoingTextPayload(
            sender_id='conversation-b', text='No cards here'))
        self.assertEqual(unrelated.payload.text, 'No cards here')

    async def test_bad_card_stops_unchecked_numeric_model_output(self):
        text = await self.present({'status': 'complete', 'cards': [{'invalid': True}]})
        self.assertIn('could not be validated', text)
        self.assertNotIn('9999', text)


if __name__ == '__main__':
    unittest.main()
