"""Client, mock and host against the learner-supplied release definitions.

The wire tests need the pinned release archive; they skip only when it is
absent, and a skipped run never qualifies a gate. HostTests also run in CI
through test_host_ci with a vendor-free test double.
"""
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from bh_demo.client import BankingHubClient, Unavailable, UnknownOutcome
from bh_demo.host import (
    Journal, BankingHubService, Refused, READ_GRANT_SECONDS, TRANSFER_GRANT_SECONDS, REVIEW_SECONDS,
    UNSOURCED)
from bh_demo.mock import MOCK_ORGANIZATION, BankingHubMock, serve, status
from bh_demo.permissions import PERMISSIONS
from tests.support import Clock, listener, load_contract


class Fixture:
    def __init__(self, contract, fault="none"):
        self.mock = BankingHubMock(contract, fault=fault)
        self.sock = listener()
        self.server = serve(self.mock, self.sock)
        self.port = self.sock.getsockname()[1]
        self.client = BankingHubClient(contract, f"http://127.0.0.1:{self.port}", MOCK_ORGANIZATION, timeout=2)

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
        self.assertIn(("5550010002", "SDA"), self.client.party_accounts("PARTY-A"))
        self.assertEqual(self.client.party_accounts("NOBODY"), [])  # EFX 1120 is no records

    def test_balance_is_the_avail_entry_never_ledger(self):
        self.assertEqual(self.client.available_balance("5550010001"), Decimal("1250.00"))
        # Ledger is 1275.00 in the fixture and listed first: it must never be substituted.
        self.assertNotEqual(self.client.available_balance("5550010001"), Decimal("1275.00"))

    def test_a_missing_or_repeated_avail_entry_is_unavailable(self):
        avail = {"BalType": "Avail", "CurAmt": {"Amt": 1.0, "CurCode": {"CurCodeValue": "USD"}}}
        ledger = dict(avail, BalType="Ledger")
        for balances in ([ledger], [avail, avail], [dict(avail, BalType="avail")], []):
            with self.subTest(balances=balances):
                record = {"AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"},
                          "DepositAcctInfo": {"AcctBal": balances}}
                with patch.object(self.client, "_record", return_value=record), self.assertRaises(Unavailable):
                    self.client.available_balance("5550010001")

    def test_loan_payment_is_the_total_entry_never_a_part_or_a_sum(self):
        payment = self.client.loan_payment("5550019001")
        # The fixture also holds Principal 152.00 and Interest 30.40, listed first.
        self.assertEqual(payment, {"due_date": "2026-12-01", "amount": "182.40", "currency": "USD"})

    def test_a_missing_or_repeated_total_entry_is_unavailable(self):
        def part(label, amount=1.0):
            return {"CompositeCurAmtType": label, "CurAmt": {"Amt": amount, "CurCode": {"CurCodeValue": "USD"}}}
        for parts in ([part("Principal"), part("Interest")], [part("Total"), part("Total", 2.0)],
                      [part("Total", float("nan"))], [part("total")]):
            with self.subTest(parts=parts):
                record = {"AcctKeys": {"AcctId": "5550019001", "AcctType": "LOAN"},
                          "LoanAcctInfo": {"NextPmt": {"PmtDt": "2026-12-01", "PmtCompositeAmt": parts}}}
                with patch.object(self.client, "_record", return_value=record), self.assertRaises(Unavailable):
                    self.client.loan_payment("5550019001")

    def test_wrong_account_kind_is_not_found(self):
        with self.assertRaises(Unavailable):
            self.client.available_balance("5550019001")  # a loan id sent as DDA
        with self.assertRaises(Unavailable):
            self.client.available_balance("5550010002")  # an SDA id sent as DDA

    def test_mock_rejects_a_request_that_breaks_the_contract_or_carries_a_transfer_type(self):
        header = json.dumps({"OrganizationId": "X"})
        body = {"XferInfo": {"TransferType": "Internal",
                             "FromAcctRef": {"AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"}},
                             "ToAcctRef": {"AcctKeys": {"AcctId": "5550010002", "AcctType": "SDA"}},
                             "CurAmt": {"Amt": 1.0, "CurCode": {"CurCodeValue": "USD"}}}}
        reply = httpx.post(f"http://127.0.0.1:{self.fx.port}{self.contract.path('xfer')}",
                           content=json.dumps(body), headers={"EFXHeader": header}, trust_env=False)
        self.assertEqual(reply.status_code, 400)
        reply = httpx.post(f"http://127.0.0.1:{self.fx.port}{self.contract.path('acct')}",
                           content=json.dumps({"AcctSel": {"AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"}}}),
                           trust_env=False)  # no EFXHeader at all
        self.assertEqual(reply.status_code, 400)
        self.assertEqual(self.fx.mock.transfers, 0)

    def test_transfer_omits_transfer_type_is_accepted_not_posted_and_moves_the_fixture(self):
        sent = []
        original = self.fx.mock._transfer
        self.fx.mock._transfer = lambda body: (sent.append(body), original(body))[1]
        self.assertEqual(self.client.transfer("5550010001", "DDA", "5550010002", "SDA", Decimal("25.50")),
                         "accepted")
        self.assertNotIn("TransferType", sent[0]["XferInfo"])
        self.assertNotIn("RecurModel", sent[0]["XferInfo"])
        self.assertEqual(self.client.available_balance("5550010001"), Decimal("1224.50"))
        self.assertEqual(self.fx.mock.transfers, 1)

    def test_transfer_refusals_move_nothing(self):
        for args in (("5550010001", "DDA", "5550010002", "SDA", Decimal("99999.00")),  # over balance
                     ("5550010001", "DDA", "5550020001", "DDA", Decimal("1.00")),     # another party
                     ("5550010001", "DDA", "5550019001", "LOAN", Decimal("1.00")),    # to a loan
                     ("5550010002", "SDA", "5550010001", "DDA", Decimal("1.00")),     # from an SDA
                     ("5550010001", "DDA", "5550010002", "DDA", Decimal("1.00"))):    # wrong type code
            with self.subTest(args=args):
                self.assertEqual(self.client.transfer(*args), "refused")
        self.assertEqual(self.fx.mock.transfers, 0)

    def test_only_201_with_valid_is_accepted_and_any_other_reply_is_unknown_or_refused(self):
        valid = {"Status": status(), "XferStatusRec": {"XferKeys": {}, "XferStatus": {"XferStatusCode": "Valid"}}}
        cases = [
            ((200, valid, False), UnknownOutcome),  # Fiserv's older sample shows 200: never assume
            ((500, {"Status": status("999", "Error", "Error")}, False), UnknownOutcome),
            ((201, {"Status": status("50", "Warning", "Warning")}, False), UnknownOutcome),
            ((201, dict(valid, XferStatusRec={"XferKeys": {}, "XferStatus": {"XferStatusCode": "Deleted"}}),
              False), UnknownOutcome),
            ((201, dict(valid, XferStatusRec={"XferKeys": {}, "XferStatus": {"XferStatusCode": "Rejected"}}),
              False), "refused"),
            ((422, {"Status": status("1020", "Not permitted", "Error")}, False), "refused"),
            # Council M1: the EFX gate itself decides. Each of these carries a Valid status.
            ((201, dict(valid, Status=status("0", "Success", "Warning")), False), UnknownOutcome),
            ((201, dict(valid, Status=status("1040", "Request declined", "Info")), False), UnknownOutcome),
            ((201, dict(valid, XferStatusRec={"XferKeys": {}, "XferStatus": {"XferStatusCode": "valid"}}),
              False), UnknownOutcome),
            ((201, dict(valid, XferStatusRec={"XferKeys": {}, "XferStatus": {"XferStatusCode": " Valid"}}),
              False), UnknownOutcome),
        ]
        for reply, expected in cases:
            with self.subTest(reply=reply[:2]):
                self.fx.mock.handle = lambda path, header, raw, reply=reply: reply
                args = ("5550010001", "DDA", "5550010002", "SDA", Decimal("1.00"))
                if expected is UnknownOutcome:
                    with self.assertRaises(UnknownOutcome):
                        self.client.transfer(*args)
                else:
                    self.assertEqual(self.client.transfer(*args), expected)


