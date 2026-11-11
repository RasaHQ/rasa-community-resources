"""Fictional domain controls, not vendor-contract or channel authentication proof."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import unittest

from banking_demo import BankingService, Refused, SessionContext


class DomainFixture:
    """No network, licence, financial-provider contract or real customer data."""

    def __init__(self):
        self.calls = []
        self.reads = []
        self.outcome = "queued"
        self.balance_result = {"amount": "123.45", "currency": "USD"}

    def balance(self, account):
        self.reads.append(account)
        return self.balance_result

    def submit(self, operation, transfer):
        self.calls.append((operation, transfer))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class Guard(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.adapter = DomainFixture()
        self.bank = BankingService(self.adapter, clock=lambda: self.now)
        self.context = SessionContext(
            "fictional-host-session", 1, "fictional-caller",
            frozenset({"checking-A", "savings-A"}), 1000,
        )
        self.bank.open_session(self.context)

    def review(self, **changes):
        fields = dict(source="checking-A", destination="savings-A",
                      amount="10.00", currency="USD")
        fields.update(changes)
        return self.bank.review_transfer(self.context, **fields)

    def confirm(self, review):
        self.bank.confirm(self.context, review["review"],
                          {k: review[k] for k in ("source", "destination", "amount", "currency")})

    def test_unregistered_context_cannot_read(self):
        with self.assertRaisesRegex(Refused, "stale_session"):
            self.bank.accounts(replace(self.context, session="unbound"))

    def test_untrusted_payload_is_not_context(self):
        with self.assertRaisesRegex(Refused, "invalid_session"):
            self.bank.accounts({"verified": True, "principal": "fictional-caller"})

    def test_cross_principal_context_refused(self):
        with self.assertRaisesRegex(Refused, "stale_session"):
            self.bank.balance(replace(self.context, principal="other"), "checking-A")

    def test_other_account_refusal_does_not_probe_existence(self):
        for alias in ("other-existing", "unknown", None):
            with self.subTest(alias=alias), self.assertRaisesRegex(Refused, "account_unavailable"):
                self.bank.balance(self.context, alias)
        self.assertEqual(self.adapter.reads, [])

    def test_scoped_reads_need_no_confirmation(self):
        self.assertEqual(self.bank.accounts(self.context)["accounts"], ["checking-A", "savings-A"])
        self.assertEqual(self.bank.balance(self.context, "checking-A")["state"], "supplied")
        self.assertEqual(self.adapter.calls, [])

    def test_expired_assurance_refuses_read_and_write(self):
        review = self.review()
        self.confirm(review)
        self.now = 1000
        for call in (lambda: self.bank.balance(self.context, "checking-A"),
                     lambda: self.bank.submit(self.context, review["review"])):
            with self.assertRaisesRegex(Refused, "assurance_required"):
                call()
        self.assertEqual(self.adapter.calls, [])

    def test_review_does_not_submit(self):
        review = self.review(amount="10")
        self.assertEqual(review["amount"], "10.00")
        self.assertEqual(self.adapter.calls, [])
        with self.assertRaisesRegex(Refused, "confirmation_required"):
            self.bank.submit(self.context, review["review"])

    def test_decimal_invalid_or_unsupported_amounts_refuse(self):
        for value in ("0", "-1", "nan", "inf", "1e999999", "1.001", "1,00", 10, "9" * 30):
            with self.subTest(value=value), self.assertRaises(Refused):
                self.review(amount=value)
        self.assertEqual(self.adapter.calls, [])

    def test_destination_and_currency_are_checked(self):
        for fields in ({"destination": "other"}, {"destination": "checking-A"}, {"currency": "EUR"}):
            with self.subTest(fields=fields), self.assertRaises(Refused):
                self.review(**fields)
        self.assertEqual(self.adapter.calls, [])

    def test_confirmation_requires_exact_review(self):
        review = self.review()
        fields = {k: review[k] for k in ("source", "destination", "amount", "currency")}
        for field, value in (("amount", "11.00"), ("destination", "checking-A"), ("currency", "EUR")):
            fresh = self.review()
            with self.subTest(field=field), self.assertRaisesRegex(Refused, "review_changed"):
                self.bank.confirm(self.context, fresh["review"], {**fields, field: value})
            with self.assertRaises(Refused):
                self.bank.submit(self.context, fresh["review"])
        self.assertEqual(self.adapter.calls, [])

    def test_cancel_cannot_be_confirmed_or_submitted(self):
        review = self.review()
        self.bank.cancel(self.context, review["review"])
        with self.assertRaises(Refused):
            self.confirm(review)
        with self.assertRaises(Refused):
            self.bank.submit(self.context, review["review"])
        self.assertEqual(self.adapter.calls, [])

    def test_expiry_invalidates_even_confirmed_review(self):
        review = self.review()
        self.confirm(review)
        self.now = 220
        with self.assertRaises(Refused):
            self.bank.submit(self.context, review["review"])
        self.assertEqual(self.adapter.calls, [])

    def test_reset_invalidates_old_context_and_consent(self):
        review = self.review()
        self.confirm(review)
        self.bank.reset(self.context)
        new = replace(self.context, revision=2, principal="another-fictional-caller")
        self.bank.open_session(new)
        for ctx in (self.context, new):
            with self.assertRaises(Refused):
                self.bank.submit(ctx, review["review"])
        self.assertEqual(self.adapter.calls, [])

    def test_expired_session_can_still_be_reset(self):
        self.now = 1000
        self.bank.reset(self.context)
        with self.assertRaisesRegex(Refused, "stale_session"):
            self.bank.accounts(self.context)

    def test_ambiguous_dispatch_is_consumed_and_redacted(self):
        review = self.review()
        self.confirm(review)
        self.adapter.outcome = RuntimeError("PRIVATE-INPUT-CANARY")
        outcome = self.bank.submit(self.context, review["review"])
        self.assertEqual(outcome["state"], "unknown")
        self.assertNotIn("PRIVATE-INPUT-CANARY", str(outcome))
        self.assertEqual(self.bank.submit(self.context, review["review"]), outcome)
        self.assertEqual(self.bank.status(self.context, review["review"]), outcome)
        self.assertEqual(self.bank.cancel(self.context, review["review"]), outcome)
        self.assertEqual(len(self.adapter.calls), 1)

    def test_outcomes_not_relabelled_as_posted(self):
        for state in ("queued", "accepted", "posted", "refused", "unsupported", "not-a-state"):
            review = self.review()
            self.confirm(review)
            self.adapter.outcome = state
            result = self.bank.submit(self.context, review["review"])
            self.assertEqual(result["state"], state if state != "not-a-state" else "unknown")

    def test_unknown_outcome_blocks_new_review_even_after_session_reset(self):
        review = self.review()
        self.confirm(review)
        self.adapter.outcome = TimeoutError("fictional lost response")
        self.assertEqual(self.bank.submit(self.context, review["review"])["state"], "unknown")
        with self.assertRaisesRegex(Refused, "outcome_unresolved"):
            self.review()
        self.bank.reset(self.context)
        replacement = replace(self.context, revision=2)
        self.bank.open_session(replacement)
        with self.assertRaisesRegex(Refused, "outcome_unresolved"):
            self.bank.review_transfer(replacement, "checking-A", "savings-A", "10.00", "USD")
        self.assertEqual(len(self.adapter.calls), 1)
        other = replace(self.context, session="other-session", principal="other-caller",
                        accounts=frozenset({"checking-B", "savings-B"}))
        self.bank.open_session(other)
        self.assertEqual(self.bank.review_transfer(
            other, "checking-B", "savings-B", "10.00", "USD"
        )["state"], "pending")

    def test_concurrent_duplicate_submission_only_dispatches_once(self):
        review = self.review()
        self.confirm(review)
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda _: self.bank.submit(self.context, review["review"]), range(24)))
        self.assertEqual(len(self.adapter.calls), 1)
        self.assertTrue(all(value == outcomes[0] for value in outcomes))
        with self.assertRaisesRegex(Refused, "review_not_pending"):
            self.confirm(review)

    def test_second_session_cannot_observe_review(self):
        review = self.review()
        other = replace(self.context, session="other-session")
        self.bank.open_session(other)
        for call in (self.bank.status, self.bank.submit, self.bank.cancel):
            with self.assertRaisesRegex(Refused, "review_unavailable"):
                call(other, review["review"])

    def test_host_cannot_rebind_existing_session(self):
        with self.assertRaisesRegex(Refused, "session_already_bound"):
            self.bank.open_session(replace(self.context, principal="other"))

    def test_no_raw_adapter_payload_or_bad_amount_in_read_result(self):
        for result in ({"amount": "secret-token", "currency": "USD"},
                       {"amount": "10.00", "currency": "USD", "raw": "private"},
                       {"amount": "nan", "currency": "USD"}):
            self.adapter.balance_result = result
            self.assertEqual(self.bank.balance(self.context, "checking-A"), {"state": "unavailable"})


if __name__ == "__main__":
    unittest.main()
