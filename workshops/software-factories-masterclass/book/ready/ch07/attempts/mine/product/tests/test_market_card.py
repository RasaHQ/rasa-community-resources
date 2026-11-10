"""Tests for the market card."""
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
