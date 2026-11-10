import unittest
from crewai.tools.tool_failure import ToolFailurePolicy
from claim_crew.failure_signals import failure_case


class NativeFailureSignals(unittest.TestCase):
    def observed(self, declared, policy):
        row = failure_case(declared, policy)
        self.assertEqual(row["tool_calls"], 1)
        self.assertEqual(
            row["observed_results"],
            [
                {
                    "declared": declared,
                    "error_text": "Synthetic source temporarily unavailable (code: source_unavailable)",
                }
            ],
        )
        return row

    def test_plain_error_string_finishes_and_passes_under_all_policies(self):
        for policy in ToolFailurePolicy:
            row = self.observed(False, policy)
            self.assertEqual(row["completed_tasks"], 2)
            self.assertTrue(row["final_output_present"])
            self.assertEqual(row["recorded_tool_failures"], 0)
            self.assertEqual(row["handoff_status"], "ready")

    def test_same_error_wording_declared_warn_is_recorded_and_withheld(self):
        row = self.observed(True, ToolFailurePolicy.WARN)
        self.assertEqual(row["completed_tasks"], 2)
        self.assertTrue(row["final_output_present"])
        self.assertEqual(row["recorded_tool_failures"], 1)
        self.assertEqual(row["handoff_status"], "incomplete")

    def test_declared_ignore_finishes_without_recorded_failure(self):
        row = self.observed(True, ToolFailurePolicy.IGNORE)
        self.assertEqual(row["recorded_tool_failures"], 0)
        self.assertEqual(row["handoff_status"], "ready")

    def test_declared_raise_aborts_native_execution(self):
        row = self.observed(True, ToolFailurePolicy.RAISE)
        self.assertEqual(row["exception"], "ToolExecutionFailedError")
        self.assertNotIn("handoff_status", row)


if __name__ == "__main__":
    unittest.main()