class RawReplies(unittest.TestCase):
    """Council L2 and L3: a duplicated key or a malformed reply never decides by accident."""

    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()

    def client_with(self, code, raw):
        client = BankingHubClient(self.contract, "http://127.0.0.1:9", MOCK_ORGANIZATION)
        transport = httpx.MockTransport(lambda request: httpx.Response(code, content=raw))
        original = httpx.Client
        def patched(**kwargs):
            kwargs["transport"] = transport
            return original(**kwargs)
        return client, patch.object(httpx, "Client", patched)

    def test_a_duplicated_status_key_is_unknown_for_a_transfer(self):
        raw = (b'{"Status": {"StatusCode": "0", "StatusDesc": "Success", "Severity": "Info", '
               b'"SvcProviderName": "X"}, "XferStatusRec": {"XferKeys": {}, "XferStatus": '
               b'{"XferStatusCode": "Rejected", "XferStatusCode": "Valid"}}}')
        client, patched = self.client_with(201, raw)
        with patched, self.assertRaises(UnknownOutcome):
            client.transfer("5550010001", "DDA", "5550010002", "SDA", Decimal("1.00"))

    def test_a_duplicated_balance_label_is_unavailable(self):
        raw = (b'{"Status": {"StatusCode": "0", "StatusDesc": "Success", "Severity": "Info", '
               b'"SvcProviderName": "X"}, "AcctRec": {"AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"}, '
               b'"AcctStatus": {"AcctStatusCode": "x"}, "DepositAcctInfo": {"AcctBal": [{"BalType": "Ledger", '
               b'"BalType": "Avail", "CurAmt": {"Amt": 1.0, "CurCode": {"CurCodeValue": "USD"}}}]}}}')
        client, patched = self.client_with(200, raw)
        with patched, self.assertRaises(Unavailable):
            client.available_balance("5550010001")

    def test_an_amount_the_wire_cannot_carry_exactly_is_refused_unsent(self):
        fx = Fixture(self.contract)
        self.addCleanup(fx.close)
        self.assertEqual(fx.client.transfer("5550010001", "DDA", "5550010002", "SDA",
                                            Decimal("9007199254740993.00")), "refused")
        self.assertEqual(fx.mock.transfers, 0)


