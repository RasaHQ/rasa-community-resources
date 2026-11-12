"""Host tests, run in CI with a vendor-free test double.

They prove the honest-unavailable rule: every fact the release cannot supply
answers 'unavailable' with a closed reason, only for the caller's own alias,
without any call to the bank, and no path can send a transfer.
"""
import unittest

from bh_demo.host import BankingHubService, Refused, READ_GRANT_SECONDS, UNSOURCED
from bh_demo.permissions import PERMISSIONS
from tests.fakes import FakeClient
from tests.support import Clock


class HostTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.client = FakeClient()
        self.service = BankingHubService(self.client, PERMISSIONS, clock=self.clock)
        self.ctx = self.service.open_session("demo-A")
        self.client.calls.clear()

    def test_accounts_are_the_release_codes_never_relabelled(self):
        self.assertEqual(self.service.accounts(self.ctx), {"accounts": ["DDA-A", "LOAN-A", "SDA-A"]})
        for alias in self.service.accounts(self.ctx)["accounts"]:
            self.assertNotRegex(alias.lower(), "checking|savings|bills")

    def test_relationships_never_authorize_on_their_own(self):
        self.client.party_accounts = lambda party: [("5550010001", "DDA"), ("9999999999", "DDA")]
        ctx = self.service.open_session("demo-A")
        self.assertEqual(self.service.accounts(ctx), {"accounts": ["DDA-A"]})

    def test_unsourced_facts_are_unavailable_with_a_reason_and_no_bank_call(self):
        cases = [(self.service.balance, "DDA-A", "balance"), (self.service.balance, "SDA-A", "balance"),
                 (self.service.history, "DDA-A", "history"), (self.service.payoff, "LOAN-A", "payoff")]
        for method, alias, fact in cases:
            with self.subTest(fact=fact, alias=alias):
                self.assertEqual(method(self.ctx, alias), {"state": "unavailable", "reason": UNSOURCED[fact]})
        self.assertEqual(self.client.calls, [])

    def test_unavailable_still_checks_the_alias_first(self):
        for method, alias in ((self.service.balance, "DDA-B"), (self.service.balance, "LOAN-A"),
                              (self.service.history, "LOAN-A"), (self.service.payoff, "DDA-A"),
                              (self.service.payoff, "LOAN-B")):
            with self.subTest(alias=alias):
                with self.assertRaisesRegex(Refused, "account_unavailable"):
                    method(self.ctx, alias)

    def test_loan_payment_gives_the_date_and_says_the_amount_is_missing(self):
        reply = self.service.loan_payment(self.ctx, "LOAN-A")
        self.assertEqual(reply, {"state": "supplied", "due_date": "2026-12-01",
                                 "reason": UNSOURCED["payment_amount"]})
        self.assertNotIn("amount", reply)
        self.assertEqual(self.client.calls, [("acct", "5550019001")])

    def test_loan_payment_never_reads_another_callers_loan(self):
        with self.assertRaisesRegex(Refused, "account_unavailable"):
            self.service.loan_payment(self.ctx, "LOAN-B")
        self.assertEqual(self.client.calls, [])

    def test_no_path_can_send_a_transfer(self):
        self.assertEqual(self.service.review_transfer(self.ctx, "DDA-A", "SDA-A", "5", "USD"),
                         {"state": "refused", "reason": UNSOURCED["transfer"]})
        self.assertEqual(self.service.status(self.ctx), {"state": "none", "reason": UNSOURCED["transfer"]})
        for step in (lambda: self.service.confirm(self.ctx, "any", {}),
                     lambda: self.service.submit(self.ctx, "any")):
            with self.assertRaisesRegex(Refused, UNSOURCED["transfer"]):
                step()
        from bh_demo.client import BankingHubClient
        self.assertFalse(hasattr(BankingHubClient, "transfer"))  # the real client cannot send one
        self.assertEqual(self.client.calls, [])

    def test_assurance_expires_and_verify_me_is_dated_by_the_phrase(self):
        self.clock.now += READ_GRANT_SECONDS
        with self.assertRaisesRegex(Refused, "assurance_required"):
            self.service.accounts(self.ctx)
        self.service.assure(self.ctx, READ_GRANT_SECONDS + 1)  # an old phrase stays stale
        with self.assertRaisesRegex(Refused, "assurance_required"):
            self.service.accounts(self.ctx)
        self.service.assure(self.ctx, 0)
        self.assertIn("accounts", self.service.accounts(self.ctx))
        for bad in (True, -1, float("nan"), float("inf"), 86401, "0"):
            with self.subTest(age=bad), self.assertRaisesRegex(Refused, "invalid_assurance_event"):
                self.service.assure(self.ctx, bad)

    def test_sessions_are_host_bound(self):
        with self.assertRaisesRegex(Refused, "unknown_simulated_caller"):
            self.service.open_session("someone-else")
        self.service.reset(self.ctx)
        with self.assertRaisesRegex(Refused, "stale_session"):
            self.service.accounts(self.ctx)

    def test_invalid_history_page_is_refused(self):
        for page in (0, 21, "1", True):
            with self.subTest(page=page), self.assertRaisesRegex(Refused, "invalid_page"):
                self.service.history(self.ctx, "DDA-A", page)


if __name__ == "__main__":
    unittest.main()
