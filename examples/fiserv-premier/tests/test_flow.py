from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

import httpx

from premier_demo.client import PremierClient, Unavailable, UnknownOutcome
from premier_demo.host import (
    Journal, PremierService, Refused, READ_GRANT_SECONDS, TRANSFER_GRANT_SECONDS, REVIEW_SECONDS)
from premier_demo.mock import MOCK_ORGANIZATION, PremierMock, serve
from premier_demo.permissions import PERMISSIONS
from tests.support import Clock, listener, load_contract


class Fixture:
    def __init__(self, contract, fault="none"):
        self.mock = PremierMock(contract, fault=fault)
        self.sock = listener()
        self.server = serve(self.mock, self.sock)
        self.port = self.sock.getsockname()[1]
        self.client = PremierClient(contract, f"http://127.0.0.1:{self.port}", MOCK_ORGANIZATION, timeout=2)

    def close(self):
        self.server.shutdown()
        self.sock.close()


class WireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()

    def setUp(self):
        self.fx = Fixture(self.contract)
        self.addCleanup(self.fx.close)
        self.client = self.fx.client

    def test_party_relationships_list_accounts(self):
        self.assertIn(("5550010001", "DDA"), self.client.party_accounts("PARTY-A"))
        with self.assertRaises(Unavailable):
            self.client.party_accounts("NOBODY")

    def test_balance_is_available_only_never_ledger(self):
        self.assertEqual(self.client.available_balance("5550010001"), Decimal("1250.00"))
        # ledger is 1275.00 in the fixture: it must never be substituted
        self.assertNotEqual(self.client.available_balance("5550010001"), Decimal("1275.00"))

    def test_history_returns_a_bounded_page_with_a_cursor(self):
        rows, cursor = self.client.transactions("5550010001")
        self.assertEqual(len(rows), 3)
        self.assertIsNotNone(cursor)
        more, end = self.client.transactions("5550010001", cursor)
        self.assertEqual(len(more), 2)
        self.assertIsNone(end)

    def test_loan_payment_uses_the_total_not_due_or_past_due(self):
        payment = self.client.loan_payment("5550019001")
        self.assertEqual(payment["amount"], "182.40")  # fixture also holds 242.40 due and 60.00 past due
        self.assertEqual(payment["due_date"], "2026-12-01")

    def test_payoff_is_the_current_value(self):
        self.assertEqual(self.client.current_payoff("5550019001")["amount"], "4120.55")

    def test_wrong_account_kind_for_a_document_is_not_found(self):
        with self.assertRaises(Unavailable):
            self.client.available_balance("5550019001")  # a loan id sent as DDA

    def test_mock_rejects_a_request_that_breaks_the_contract(self):
        header = json.dumps({"OrganizationId": "X"})
        reply = httpx.post(f"http://127.0.0.1:{self.fx.port}{self.contract.path('xfer')}",
                           content=json.dumps({"XferInfo": {"TransferType": "Bogus"}}),
                           headers={"EFXHeader": header}, trust_env=False)
        self.assertEqual(reply.status_code, 400)
        reply = httpx.post(f"http://127.0.0.1:{self.fx.port}{self.contract.path('dda')}",
                           content=json.dumps({"AcctSel": {"AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"}}}),
                           trust_env=False)  # no EFXHeader at all
        self.assertEqual(reply.status_code, 400)

    def test_transfer_is_accepted_not_posted_and_moves_the_fixture(self):
        self.assertEqual(self.client.transfer("5550010001", "5550010002", Decimal("25.50")), "accepted")
        self.assertEqual(self.client.available_balance("5550010002"), Decimal("325.50"))

    def test_transfer_refusals(self):
        self.assertEqual(self.client.transfer("5550010001", "5550010002", Decimal("99999.00")), "refused")
        self.assertEqual(self.client.transfer("5550010001", "5550020001", Decimal("1.00")), "refused")
        self.assertEqual(self.client.transfer("5550010001", "5550019001", Decimal("1.00")), "refused")
        self.assertEqual(self.fx.mock.transfers, 0)


class LostReply(unittest.TestCase):
    def test_a_lost_reply_is_unknown_and_never_resent(self):
        contract = load_contract()
        fx = Fixture(contract, fault="transfer-response-lost")
        self.addCleanup(fx.close)
        with self.assertRaises(UnknownOutcome):
            fx.client.transfer("5550010001", "5550010002", Decimal("10.00"))
        self.assertEqual(fx.mock.transfers, 1)


class HostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()

    def build(self, fault="none"):
        self.fx = Fixture(self.contract, fault)
        self.addCleanup(self.fx.close)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "journal.sqlite3"
        self.clock = Clock()
        self.journal = Journal(self.path)
        self.addCleanup(lambda: self._safe_close(self.journal))
        self.service = PremierService(self.fx.client, self.journal, PERMISSIONS, clock=self.clock)
        return self.service.open_session("demo-A")

    @staticmethod
    def _safe_close(journal):
        try:
            journal.close()
        except Exception:
            pass

    def review(self, context, amount="25.00"):
        return self.service.review_transfer(context, "checking-A", "bills-A", amount, "USD")

    def exact(self, review):
        return {k: review[k] for k in ("source", "destination", "amount", "currency")}

    def test_reads_use_only_permitted_aliases(self):
        context = self.build()
        self.assertEqual(self.service.accounts(context)["accounts"], ["bills-A", "checking-A", "loan-A"])
        self.assertEqual(self.service.balance(context, "checking-A")["amount"], "1250.00")
        with self.assertRaises(Refused):
            self.service.balance(context, "checking-B")  # another caller's alias
        with self.assertRaises(Refused):
            self.service.balance(context, "loan-A")  # a loan is not a deposit account
        self.assertEqual(self.service.payoff(context, "loan-A")["as_of"], "current")

    def test_read_grant_expires_at_300_seconds(self):
        context = self.build()
        self.clock.now += READ_GRANT_SECONDS - 1
        self.service.accounts(context)
        self.clock.now += 1
        with self.assertRaises(Refused):
            self.service.accounts(context)
        self.service.assure(context)
        self.service.accounts(context)

    def test_transfer_needs_a_fresh_grant_at_review_and_at_send(self):
        context = self.build()
        self.clock.now += TRANSFER_GRANT_SECONDS
        with self.assertRaises(Refused):
            self.review(context)
        self.service.assure(context)
        review = self.review(context)
        self.service.confirm(context, review["review"], self.exact(review))
        self.clock.now += TRANSFER_GRANT_SECONDS  # grant ages before the actual send
        with self.assertRaises(Refused):
            self.service.submit(context, review["review"])
        self.assertEqual(self.fx.mock.transfers, 0)

    def test_review_expires_at_30_seconds_and_cannot_be_confirmed(self):
        context = self.build()
        review = self.review(context)
        self.clock.now += REVIEW_SECONDS
        with self.assertRaises(Refused):
            self.service.confirm(context, review["review"], self.exact(review))
        with self.assertRaises(Refused):
            self.service.submit(context, review["review"])

    def test_changed_details_cancel_the_review(self):
        context = self.build()
        review = self.review(context)
        changed = dict(self.exact(review), amount="26.00")
        with self.assertRaises(Refused):
            self.service.confirm(context, review["review"], changed)
        with self.assertRaises(Refused):
            self.service.submit(context, review["review"])

    def test_one_confirmed_review_sends_exactly_once(self):
        context = self.build()
        review = self.review(context)
        self.service.confirm(context, review["review"], self.exact(review))
        self.assertEqual(self.service.submit(context, review["review"])["state"], "accepted")
        with self.assertRaises(Refused):
            self.service.submit(context, review["review"])  # consumed
        self.assertEqual(self.fx.mock.transfers, 1)
        self.assertEqual(self.service.status(context)["state"], "accepted")

    def test_unsupported_transfers_are_refused_before_review(self):
        context = self.build()
        for args in (("checking-A", "checking-A", "1.00", "USD"), ("checking-A", "bills-A", "1.00", "EUR"),
                     ("checking-A", "loan-A", "1.00", "USD"), ("checking-A", "bills-A", "0", "USD"),
                     ("checking-A", "bills-A", "1.001", "USD"), ("checking-A", "checking-B", "1.00", "USD")):
            with self.assertRaises(Refused):
                self.service.review_transfer(context, *args)

    def test_unknown_outcome_holds_the_principal_across_sessions_and_restart(self):
        context = self.build(fault="transfer-response-lost")
        review = self.review(context)
        self.service.confirm(context, review["review"], self.exact(review))
        self.assertEqual(self.service.submit(context, review["review"])["state"], "unknown")
        self.assertEqual(self.fx.mock.transfers, 1)
        again = self.service.open_session("demo-A")  # a new session cannot clear it
        with self.assertRaises(Refused):
            self.review(again)
        self.assertEqual(self.service.status(again)["state"], "unknown")
        self.assertEqual(self.service.balance(again, "checking-A")["state"], "supplied")  # reads stay open
        self.journal.close()  # restart
        reopened = Journal(self.path)
        self.addCleanup(reopened.close)
        self.assertTrue(reopened.held("demo-A"))
        self.assertFalse(reopened.held("demo-B"))

    def test_journal_has_one_owner_and_stores_no_financial_payload(self):
        self.build()
        with self.assertRaises(Refused):
            Journal(self.path)
        context = self.service.open_session("demo-A")
        review = self.review(context, "12.34")
        self.service.confirm(context, review["review"], self.exact(review))
        self.service.submit(context, review["review"])
        self.journal.close()
        data = self.path.read_bytes()
        for forbidden in (b"12.34", b"5550010001", b"checking-A"):
            self.assertNotIn(forbidden, data)

    def test_reset_fixture_audits_and_keeps_the_old_unknown_in_history(self):
        context = self.build(fault="transfer-response-lost")
        review = self.review(context)
        self.service.confirm(context, review["review"], self.exact(review))
        self.service.submit(context, review["review"])
        with self.assertRaises(Refused):
            Journal(self.path).reset_fixture("while running")  # lock is held by the backend
        self.journal.close()
        stopped = Journal(self.path)
        self.addCleanup(stopped.close)
        with self.assertRaises(Refused):
            stopped.reset_fixture("   ")
        self.assertEqual(stopped.reset_fixture("new fictional exercise"), 2)
        self.assertFalse(stopped.held("demo-A"))
        rows = stopped._db.execute("SELECT state FROM marker").fetchall()
        self.assertEqual(rows, [("historical_unknown",)])
        self.assertEqual(stopped._db.execute("SELECT count(*) FROM audit").fetchone()[0], 1)
        self.service.journal = stopped
        with self.assertRaises(Refused):  # the old session is stale in the new epoch
            self.service.accounts(context)


if __name__ == "__main__":
    unittest.main()