class LostReply(unittest.TestCase):
    def test_a_lost_reply_is_unknown_and_never_resent(self):
        contract = load_contract()
        fx = Fixture(contract, fault="transfer-response-lost")
        self.addCleanup(fx.close)
        with self.assertRaises(UnknownOutcome):
            fx.client.transfer("5550010001", "DDA", "5550010002", "SDA", Decimal("10.00"))
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
        self.service = BankingHubService(self.fx.client, self.journal, PERMISSIONS, clock=self.clock)
        return self.service.open_session("demo-A")

    @staticmethod
    def _safe_close(journal):
        try:
            journal.close()
        except Exception:
            pass

    def review(self, context, amount="25.00"):
        return self.service.review_transfer(context, "DDA-A", "SDA-A", amount, "USD")

    def exact(self, review):
        return {k: review[k] for k in ("source", "destination", "amount", "currency")}

    def test_reads_use_only_permitted_aliases_and_the_release_codes(self):
        context = self.build()
        self.assertEqual(self.service.accounts(context)["accounts"], ["DDA-A", "LOAN-A", "SDA-A"])
        self.assertEqual(self.service.balance(context, "DDA-A")["amount"], "1250.00")
        self.assertEqual(self.service.loan_payment(context, "LOAN-A")["amount"], "182.40")
        with self.assertRaises(Refused):
            self.service.balance(context, "DDA-B")  # another caller's alias
        with self.assertRaises(Refused):
            self.service.balance(context, "LOAN-A")  # a loan is not a deposit account

    def test_unsourced_facts_are_unavailable_with_a_reason_and_no_bank_call(self):
        context = self.build()
        calls = getattr(self.fx.client, "calls", None)
        if calls is not None:
            calls.clear()
        self.assertEqual(self.service.balance(context, "SDA-A"),
                         {"state": "unavailable", "reason": UNSOURCED["sda_balance"]})
        self.assertEqual(self.service.history(context, "DDA-A"),
                         {"state": "unavailable", "reason": UNSOURCED["history"]})
        self.assertEqual(self.service.payoff(context, "LOAN-A"),
                         {"state": "unavailable", "reason": UNSOURCED["payoff"]})
        if calls is not None:
            self.assertEqual(calls, [])
        with self.assertRaises(Refused):
            self.service.payoff(context, "LOAN-B")  # the alias is still checked first
        for page in (0, 21, "1", True):
            with self.subTest(page=page), self.assertRaises(Refused):
                self.service.history(context, "DDA-A", page)

    def test_read_grant_expires_at_300_seconds(self):
        context = self.build()
        self.clock.now += READ_GRANT_SECONDS - 1
        self.service.accounts(context)
        self.clock.now += 1
        with self.assertRaises(Refused):
            self.service.accounts(context)
        self.service.assure(context)
        self.service.accounts(context)

    def test_assurance_is_dated_by_when_the_phrase_was_said(self):
        context = self.build()
        self.service.assure(context, 299)
        self.service.accounts(context)
        self.service.assure(context, 300)
        with self.assertRaises(Refused):
            self.service.accounts(context)
        self.service.assure(context, 59)
        self.review(context)
        self.service.assure(context, 60)
        with self.assertRaises(Refused):
            self.review(context)
        for bad in (-1, float("nan"), float("inf"), True, "0", 10 ** 9):
            with self.assertRaises(Refused):
                self.service.assure(context, bad)

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
        for args in (("DDA-A", "SDA-A", "1000000.01", "USD"),  # council L1: above the teaching cap
                     ("DDA-A", "DDA-A", "1.00", "USD"), ("DDA-A", "SDA-A", "1.00", "EUR"),
                     ("DDA-A", "LOAN-A", "1.00", "USD"), ("DDA-A", "SDA-A", "0", "USD"),
                     ("DDA-A", "SDA-A", "1.001", "USD"), ("DDA-A", "DDA-B", "1.00", "USD"),
                     ("SDA-A", "DDA-A", "1.00", "USD")):
            with self.subTest(args=args), self.assertRaises(Refused):
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
        self.assertEqual(self.service.balance(again, "DDA-A")["state"], "supplied")  # reads stay open
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
        for forbidden in (b"12.34", b"5550010001", b"DDA-A"):
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
