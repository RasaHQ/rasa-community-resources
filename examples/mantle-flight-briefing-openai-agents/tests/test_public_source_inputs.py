"""No provider access: missing traveller inputs must stop before source calls."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.jobs import BriefingRefused, NeedsInput, Work
from briefing.public_sources import PublicSourcesRunner


class NeverSources:
    def read_briefing(self, *args, **kwargs):
        raise AssertionError('No source call before explicit inputs')
    def close(self):
        pass


class PublicSourceInputs(unittest.IsolatedAsyncioTestCase):
    async def test_missing_inputs_resume_same_explicit_journey_without_defaults(self):
        runner = PublicSourcesRunner(NeverSources())
        inputs = None
        for text, field in (
                ('callsign=TEST123', 'meeting_time'),
                ('tomorrow at five', 'meeting_time'),
                ('2026-10-22T17:00:00Z', 'transfer_minutes'),
                ('not sure', 'transfer_minutes')):
            with self.assertRaises(NeedsInput) as caught:
                await runner(Work(text, 'request', 1, None, inputs=inputs))
            self.assertEqual(caught.exception.field, field)
            inputs = caught.exception.inputs
            self.assertEqual(inputs['callsign'], 'TEST123')
        self.assertNotIn('transfer_minutes', inputs)

    async def test_no_real_flight_is_silently_replaced_with_replay(self):
        runner = PublicSourcesRunner(NeverSources())
        with self.assertRaises(BriefingRefused):
            await runner(Work('show my flight', 'request', 1, None))

    async def test_four_error_references_still_use_actual_core_callback_results(self):
        from zeo_core.contracts.ui.widgets import DataRef, DataError
        class Sources(NeverSources):
            calls = 0
            def read_briefing(self, callsign, **kwargs):
                self.calls += 1
                return {component: DataRef(id=component, source='Synthetic unavailable control',
                    fetched_at='2026-10-22T01:00:00Z', as_of=None, replay=False,
                    payload={}, error=DataError(reason='Source unavailable')) for component in (
                        'flight_status', 'weather_hourly', 'arrival_timeline', 'market_watchlist')}
        sources = Sources()
        runner = PublicSourcesRunner(sources)
        answer = await runner(Work('callsign=TEST123 meeting=2026-10-22T17:00:00Z transfer=45',
                                   'request', 1, None))
        self.assertEqual(sources.calls, 1)
        self.assertTrue(answer.turn.ok)
        self.assertEqual(len(answer.cards), 4)
        self.assertEqual(set(answer.required_components), set(answer.cards))
        self.assertTrue(all(ref.error is not None and not ref.payload for ref in answer.cards.values()))

    async def test_explicit_replay_missing_inputs_resume_without_entering_public_sources(self):
        runner = PublicSourcesRunner(NeverSources())
        with self.assertRaises(NeedsInput) as first:
            await runner(Work('Replay DEMO101 missing inputs', 'request', 1, None))
        self.assertEqual(first.exception.inputs['source_mode'], 'replay')
        with self.assertRaises(NeedsInput) as second:
            await runner(Work('2026-10-22T17:00:00Z', 'request', 2, None,
                              inputs=first.exception.inputs))
        self.assertEqual(second.exception.field, 'transfer_minutes')
        answer = await runner(Work('45 minutes', 'request', 3, None,
                                   inputs=second.exception.inputs))
        self.assertTrue(answer.turn.ok)
        self.assertTrue(all(ref.replay for ref in answer.cards.values()))
