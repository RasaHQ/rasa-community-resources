"""No provider access: missing traveller inputs must stop before source calls."""
import unittest
from datetime import datetime, timezone
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
    async def test_missing_meeting_keeps_flight_and_visible_default(self):
        runner = PublicSourcesRunner(NeverSources(), clock=lambda: datetime(2026, 10, 22, 1, tzinfo=timezone.utc))
        inputs = None
        for text in ('Lufthansa 400 to JFK', 'tomorrow at five'):
            with self.assertRaises(NeedsInput) as caught:
                await runner(Work(text, 'request', 1, None, inputs=inputs))
            self.assertEqual(caught.exception.field, 'meeting_time')
            self.assertNotIn('ISO', caught.exception.question)
            inputs = caught.exception.inputs
            self.assertEqual(inputs['callsign'], 'DLH400')
            self.assertEqual(inputs['destination'], 'KJFK')
            self.assertEqual(inputs['transfer_minutes'], 90)
            self.assertTrue(inputs['transfer_assumed'])

    async def test_no_real_flight_is_silently_replaced_with_replay(self):
        runner = PublicSourcesRunner(NeverSources(), clock=lambda: datetime(2026, 10, 22, 1, tzinfo=timezone.utc))
        with self.assertRaises(NeedsInput) as caught:
            await runner(Work('show my flight', 'request', 1, None))
        self.assertEqual(caught.exception.field, 'destination')
        self.assertTrue(caught.exception.question.endswith('Where are you heading?'))
        self.assertNotEqual(caught.exception.inputs.get('source_mode'), 'replay')

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
        runner = PublicSourcesRunner(sources, clock=lambda: datetime(2026, 10, 22, 1, tzinfo=timezone.utc))
        answer = await runner(Work('callsign=TEST123 destination=EDDF meeting=2026-10-22T17:00:00Z transfer=45',
                                   'request', 1, None))
        self.assertEqual(sources.calls, 1)
        self.assertTrue(answer.turn.ok)
        self.assertEqual(len(answer.cards), 4)
        self.assertEqual(set(answer.required_components), set(answer.cards))
        self.assertTrue(all(ref.error is not None and not ref.payload for ref in answer.cards.values()))

    async def test_explicit_replay_missing_inputs_resume_without_entering_public_sources(self):
        runner = PublicSourcesRunner(NeverSources(), clock=lambda: datetime(2026, 10, 22, 1, tzinfo=timezone.utc))
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

    async def test_invalid_transfer_revision_cannot_silently_keep_an_old_assumption(self):
        runner = PublicSourcesRunner(NeverSources(), clock=lambda: datetime(2026, 10, 22, 1, tzinfo=timezone.utc))
        for text in ('transfer=-1', 'transfer=1500', 'transfer=unknown'):
            with self.subTest(text=text), self.assertRaises(NeedsInput) as caught:
                await runner(Work(text, 'request', 2, None, inputs={
                    'callsign': 'TEST123', 'destination': 'EDDF', 'meeting_time': '2026-10-22T17:00:00Z',
                    'transfer_minutes': 45}))
            self.assertEqual(caught.exception.field, 'transfer_minutes')
            self.assertNotIn('transfer_minutes', caught.exception.inputs)

    async def test_invalid_new_callsign_does_not_keep_the_old_journey(self):
        runner = PublicSourcesRunner(NeverSources(), clock=lambda: datetime(2026, 10, 22, 1, tzinfo=timezone.utc))
        with self.assertRaises(BriefingRefused):
            await runner(Work('callsign=../private', 'request', 2, None,
                              inputs={'callsign': 'TEST123', 'transfer_minutes': 45,
                                      'meeting_time': '2026-10-22T17:00:00Z'}))


class ReplayTravellerWords(unittest.IsolatedAsyncioTestCase):
    async def test_named_replay_accepts_natural_meeting_and_travel_allowance(self):
        runner = PublicSourcesRunner(NeverSources(), clock=lambda: datetime(2026, 10, 22, 1, tzinfo=timezone.utc))
        with self.assertRaises(NeedsInput) as first:
            await runner(Work('Replay DEMO101 missing inputs', 'request', 1, None))
        with self.assertRaises(NeedsInput) as second:
            await runner(Work('the 6 pm meeting tomorrow', 'request', 2, None, inputs=first.exception.inputs))
        self.assertEqual(second.exception.field, 'transfer_minutes')
        self.assertEqual(second.exception.inputs['meeting_time'], '2026-10-23T18:00:00-04:00')
        answer = await runner(Work('an hour to get into town', 'request', 3, None, inputs=second.exception.inputs))
        self.assertTrue(answer.turn.ok)
        self.assertEqual(answer.inputs['transfer_minutes'], 60)
        self.assertTrue(all(ref.replay for ref in answer.cards.values()))
