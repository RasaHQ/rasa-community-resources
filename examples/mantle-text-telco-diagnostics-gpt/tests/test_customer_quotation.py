"""Regression-detector controls; passing tests do not mean the service is repaired."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controls.customer_quotation import require_request_boundary, run_cases


class CustomerQuotationControls(unittest.TestCase):
    def test_detector_exposes_current_quotation_failure(self):
        result = run_cases()
        self.assertEqual(result["cases"]["quotation"]["result"]["status"], "selected")
        self.assertIsNotNone(result["cases"]["quotation"]["selection"])
        with self.assertRaisesRegex(AssertionError, "quotation: mentioning"):
            require_request_boundary(result)

    def test_negation_and_positive_remain_distinct_without_commands(self):
        cases = run_cases()["cases"]
        self.assertEqual(cases["negation"]["result"]["status"], "blocked")
        self.assertIsNone(cases["negation"]["selection"])
        self.assertEqual(cases["request"]["result"]["status"], "selected")
        self.assertIsNotNone(cases["request"]["selection"])
        self.assertTrue(all(not case["commands"] for case in cases.values()))


if __name__ == "__main__":
    unittest.main()
