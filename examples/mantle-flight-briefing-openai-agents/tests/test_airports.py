"""Only explicit codes in the pinned local public-domain table are accepted."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.airports import airport, table
from briefing.public_sources import PublicSourcesRunner
from briefing.jobs import BriefingRefused, Work


class Airports(unittest.IsolatedAsyncioTestCase):
    def test_codes_resolve_the_same_pinned_airport(self):
        self.assertEqual(airport('LHR'), airport('EGLL'))
        self.assertEqual(airport('EGLL')['ident'], 'EGLL')
        self.assertEqual(len(table()), 12)
        row = airport('EGLL')
        row['ident'] = 'POISON'
        self.assertEqual(airport('EGLL')['ident'], 'EGLL')

    async def test_unknown_or_injected_destination_stops_before_sources(self):
        class NeverSources:
            def read_briefing(self, *args, **kwargs):
                raise AssertionError('Unknown destination must never contact sources')
        runner = PublicSourcesRunner(NeverSources())
        for destination in ('ZZZZ', '../EGLL', 'https://evil.invalid', 'NaN'):
            with self.subTest(destination=destination), self.assertRaises(BriefingRefused):
                await runner(Work('callsign=TEST123 destination=' + destination +
                                 ' meeting=2026-10-22T17:00:00Z transfer=45', 'request', 1, None))
