"""Temporal/consent controls without a bank, model, SDK or network."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import unittest

from host import HostPolicy, Refused, Session, TransferIntent


class HostPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.policy = HostPolicy(lambda: self.now)
        self.session = Session("fictional-A", "revision-A", frozenset({"checking", "savings"}), "GBP", 0.0)
        self.intent = TransferIntent("checking", "savings", "50.00", "GBP")

    def prepare(self):
        r = self.policy.review(self.session, self.intent, 4)
        self.policy.delivered(r)
        return r

    def test_read_expiry_boundary(self):
        self.now = 299
        self.policy.require_read(self.session, "checking")
        self.now = 300
        with self.assertRaisesRegex(Refused, "assurance_expired"):
            self.policy.require_read(self.session, "checking")

    def test_transfer_grant_boundary(self):
        self.now = 59
        self.policy.review(self.session, self.intent, 4)
        self.now = 60
        with self.assertRaisesRegex(Refused, "assurance_expired"):
            self.policy.review(self.session, self.intent, 4)

    def test_review_expiry_boundary(self):
        self.prepare()
        self.now = 29
        self.policy.confirm(self.session, self.intent, "yes", 5)
        self.now = 0
        self.prepare()
        self.now = 30
        with self.assertRaisesRegex(Refused, "review_expired"):
            self.policy.confirm(self.session, self.intent, "yes", 5)

    def test_assurance_can_expire_between_review_and_confirmation(self):
        self.now = 59
        self.prepare()
        self.now = 60
        with self.assertRaisesRegex(Refused, "assurance_expired"):
            self.policy.confirm(self.session, self.intent, "yes", 5)

    def test_next_actual_turn_only(self):
        for turn in (4, 6, True):
            with self.subTest(turn=turn):
                self.prepare()
                with self.assertRaises(Refused):
                    self.policy.confirm(self.session, self.intent, "yes", turn)

    def test_failed_or_missing_delivery_never_arms_confirmation(self):
        self.policy.review(self.session, self.intent, 4)
        with self.assertRaisesRegex(Refused, "review_unavailable"):
            self.policy.confirm(self.session, self.intent, "yes", 5)

    def test_stale_delivery_invalidates_pending_review(self):
        stale = self.prepare()
        current = self.policy.review(self.session, self.intent, 4)
        self.assertIsNot(stale, current)
        with self.assertRaises(Refused):
            self.policy.delivered(stale)
        with self.assertRaises(Refused):
            self.policy.confirm(self.session, self.intent, "yes", 5)

    def test_consumed_confirmation_cannot_repeat(self):
        self.prepare()
        permit = self.policy.confirm(self.session, self.intent, "confirmed", 5)
        self.assertEqual(permit.intent.amount, "50")
        with self.assertRaisesRegex(Refused, "review_unavailable"):
            self.policy.confirm(self.session, self.intent, "confirmed", 6)

    def test_changed_amount_cannot_use_old_confirmation(self):
        self.prepare()
        changed = replace(self.intent, amount="51")
        with self.assertRaisesRegex(Refused, "review_changed"):
            self.policy.confirm(self.session, changed, "yes", 5)
        with self.assertRaises(Refused):
            self.policy.confirm(self.session, self.intent, "yes", 5)

    def test_session_or_assurance_rebinding_invalidates_review(self):
        for session in (replace(self.session, revision="revision-B"),
                        replace(self.session, principal="fictional-B"),
                        replace(self.session, assured_at=1.0)):
            with self.subTest(session=session):
                self.prepare()
                with self.assertRaisesRegex(Refused, "review_changed"):
                    self.policy.confirm(session, self.intent, "yes", 5)

    def test_negative_answer_consumes_review(self):
        self.prepare()
        with self.assertRaisesRegex(Refused, "confirmation_required"):
            self.policy.confirm(self.session, self.intent, "no", 5)
        with self.assertRaises(Refused):
            self.policy.confirm(self.session, self.intent, "yes", 6)

    def test_cancel_invalidates_review(self):
        self.prepare()
        self.policy.cancel()
        with self.assertRaises(Refused):
            self.policy.confirm(self.session, self.intent, "yes", 5)

    def test_scope_and_currency_refuse(self):
        for intent in (replace(self.intent, destination="other-person"),
                       replace(self.intent, currency="USD")):
            with self.subTest(intent=intent):
                with self.assertRaises(Refused):
                    self.policy.review(self.session, intent, 4)
        with self.assertRaises(Refused):
            self.policy.require_read(self.session, "other-person")

    def test_invalid_clock_and_future_grant_refuse(self):
        for now in (float("nan"), float("inf"), -1.0, True):
            with self.subTest(now=now):
                self.now = now
                with self.assertRaises(Refused):
                    self.policy.require_read(self.session, "checking")

    def test_new_review_has_a_distinct_private_operation_key(self):
        first = self.prepare()
        permit = self.policy.confirm(self.session, self.intent, "yes", 5)
        second = self.policy.review(self.session, self.intent, 5)
        self.assertEqual(permit.operation_id, first.operation_id)
        self.assertNotEqual(second.operation_id, permit.operation_id)
        self.assertEqual(len(permit.operation_id), 32)

    def test_concurrent_confirmations_consume_one_review(self):
        self.prepare()
        start = threading.Barrier(2)
        def confirm():
            start.wait(timeout=2)
            try:
                return self.policy.confirm(self.session, self.intent, "yes", 5)
            except Refused:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(confirm) for _ in range(2)]
            self.assertEqual(sum(job.result() is not None for job in jobs), 1)

    def test_malformed_private_binding_and_aliases_refuse(self):
        for change in ({"principal": 12}, {"revision": []}, {"currency": 1},
                       {"aliases": {"checking"}}, {"assured_at": float("nan")}):
            with self.subTest(change=change):
                with self.assertRaises(Refused):
                    replace(self.session, **change)
        for change in ({"source": []}, {"destination": True}, {"currency": 1}):
            with self.subTest(change=change):
                with self.assertRaises(Refused):
                    replace(self.intent, **change)

    def test_invalid_amounts_refuse_without_rounding(self):
        for amount in ("0", "-1", "NaN", "1e4", "1,000", True, "9" * 33):
            with self.subTest(amount=amount):
                with self.assertRaises(Refused):
                    replace(self.intent, amount=amount)
        self.assertEqual(replace(self.intent, amount="0.0100").amount, "0.01")


if __name__ == "__main__":
    unittest.main()
