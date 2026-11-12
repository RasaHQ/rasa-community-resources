from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import httpx

from silverlake_demo.client import SilverLakeClient, Unavailable, UnknownOutcome
from silverlake_demo.contract import (ARCHIVE_NAME, ContractError, MissingContractInput, envelope, extract,
                                      header, q, sub)
from silverlake_demo.mock import PATH, SilverLakeMock, serve
from tests.support import listener, load_contract


class InputHandling(unittest.TestCase):
    """These run without any vendor bytes."""

    def test_absent_archive_is_a_plain_launch_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(MissingContractInput) as raised:
                extract(Path(folder) / ARCHIVE_NAME, Path(folder) / "cache")
        self.assertIn("jkhy.github.io", str(raised.exception))

    def test_wrong_bytes_fail_even_when_named_correctly(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ARCHIVE_NAME
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("R2026.1.00TPGPub/Validation/TPG_Inquiry.wsdl", "not a vendor definition")
            with self.assertRaises(ContractError) as raised:
                extract(path, Path(folder) / "cache")
            self.assertNotIsInstance(raised.exception, MissingContractInput)


class Fixture:
    def __init__(self, contract, fault="none"):
        self.mock = SilverLakeMock(contract, fault=fault)
        self.sock = listener()
        self.server = serve(self.mock, self.sock)
        self.port = self.sock.getsockname()[1]
        self.client = SilverLakeClient(contract, f"http://127.0.0.1:{self.port}", timeout=2)

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

    def test_soap_actions_come_from_the_pinned_wsdls(self):
        self.assertEqual(self.contract.actions["XferAdd"], "http://jackhenry.com/ws/XferAdd")
        self.assertEqual(set(self.contract.actions), {"AcctSrch", "AcctBalInq", "AcctHistSrch", "AcctInq",
                                                      "LnPayoffInq", "XferAdd"})

    def test_account_search_balance_and_history(self):
        self.assertIn(("7001001", "L"), self.client.accounts("C100001"))
        self.assertEqual(self.client.available_balance("1001001", "D"), "1250.00")  # never CurBal 1275.00
        rows, cursor = self.client.history("1001001", "D")
        self.assertEqual((len(rows), cursor), (3, "3"))
        rows, cursor = self.client.history("1001001", "D", cursor)
        self.assertEqual((len(rows), cursor), (2, None))

    def test_loan_payment_is_two_separate_supplied_facts(self):
        payment = self.client.loan_payment("7001001")
        self.assertEqual(payment["amount_due"], "242.40")  # PmtAmtDue, not PmtAmt 182.40 or past due 60.00
        self.assertEqual(payment["next_due_date"], "2026-12-01")  # NxtPayDt, not NxtSchedPmtDt

    def test_dated_payoff_only_for_a_supplied_date(self):
        self.assertEqual(self.client.payoff("7001001", "2026-11-20")["amount"], "4120.55")
        with self.assertRaises(Unavailable):
            self.client.payoff("7001001", "2026-12-24")

    def test_wrong_kind_and_wrong_action_are_refused(self):
        with self.assertRaises(Unavailable):
            self.client.available_balance("7001001", "L")
        request = ET.Element(q("AcctBalInq"))
        header(request)
        node = sub(request, "InAcctId")
        sub(node, "AcctId", "1001001")
        sub(node, "AcctType", "D")
        reply = httpx.post(f"http://127.0.0.1:{self.fx.port}{PATH}", content=envelope(request), trust_env=False,
                           headers={"SOAPAction": '"http://jackhenry.com/ws/XferAdd"'})
        self.assertEqual(reply.status_code, 500)
        self.assertIn(b"Fault", reply.content)

    def test_schema_violations_are_refused_by_the_mock(self):
        bad = ET.Element(q("XferAdd"))
        header(bad)  # AcctIdFrom is required by the schema
        reply = httpx.post(f"http://127.0.0.1:{self.fx.port}{PATH}", content=envelope(bad), trust_env=False,
                           headers={"SOAPAction": '"http://jackhenry.com/ws/XferAdd"'})
        self.assertEqual(reply.status_code, 500)
        doctype = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e "x">]><x/>'
        reply = httpx.post(f"http://127.0.0.1:{self.fx.port}{PATH}", content=doctype, trust_env=False,
                           headers={"SOAPAction": '"http://jackhenry.com/ws/AcctInq"'})
        self.assertEqual(reply.status_code, 500)

    def test_transfer_accepted_not_posted_and_business_errors_refuse(self):
        self.assertEqual(self.client.transfer(("1001001", "D"), ("1001002", "S"), Decimal("25.50")), "accepted")
        self.assertEqual(self.client.available_balance("1001002", "S"), "325.50")
        self.assertEqual(self.client.transfer(("1001001", "D"), ("1001002", "S"), Decimal("0")), "refused")
        self.assertEqual(self.client.transfer(("1001001", "D"), ("2001001", "D"), Decimal("1")), "refused")
        self.assertEqual(self.client.transfer(("1001001", "D"), ("7001001", "L"), Decimal("1")), "refused")
        self.assertEqual(self.fx.mock.transfers, 1)


class LostReply(unittest.TestCase):
    def test_a_lost_reply_is_unknown_and_never_resent(self):
        fx = Fixture(load_contract(), fault="transfer-response-lost")
        self.addCleanup(fx.close)
        with self.assertRaises(UnknownOutcome):
            fx.client.transfer(("1001001", "D"), ("1001002", "S"), Decimal("10"))
        self.assertEqual(fx.mock.transfers, 1)


if __name__ == "__main__":
    unittest.main()
