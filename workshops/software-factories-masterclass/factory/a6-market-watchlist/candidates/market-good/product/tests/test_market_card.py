"""Tests for the market card."""
import unittest

from briefing.market_card import market_card


class Sources:
    def __init__(self):
        self.asked = None

    def market(self, currencies):
        self.asked = currencies
        return "card"


class MarketCard(unittest.TestCase):
    def test_it_asks_the_reader_for_the_travellers_currencies(self):
        sources = Sources()
        self.assertEqual(market_card(sources, ("USD", "GBP")), "card")
        self.assertEqual(sources.asked, ["USD", "GBP"])


if __name__ == "__main__":
    unittest.main()
