import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from billing_history import LatestFirst, RetainedHistory, demonstrate, minimal_trace, old_conflict, separate_sources
from billing_reconciliation import Observation, Reconciliation, fixture


class BillingHistoryTests(unittest.TestCase):
    def test_same_latest_policy_hides_a_different_conflict_observation(self):
        strict, latest = Reconciliation("account-1", "policy-1"), LatestFirst("account-1", "policy-1")
        for event in minimal_trace():
            strict.receive(event)
            latest.receive(event)
        self.assertEqual(strict.current["policy"], latest.current["policy"])
        self.assertEqual(strict.conflicts, {"policy"})
        self.assertEqual(latest.conflicts, set())

    def test_latest_first_does_detect_when_old_pair_arrives_first(self):
        latest = LatestFirst("account-1", "policy-1")
        for event in [fixture()[-2], old_conflict(), fixture()[-1]]:
            latest.receive(event)
        self.assertEqual(latest.conflicts, {"policy"})

    def test_order_enumeration_retains_exact_denominator(self):
        result = demonstrate()
        self.assertEqual(result["delivery_orders"], 5040)
        self.assertEqual(result["latest_first_missed_old_conflict"], 3360)
        self.assertEqual(result["retained_history_detected_old_conflict"], 5040)

    def test_newer_revision_does_not_clear_prior_contradiction(self):
        strict = Reconciliation("account-1", "policy-1")
        for event in [*fixture(), old_conflict()]:
            strict.receive(event)
        strict.receive(Observation("account-1", "policy-1", "policy", 7, "active"))
        self.assertEqual(strict.report()["status"], "investigate")
        self.assertEqual(strict.report()["invoice_state"], "unknown")

    def test_separate_reports_keep_unconflicted_evidence_but_not_policy(self):
        strict = Reconciliation("account-1", "policy-1")
        for event in [*fixture(), old_conflict()]:
            strict.receive(event)
        result = separate_sources(strict)
        self.assertEqual(result["payment"], {"status": "observed", "state": "settled"})
        self.assertEqual(result["invoice"], {"status": "observed", "state": "paid"})
        self.assertEqual(result["policy"], {"status": "investigate", "state": "unknown"})

    def test_missing_source_never_becomes_observed(self):
        strict = Reconciliation("account-1", "policy-1")
        strict.receive(fixture()[0])
        self.assertEqual(separate_sources(strict)["policy"]["status"], "investigate")

    def test_fast_path_does_not_drop_account_validation(self):
        latest = LatestFirst("account-1", "policy-1")
        latest.receive(fixture()[-1])
        with self.assertRaises(ValueError):
            latest.receive(Observation("other", "policy-1", "policy", 1, "active"))

    def test_fast_path_preserves_old_revision_and_state_validation(self):
        latest = LatestFirst("account-1", "policy-1")
        latest.receive(fixture()[-1])
        for revision, state in [(True, "active"), (1, "not-a-policy-state")]:
            with self.assertRaises(ValueError):
                latest.receive(Observation("account-1", "policy-1", "policy", revision, state))

    def test_diagnostic_history_keeps_both_states_and_revision(self):
        strict = RetainedHistory("account-1", "policy-1")
        for event in minimal_trace():
            strict.receive(event)
        evidence = strict.conflict_evidence()
        self.assertEqual(len(evidence), 1)
        self.assertEqual((evidence[0]["source"], evidence[0]["revision"]), ("policy", 5))
        self.assertEqual({item["state"] for item in evidence[0]["observations"]}, {"lapsed", "active"})

    def test_duplicate_observation_does_not_multiply_diagnostic_history(self):
        strict = RetainedHistory("account-1", "policy-1")
        for event in [*minimal_trace(), *minimal_trace()]:
            strict.receive(event)
        self.assertEqual(len(strict.conflict_evidence()[0]["observations"]), 2)

    def test_source_separation_never_uses_payment_to_fill_policy(self):
        strict = Reconciliation("account-1", "policy-1")
        strict.receive(fixture()[1])
        self.assertEqual(separate_sources(strict)["policy"]["state"], "unknown")


if __name__ == "__main__":
    unittest.main()
