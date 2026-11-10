"""Execute the native Crew and inspect recorded failure, not just final prose."""

import unittest
from claim_crew.native_fixture import create_fixture
from claim_crew.acceptance import inspect_result


class NativeCompletion(unittest.TestCase):
    def test_complete_native_tasks_are_accepted(self):
        result = create_fixture("vehicle").kickoff()
        self.assertEqual([t.name for t in result.tasks_output], ["source", "checklist"])
        self.assertFalse(result.has_tool_failures)
        self.assertEqual(inspect_result(result, "vehicle")["status"], "ready")

    def test_warn_can_finish_with_failed_source_but_handoff_withholds_it(self):
        result = create_fixture("vehicle", unavailable=True).kickoff()
        self.assertTrue(result.raw)
        self.assertEqual(len(result.tasks_output), 2)
        self.assertTrue(result.has_tool_failures)
        self.assertEqual(result.tool_failures[0].failure.code, "source_unavailable")
        self.assertEqual(inspect_result(result, "vehicle")["status"], "incomplete")

    def test_other_claim_type_retains_its_own_source(self):
        result = create_fixture("travel").kickoff()
        accepted = inspect_result(result, "travel")
        self.assertEqual(accepted["source"]["source_id"], "HC-T-201")
        self.assertEqual(inspect_result(result, "vehicle")["status"], "incomplete")

    def test_removing_only_failure_guard_accepts_the_failed_native_run(self):
        import inspect
        import claim_crew.acceptance as acceptance

        result = create_fixture("vehicle", unavailable=True).kickoff()
        self.assertEqual(inspect_result(result, "vehicle")["status"], "incomplete")
        source = inspect.getsource(acceptance.inspect_result)
        guard = " or result.has_tool_failures"
        self.assertEqual(source.count(guard), 1)
        namespace = dict(vars(acceptance))
        exec(
            compile(source.replace(guard, "", 1), "failure-guard-mutation", "exec"),
            namespace,
        )
        self.assertEqual(
            namespace["inspect_result"](result, "vehicle")["status"], "ready"
        )
        self.assertTrue(result.has_tool_failures)
