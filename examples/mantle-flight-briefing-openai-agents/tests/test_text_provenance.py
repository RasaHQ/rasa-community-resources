"""Synthetic source references: spoken/text fallback must keep their labels."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project.lib.card_text import render_cards


def market_snapshot(replay=False):
    return {'cards': [{'event': {
        'type': 'widget.upsert', 'widget_id': 'market', 'component': 'market_watchlist',
        'revision': 1, 'request_id': 'synthetic', 'data_ref': 'rates'}, 'data_ref': {
        'id': 'rates', 'source': 'Synthetic ECB reference control',
        'fetched_at': '2026-10-22T01:00:00Z', 'as_of': None,
        'replay': replay, 'delayed': False,
        'assumptions': [{'label': 'change_computed_from_two_reference_days',
                         'value': 'two ECB reference days', 'kind': 'assumption'}],
        'payload': {'market_status': 'Currencies only', 'quote_time': None,
                    'quote_date': '2026-10-21', 'rate_basis': 'daily_reference', 'delayed': False,
                    'symbols': [{'symbol': 'EURUSD', 'price': 1.2, 'change': .1, 'change_pct': 9.090909}],
                    'series': {'EURUSD': [{'time': '2026-10-20', 'value': 1.1},
                                          {'time': '2026-10-21', 'value': 1.2}]}}}}]}


class TextProvenance(unittest.TestCase):
    def test_daily_reference_and_derived_change_never_become_live_quote_or_provider_change(self):
        text = render_cards(market_snapshot())
        self.assertIn('daily reference rate, not a live quote; publication day 2026-10-21', text)
        self.assertNotIn('Freshness: live', text)
        self.assertIn('COMPUTED from two ECB reference days 2026-10-20, 2026-10-21, not provider data', text)
        self.assertNotIn('Assumption: change_computed', text)
        self.assertNotIn('9999', text)

    def test_replay_keeps_no_freshness_or_computed_source_claim(self):
        text = render_cards(market_snapshot(replay=True))
        self.assertIn('[REPLAY]', text)
        self.assertNotIn('Freshness:', text)
        self.assertNotIn('COMPUTED', text)
