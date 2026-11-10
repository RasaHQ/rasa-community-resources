"""Tests for the market card's delegation to the public sources reader."""

import unittest
from unittest.mock import Mock, sentinel

from briefing.market_card import market_card


class MarketCardTests(unittest.TestCase):
    def test_returns_reader_dataref_unchanged_for_requested_currencies(self):
        currencies = ["USD", "GBP"]
        sources = Mock(spec=["market"])
        sources.market.return_value = sentinel.market_dataref

        result = market_card(sources, currencies)

        self.assertIs(result, sentinel.market_dataref)
        sources.market.assert_called_once_with(currencies)
        self.assertIs(sources.market.call_args.args[0], currencies)

    def test_preserves_reader_unavailable_card(self):
        sources = Mock(spec=["market"])
        sources.market.return_value = sentinel.unavailable_dataref

        result = market_card(sources, ["GBP"])

        self.assertIs(result, sentinel.unavailable_dataref)
        sources.market.assert_called_once_with(["GBP"])


if __name__ == "__main__":
    unittest.main()
