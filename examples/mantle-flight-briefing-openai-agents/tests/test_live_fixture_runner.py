"""Offline resource integration tests, not model or live provider proof."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'project')]
from briefing.jobs import Jobs, Owner
from briefing.live import LiveFixtureRunner


class Client:
    beta = SimpleNamespace(agents=SimpleNamespace(sessions=SimpleNamespace(create=lambda **kwargs: None)))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class LiveFixtureRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.invocations = []
        self.call_handlers = True
        self.completed = True

        def invoke(client, **kwargs):
            self.invocations.append((client, kwargs))
            called = []
            if self.call_handlers:
                for name, handler in kwargs['handlers'].items():
                    handler({})
                    called.append(name)
            # Mirrors NativeTurn's public fields; there are no legacy call ids.
            return SimpleNamespace(session_id=f'synthetic-session-{len(self.invocations)}',
                                   ok=self.completed, status='completed' if self.completed else 'failed',
                                   output_text='Unchecked model margin 9999', tools_called=tuple(called))

        runner = LiveFixtureRunner(Client, model='offline-fixture', invoke=invoke)
        self.jobs = Jobs(runner, replacement_plan=runner.replacement_plan)
        self.owner = Owner('test-peer', 'test-conversation')

    async def asyncTearDown(self):
        await self.jobs.close()

    async def start(self):
        state = await self.jobs.briefing(self.owner, action='start', request='Replay DEMO101')
        await self.jobs._jobs[state['job_id']].task
        return state['job_id'], await self.jobs.briefing(self.owner, action='get', job_id=state['job_id'])

    async def test_actual_native_names_and_validated_cards_complete_without_model_values(self):
        _, state = await self.start()
        self.assertEqual(state['status'], 'complete', state)
        self.assertEqual(len(state['cards']), 3)
        self.assertTrue(all(c['data_ref']['replay'] for c in state['cards']))
        self.assertNotIn('9999', str(([c['data_ref']['payload'] for c in state['cards']],
                                            state.get('reason'), state['progress'])))
        self.assertEqual(len(self.invocations[0][1]['handlers']), 3)

    async def test_model_completion_without_source_callbacks_is_incomplete(self):
        self.call_handlers = False
        _, state = await self.start()
        self.assertEqual(state['status'], 'incomplete', state)
        self.assertEqual(state['cards'], [])
        self.assertNotIn('9999', str(([c['data_ref']['payload'] for c in state['cards']],
                                            state.get('reason'), state['progress'])))

    async def test_failed_native_turn_cannot_complete_even_with_all_cards(self):
        self.completed = False
        _, state = await self.start()
        self.assertEqual(state['status'], 'incomplete', state)

    async def test_revision_uses_fresh_client_and_validated_prior_not_model_text(self):
        job_id, before = await self.start()
        await self.jobs.briefing(self.owner, action='revise', job_id=job_id,
                                 change='Replay DEMO101 morning weather')
        await self.jobs._jobs[job_id].task
        after = await self.jobs.briefing(self.owner, action='get', job_id=job_id)
        self.assertEqual(after['status'], 'complete', after)
        self.assertIsNot(self.invocations[0][0], self.invocations[1][0])
        second = self.invocations[1][1]
        self.assertNotIn('session_id', second)
        self.assertIn('prior_validated_brief', second['text'])
        self.assertIn('flight_status', second['text'])
        self.assertNotIn('9999', second['text'])
        self.assertNotIn(job_id, second['text'])
        self.assertEqual(list(second['handlers']), ['read_weather_hourly'])
        old = {c['event']['component']: c for c in before['cards']}
        new = {c['event']['component']: c for c in after['cards']}
        self.assertEqual(old['flight_status'], new['flight_status'])
        self.assertEqual(old['arrival_timeline'], new['arrival_timeline'])


if __name__ == '__main__':
    unittest.main()
