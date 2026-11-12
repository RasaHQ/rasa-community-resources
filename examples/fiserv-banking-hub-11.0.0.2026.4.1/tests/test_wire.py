"""Client against the local mock, both built from the learner-supplied release file."""
import json
import unittest

import httpx

from bh_demo.client import BankingHubClient, NoRecords, Unavailable
from bh_demo.host import BankingHubService, UNSOURCED
from bh_demo.mock import MOCK_ORGANIZATION, BankingHubMock, serve, status
from bh_demo.permissions import PERMISSIONS
from tests.support import listener, load_contract


class Fixture:
    def __init__(self, contract):
        self.mock = BankingHubMock(contract)
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

    def test_party_relationships_use_the_release_codes(self):
        self.assertEqual(sorted(self.client.party_accounts("PARTY-A")),
                         [("5550010001", "DDA"), ("5550010002", "SDA"), ("5550019001", "LOAN")])

    def test_no_records_is_1120_info_and_an_empty_list(self):
        self.assertEqual(self.client.party_accounts("NOBODY"), [])

    def test_next_payment_date_is_supplied_for_a_loan(self):
        self.assertEqual(self.client.next_payment_date("5550019001"), "2026-12-01")

    def test_a_cross_type_or_unknown_account_is_unavailable(self):
        for ident in ("5550010001", "0000000000"):  # a DDA asked as LOAN, and no account
            with self.subTest(ident=ident), self.assertRaises(Unavailable):
                self.client.next_payment_date(ident)

    def test_mock_rejects_a_request_that_breaks_the_contract(self):
        header = json.dumps({"OrganizationId": MOCK_ORGANIZATION})
        with httpx.Client(trust_env=False) as http:
            bad = http.post(f"http://127.0.0.1:{self.fx.port}/accounts/secured",
                            content=json.dumps({"AcctSel": {}}), headers={"EFXHeader": header})
            no_header = http.post(f"http://127.0.0.1:{self.fx.port}/accounts/secured",
                                  content=json.dumps({"AcctSel": {"AcctKeys": {"AcctId": "5550019001",
                                                                               "AcctType": "LOAN"}}}))
            other = http.post(f"http://127.0.0.1:{self.fx.port}/transfers", content="{}",
                              headers={"EFXHeader": header})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(no_header.status_code, 400)
        self.assertEqual(other.status_code, 404)  # the mock has no transfer route at all


class StatusRules(unittest.TestCase):
    """Success is EFX 0 + Info on HTTP 200; a schema-valid reply alone is not success."""

    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()

    def reply(self, code, body):
        client = BankingHubClient(self.contract, "http://127.0.0.1:9", MOCK_ORGANIZATION)
        transport = httpx.MockTransport(lambda request: httpx.Response(code, json=body))
        original = httpx.Client

        def patched(**kwargs):
            kwargs["transport"] = transport
            return original(**kwargs)
        httpx.Client = patched
        try:
            return client.next_payment_date("5550019001")
        finally:
            httpx.Client = original

    def test_success_status_without_the_record_is_unavailable(self):
        with self.assertRaises(Unavailable):
            self.reply(200, {"Status": status()})

    def test_warning_and_error_statuses_are_never_success(self):
        record = {"AcctKeys": {"AcctId": "5550019001", "AcctType": "LOAN"},
                  "AcctStatus": {"AcctStatusCode": "x"}, "LoanAcctInfo": {"NextPmt": {"PmtDt": "2026-12-01"}}}
        for code, efx in ((200, status("50", "General warning", "Warning")),
                          (200, status("1040", "Request declined", "Warning")),
                          (404, status("1121", "No records found", "Error")),
                          (200, status("0", "Success", "Warning"))):
            with self.subTest(efx=efx["StatusCode"]), self.assertRaises(Unavailable):
                self.reply(code, {"Status": efx, "AcctRec": record})
        self.assertEqual(self.reply(200, {"Status": status(), "AcctRec": record}), "2026-12-01")

    def test_no_records_is_distinct_from_unavailable(self):
        with self.assertRaises(NoRecords):
            self.reply(200, {"Status": status("1120", "No records match the selection criteria")})


class EndToEnd(unittest.TestCase):
    """The host over the real client and mock: what a caller can actually get."""

    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()

    def test_a_caller_gets_aliases_a_date_and_honest_unavailable_answers(self):
        fx = Fixture(self.contract)
        self.addCleanup(fx.close)
        service = BankingHubService(fx.client, PERMISSIONS)
        ctx = service.open_session("demo-A")
        self.assertEqual(service.accounts(ctx), {"accounts": ["DDA-A", "LOAN-A", "SDA-A"]})
        self.assertEqual(service.loan_payment(ctx, "LOAN-A")["due_date"], "2026-12-01")
        before = fx.mock.calls
        self.assertEqual(service.balance(ctx, "DDA-A")["reason"], UNSOURCED["balance"])
        self.assertEqual(service.payoff(ctx, "LOAN-A")["reason"], UNSOURCED["payoff"])
        self.assertEqual(service.history(ctx, "SDA-A")["reason"], UNSOURCED["history"])
        self.assertEqual(fx.mock.calls, before)  # unavailable answers never reach the bank


if __name__ == "__main__":
    unittest.main()
