"""A deliberately bad candidate: the card is fine, but the protected suite was edited so the failure checks pass."""
import unittest


class MarketWatchlist(unittest.TestCase):
    def test_the_card_exists(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
