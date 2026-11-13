"""Exact local-input, fictional-effect and real HTTP controls; never a bank."""
from copy import deepcopy
from decimal import Decimal
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from contract_inputs import ContractError, MissingContractInput, load_inputs
from mock_server import FixtureState, SymitarMock, MockRefused, DirectFixtureTransport, local_mock_server
from vendor_client import SymitarClient, WireRequest, ErrorCode, ClientError

REQUESTS = {
    "findAccountBy": {"accountNumber": "0000000001"},
    "findAccountByWithBalances": {"accountNumber": "0000000001"},
    "searchAccountTransactions": {"accountNumber": "0000000001", "shareId": "0001", "startDate": "2026-11-01", "endDate": "2026-11-12"},
    "searchLoans": {"accountNumber": "0000000001"},
    "calculateLoanPayoffQuote": {"accountNumber": "0000000001", "loanId": "0001", "payoffDate": "2026-11-13"},
    "postTransfer": {"donor": {"accountNumber": "0000000001", "shareId": "0001"}, "recipient": {"accountNumber": "0000000001", "shareId": "0002"}, "amount": "1.25"},
}


class StateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name).resolve() / "fixture.sqlite3"

    def test_missing_and_corrupt_state_never_reseed(self):
        with self.assertRaises(MockRefused):
            FixtureState(self.path, "epoch-1")
        self.assertFalse(self.path.exists())
        self.path.write_bytes(b"corrupt-original")
        self.path.with_suffix(".sqlite3.lease").write_bytes(b"")
        with self.assertRaises(MockRefused):
            FixtureState(self.path, "epoch-1")
        self.assertEqual(self.path.read_bytes(), b"corrupt-original")

    def test_exclusive_lifetime_lease_and_mismatched_epoch_refuse(self):
        state = FixtureState(self.path, "epoch-1", initialize=True)
        try:
            with self.assertRaises(MockRefused):
                FixtureState(self.path, "epoch-1")
            with self.assertRaises(MockRefused):
                FixtureState(self.path, "epoch-1", initialize=True)
        finally:
            state.close()
        with self.assertRaises(MockRefused):
            FixtureState(self.path, "different-epoch")
        recovered = FixtureState(self.path, "epoch-1")
        recovered.close()

    def test_transaction_failure_rolls_back_and_recovery_keeps_prior_state(self):
        state = FixtureState(self.path, "epoch-1", initialize=True)
        before = state.snapshot()
        def broken(data):
            data["shares"][0]["balance"] = "0.00"
            raise RuntimeError("fixture failure")
        with self.assertRaises(RuntimeError):
            state.transact(broken)
        self.assertEqual(state.snapshot(), before)
        state.close()
        recovered = FixtureState(self.path, "epoch-1")
        self.assertEqual(recovered.snapshot(), before)
        recovered.close()


class ContractMockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.inputs = load_inputs()
        except MissingContractInput as error:
            raise unittest.SkipTest("SKIP: " + str(error)) from None

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name).resolve() / "fixture.sqlite3"
        self.state = FixtureState(self.path, "epoch-1", initialize=True)
        self.addCleanup(self.state.close)
        self.mock = SymitarMock(self.inputs, self.state)

    def send(self, operation, body=None):
        body = deepcopy(REQUESTS[operation] if body is None else body)
        path = self.mock.contract.request(operation, REQUESTS[operation]).replace("{InstitutionUniversalId}", "fictional-institution")
        response = self.mock.send(WireRequest("POST", path, json.dumps(body).encode()))
        self.mock.contract.response(operation, response.status, response.media_type, json.loads(response.body))
        return response

    def test_changed_and_missing_definitions_stop_mock_construction(self):
        changed = dict(self.inputs)
        changed["accounts"] = changed["accounts"].replace(b"operationId: findAccountByWithBalances",
                                                          b"operationId: findAccountByWithBalancesV2")
        self.assertNotEqual(changed["accounts"], self.inputs["accounts"])
        with self.assertRaises(ContractError):
            SymitarMock(changed, self.state)
        with tempfile.TemporaryDirectory() as empty, self.assertRaises(MissingContractInput):
            SymitarMock.from_directory(self.state, Path(empty))

    def test_all_six_operations_fit_exact_vendor_schemas(self):
        for operation in REQUESTS:
            with self.subTest(operation=operation):
                self.assertEqual(self.send(operation).status, 200)

    def test_payment_due_date_and_regular_minimum_past_due_are_distinct(self):
        loan = json.loads(self.send("searchLoans").body)[0]
        self.assertEqual(loan["paymentDue"], "250.75")
        self.assertEqual(loan["dueDate"], "2026-12-01")
        self.assertEqual(len({loan["paymentDue"], loan["payment"], loan["minimumPayment"], loan["pastDueAmount"]}), 4)

    def test_payoff_is_dated_and_never_changes_balances_or_sends(self):
        before = self.state.snapshot()
        first = json.loads(self.send("calculateLoanPayoffQuote").body)
        body = dict(REQUESTS["calculateLoanPayoffQuote"], payoffDate="2026-11-14")
        second = json.loads(self.send("calculateLoanPayoffQuote", body).body)
        self.assertEqual(first["payoffDate"], "2026-11-13")
        self.assertEqual(Decimal(second["totalPayoffAmount"]) - Decimal(first["totalPayoffAmount"]), Decimal("1.23"))
        self.assertEqual(self.state.snapshot(), before)

    def test_history_date_bounds_and_vendor_paging_types(self):
        body = dict(REQUESTS["searchAccountTransactions"], count=1, offset="0")
        result = json.loads(self.send("searchAccountTransactions", body).body)
        self.assertEqual(len(result["transactions"]), 1)
        self.assertEqual(result["paging"], {"nextOffset": "1", "results": 1, "total": 2})
        body.update(offset="1", startDate="2026-11-11", endDate="2026-11-11")
        self.assertEqual(json.loads(self.send("searchAccountTransactions", body).body)["transactions"], [])

    def test_reads_do_not_change_state_and_transfer_commits_once_with_nullable_receipts(self):
        before = self.state.snapshot()
        for operation in REQUESTS:
            if operation != "postTransfer":
                self.assertEqual(self.send(operation).status, 200)
        self.assertEqual(self.state.snapshot(), before)
        result = json.loads(self.send("postTransfer").body)
        self.assertEqual(result, {"status": "success", "confirmationNumber": None, "receiptId": None})
        data, count = self.state.snapshot()
        self.assertEqual(count, 1)
        self.assertEqual(data["shares"][0]["balance"], "1249.25")
        self.assertEqual(data["shares"][1]["balance"], "5401.25")
        self.state.close()
        self.state = FixtureState(self.path, "epoch-1")
        self.addCleanup(self.state.close)
        self.assertEqual(self.state.snapshot(), (data,count))

    def test_outside_customer_combined_selectors_and_coerced_amount_refuse_without_effect(self):
        before = self.state.snapshot()
        bad = deepcopy(REQUESTS["postTransfer"])
        cases = []
        for key,value in [("amount", 1.25),("amount", "NaN"),("amount", "0.00"),("amount", "9999999.99")]:
            cases.append(dict(bad, **{key:value}))
        combined = deepcopy(bad); combined["donor"]["loanId"] = "0001"; cases.append(combined)
        foreign = deepcopy(bad); foreign["recipient"]["accountNumber"] = "outside"; cases.append(foreign)
        for body in cases:
            self.assertEqual(self.send("postTransfer", body).status, 400)
        self.assertEqual(self.state.snapshot(), before)

    def test_response_failure_or_commit_failure_does_not_become_definite_transfer_rejection(self):
        original = self.state.transact
        def fail(operation):
            raise OSError("private-local-path")
        self.state.transact = fail
        try:
            response = self.send("postTransfer")
            self.assertEqual(response.status, 500)
            self.assertNotIn(b"private-local-path", response.body)
        finally:
            self.state.transact = original

    def test_duplicate_raw_key_unknown_route_and_foreign_institution_do_not_dispatch(self):
        before = self.state.snapshot()
        for request in [WireRequest("POST", "/unknown", b"{}"),
                WireRequest("POST", "/a/api/symitar/v1/other/transfers", json.dumps(REQUESTS["postTransfer"]).encode()),
                WireRequest("POST", "/a/api/symitar/v1/fictional-institution/transfers", b'{"amount":"1.00","amount":"2.00"}'),
                WireRequest("POST", "/a/api/symitar/v1/fictional-institution/transfers", json.dumps(REQUESTS["postTransfer"]).encode("utf-16"))]:
            self.assertEqual(self.mock.send(request).status, 400)
        self.assertEqual(self.state.snapshot(), before)

    def test_real_loopback_vendor_wire_and_origin_refusal(self):
        bearer = "fictional-wire-test-capability-123456"
        server = local_mock_server(self.mock, bearer)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
        thread.start()
        try:
            path = self.mock.contract.request("searchLoans", REQUESTS["searchLoans"]).replace("{InstitutionUniversalId}", "fictional-institution")
            for origin,status in [(None,200),("https://evil.invalid",403)]:
                connection = http.client.HTTPConnection(*server.server_address, timeout=2)
                try:
                    headers = {"Content-Type":"application/json","Authorization":"Bearer " + bearer}
                    if origin: headers["Origin"] = origin
                    connection.request("POST", path, json.dumps(REQUESTS["searchLoans"]), headers)
                    response = connection.getresponse()
                    self.assertEqual(response.status, status)
                    data = response.read()
                    if status == 200:
                        self.mock.contract.response("searchLoans",200,"application/json",json.loads(data))
                finally:
                    connection.close()
        finally:
            server.shutdown(); thread.join(2); server.server_close()
        self.assertFalse(thread.is_alive())


class ClientIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_contract_client_and_mock_nullable_transfer_and_unknown_failure(self):
        try:
            inputs = load_inputs()
        except MissingContractInput as error:
            self.skipTest(str(error))
        with tempfile.TemporaryDirectory() as directory:
            state = FixtureState(Path(directory).resolve()/"fixture.sqlite3", "epoch-1", initialize=True)
            try:
                mock = SymitarMock(inputs,state)
                client = SymitarClient(DirectFixtureTransport(mock),mock.contract,"fictional-institution")
                result = await client.call("postTransfer", REQUESTS["postTransfer"])
                self.assertEqual(result.data["status"], "success")
                self.assertIsNone(result.data["receiptId"])
                self.assertEqual(state.snapshot()[1],1)
                def broken(operation): raise OSError("fictional lost persistence")
                state.transact = broken
                with self.assertRaises(ClientError) as caught:
                    await client.call("postTransfer", REQUESTS["postTransfer"])
                self.assertEqual(caught.exception.code, ErrorCode.UNKNOWN)
            finally:
                state.close()


if __name__ == "__main__":
    unittest.main()
