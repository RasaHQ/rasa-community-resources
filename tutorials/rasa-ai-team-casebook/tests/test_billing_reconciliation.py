"""Exercise the synthetic source/revision contract, not insurance eligibility."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from billing_reconciliation import Observation, Reconciliation, demonstrate, fixture


class BillingReconciliationTests(unittest.TestCase):
    def ready(self):
        result = Reconciliation("account-1", "policy-1")
        for event in fixture():
            result.receive(event)
        return result

    def test_all_720_delivery_orders_and_defective_comparison(self):
        self.assertEqual(demonstrate(), {
            "kind": "authored_synthetic_fixture", "delivery_orders": 720,
            "first_invoice_inference_wrong": 360,
            "per_source_revision_reports_ready": 720,
            "model_calls": 0, "service_calls": 0, "payment_actions": 0,
        })

    def test_missing_policy_cannot_be_inferred_from_paid_invoice(self):
        result = Reconciliation("account-1", "policy-1")
        for event in fixture()[:4]:
            result.receive(event)
        self.assertEqual(result.report()["policy_state"], "unknown")
        self.assertEqual(result.report()["missing"], ["policy"])

    def test_later_arriving_old_revision_does_not_regress_state(self):
        result = self.ready()
        self.assertEqual(result.receive(fixture()[0]), "older")
        self.assertEqual(result.report()["payment_state"], "settled")

    def test_duplicate_has_no_new_action_or_state_change(self):
        result = self.ready()
        before = result.report()
        self.assertEqual(result.receive(fixture()[1]), "duplicate")
        self.assertEqual(result.report(), before)

    def test_same_revision_contradiction_requires_investigation(self):
        result = self.ready()
        conflict = Observation("account-1", "policy-1", "policy", 6, "lapsed")
        self.assertEqual(result.receive(conflict), "conflict")
        result.receive(Observation("account-1", "policy-1", "policy", 7, "active"))
        self.assertEqual(result.report()["status"], "investigate")
        self.assertEqual(result.report()["policy_state"], "unknown")

    def test_conflicting_old_revision_cannot_hide_behind_newer_data(self):
        result = self.ready()
        result.receive(Observation("account-1", "policy-1", "policy", 5, "active"))
        self.assertEqual(result.report()["conflicts"], ["policy"])
        self.assertEqual(result.report()["status"], "investigate")

    def test_other_account_or_policy_is_rejected(self):
        for account, policy in [("account-2", "policy-1"), ("account-1", "policy-2")]:
            with self.subTest(account=account, policy=policy), self.assertRaises(ValueError):
                self.ready().receive(Observation(account, policy, "payment", 42, "settled"))

    def test_invalid_revisions_and_states_are_rejected(self):
        for revision in [True, "42", 0, -1]:
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                self.ready().receive(Observation("account-1", "policy-1", "payment", revision, "settled"))
        for source, state in [("customer", "active"), ("payment", "active")]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.ready().receive(Observation("account-1", "policy-1", source, 42, state))

    def test_settled_payment_does_not_override_lapsed_policy(self):
        result = self.ready()
        result.receive(Observation("account-1", "policy-1", "policy", 7, "lapsed"))
        self.assertEqual(result.report()["payment_state"], "settled")
        self.assertEqual(result.report()["policy_state"], "lapsed")


if __name__ == "__main__":
    unittest.main()
