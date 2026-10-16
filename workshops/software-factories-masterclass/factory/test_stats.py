"""Arithmetic checks for stats.py. Run: python3 -m unittest test_stats (standard library only)."""
import unittest

import stats


class WilsonBounds(unittest.TestCase):
    def test_all_success_lower_bounds_the_masterclass_quotes(self):
        self.assertAlmostEqual(stats.wilson(18, 18)[0], 0.82412, places=5)
        self.assertAlmostEqual(stats.wilson(34, 34)[0], 0.89849, places=5)
        self.assertAlmostEqual(stats.wilson(35, 35)[0], 0.90110, places=5)

    def test_wald_collapses_where_wilson_does_not(self):
        self.assertEqual(stats.wald(18, 18), (1.0, 1.0))
        self.assertLess(stats.wilson(18, 18)[0], 1.0)

    def test_intervals_stay_inside_zero_and_one(self):
        for k, n in ((0, 1), (1, 1), (0, 18), (18, 18), (1, 3)):
            low, high = stats.wilson(k, n)
            self.assertGreaterEqual(low, 0.0)
            self.assertLessEqual(high, 1.0)


class SmallestSample(unittest.TestCase):
    def test_all_success_sizes(self):
        self.assertEqual(stats.smallest_n_for_lower_bound(0.9), 35)
        self.assertEqual(stats.smallest_n_for_lower_bound(0.95), 73)

    def test_one_failure_allowed_is_a_design_sensitivity_not_a_stopping_rule(self):
        self.assertEqual(stats.smallest_n_for_lower_bound(0.9, failures=1), 53)
        self.assertLess(stats.wilson(51, 52)[0], 0.9)
        self.assertGreaterEqual(stats.wilson(52, 53)[0], 0.9)

    def test_unreachable_target_returns_none(self):
        self.assertIsNone(stats.smallest_n_for_lower_bound(0.999999, limit=50))


if __name__ == "__main__":
    unittest.main()
