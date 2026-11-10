#!/usr/bin/env python3
"""The scripted builder: an offline stand-in for the builder from Chapter 5. It writes an attempt for a task without any model call.

    python scripted_builder.py tasks/b-limit-currencies.json attempts/mine
It reads the limit from the task and writes only the files the task allows. It never reads the protected tests.
"""
import json
import sys
from pathlib import Path

CARD = '''"""The market watchlist card, limited to {limit} currencies. Written by the scripted builder."""

LIMIT = {limit}


def market_card(sources, currencies):
    """The first {limit} of the traveler's currencies, in alphabetical order, from the ECB daily reference-rate reader."""
    return sources.market(sorted(set(currencies))[:LIMIT])
'''
TEST = '''"""Tests for the market card."""
import unittest

from briefing.market_card import LIMIT, market_card


class Sources:
    def market(self, currencies):
        return currencies


class MarketCard(unittest.TestCase):
    def test_it_asks_for_at_most_the_limit_in_alphabetical_order(self):
        asked = market_card(Sources(), ["USD", "GBP", "JPY", "CHF"])
        self.assertEqual(asked, ["CHF", "GBP", "JPY", "USD"][:LIMIT])


if __name__ == "__main__":
    unittest.main()
'''


def main(task_path, out):
    task = json.loads(Path(task_path).read_text())
    limit = task.get("limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 3:
        print("Set a limit from 1 to 3 in the task first.")
        return 2
    base = Path(out) / "product"
    (base / "briefing").mkdir(parents=True, exist_ok=True)
    (base / "tests").mkdir(parents=True, exist_ok=True)
    (base / "briefing" / "market_card.py").write_text(CARD.format(limit=limit))
    (base / "tests" / "test_market_card.py").write_text(TEST)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
