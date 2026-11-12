# SPDX-License-Identifier: MIT
"""Offline controls against privately fetched exact vendor inputs, never a bank."""
import json
from pathlib import Path
import unittest

from contract_inputs import ContractError, OPERATIONS, PINS, SymitarContract
from vendor_client import ClientError, ErrorCode, SymitarClient, WireResponse


def inputs():
    root = Path(__file__).resolve().parents[1] / ".vendor-contracts"
    return {family: (root / (family + ".yaml")).read_bytes() for family in PINS}


REQUESTS = {
    "findAccountBy": {"accountNumber": "0000000001"},
    "findAccountByWithBalances": {"accountNumber": "0000000001"},
    "searchAccountTransactions": {"accountNumber": "0000000001", "shareId": "0001",
                                  "startDate": "2026-01-01", "endDate": "2026-01-31"},
    "searchLoans": {"accountNumber": "0000000001"},
    "calculateLoanPayoffQuote": {"accountNumber": "0000000001", "loanId": "0001",
                                  "payoffDate": "2026-01-31"},
    "postTransfer": {"donor": {"accountNumber": "0000000001", "shareId": "0001"},
                     "recipient": {"accountNumber": "0000000001", "shareId": "0002"},
                     "amount": "1.00"},
}


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = inputs()
        cls.contract = SymitarContract(cls.raw)

    def test_selected_operations_use_actual_post_paths(self):
        self.assertEqual(set(REQUESTS), OPERATIONS)
        for op, body in REQUESTS.items():
            with self.subTest(operation=op):
                path = self.contract.request(op, body)
                self.assertTrue(path.startswith("/a/api/symitar/v1/{InstitutionUniversalId}/"))
        self.assertTrue(self.contract.request("postTransfer", REQUESTS["postTransfer"]).endswith("/transfers"))

    def test_hash_drift_is_rejected(self):
        raw = dict(self.raw)
        raw["loans"] += b"\n"
        with self.assertRaisesRegex(ContractError, "contract_drift"):
            SymitarContract(raw)

    def test_missing_document_refuses(self):
        raw = dict(self.raw)
        raw.pop("accounts")
        with self.assertRaisesRegex(ContractError, "missing_contract"):
            SymitarContract(raw)

    def test_actual_required_fields_types_and_selector_reject(self):
        for op, bad in [("searchLoans", {}), ("searchLoans", {"accountNumber": 1}),
                        ("calculateLoanPayoffQuote", {"accountNumber": "0000000001"}),
                        ("searchAccountTransactions", {"accountNumber": "0000000001",
                          "startDate": "2026-01-01", "endDate": "2026-01-31"}),
                        ("postTransfer", {"amount": "1.00"})]:
            with self.subTest(operation=op), self.assertRaises(ContractError):
                self.contract.request(op, bad)

    def test_actual_loan_response_type_and_nullable_transfer_fields(self):
        self.contract.response("searchLoans", 200, "application/json", [])
        with self.assertRaises(ContractError):
            self.contract.response("searchLoans", 200, "application/json", {})
        self.contract.response("postTransfer", 200, "application/json",
                               {"status": "success", "confirmationNumber": None, "receiptId": None})
        with self.assertRaises(ContractError):
            self.contract.response("postTransfer", 200, "application/json", {"status": "invented"})


class Transport:
    def __init__(self, response=None, error=None):
        self.requests = []
        self.response = response or WireResponse(200, "application/json", b"[]")
        self.error = error

    async def send(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.response


class ClientTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = SymitarContract(inputs())

    def client(self, transport):
        return SymitarClient(transport, self.contract, "fictional-institution")

    async def assert_code(self, transport, op, body, code):
        with self.assertRaises(ClientError) as caught:
            await self.client(transport).call(op, body)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    async def test_constructor_has_no_io_and_validated_call_sends_once(self):
        transport = Transport()
        client = self.client(transport)
        self.assertEqual(transport.requests, [])
        result = await client.call("searchLoans", REQUESTS["searchLoans"])
        self.assertEqual(result.data, [])
        self.assertEqual(len(transport.requests), 1)
        request = transport.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.path, "/a/api/symitar/v1/fictional-institution/loans-search")
        self.assertEqual(json.loads(request.body), REQUESTS["searchLoans"])
        self.assertNotIn("0000000001", repr(request))

    async def test_institution_cannot_change_pinned_route(self):
        transport = Transport()
        for institution in ("..", "a/b", "a?x=y", "a%2fb", "", True):
            with self.subTest(institution=institution), self.assertRaises(ClientError):
                SymitarClient(transport, self.contract, institution)
        self.assertEqual(transport.requests, [])

    async def test_unsupported_operation_and_invalid_request_never_send(self):
        transport = Transport()
        for op, body in [("postLoanPrincipalPayment", {}), ("searchLoans", {}),
                         ("searchLoans", {"accountNumber": float("nan")})]:
            await self.assert_code(transport, op, body, ErrorCode.INVALID_REQUEST)
        self.assertEqual(transport.requests, [])

    async def test_transport_loss_read_unavailable_transfer_unknown_no_retry(self):
        for op, code in [("searchLoans", ErrorCode.UNAVAILABLE), ("postTransfer", ErrorCode.UNKNOWN)]:
            transport = Transport(error=TimeoutError("fictional-sensitive-diagnostic"))
            error = await self.assert_code(transport, op, REQUESTS[op], code)
            self.assertEqual(len(transport.requests), 1)
            self.assertNotIn("fictional-sensitive", str(error))
            self.assertTrue(error.__suppress_context__)

    async def test_invalid_response_or_media_never_becomes_success(self):
        for response in [WireResponse(200, "application/json", b"{}"),
                         WireResponse(200, "text/html", b"[]"),
                         WireResponse(200, "application/json", b"NaN"),
                         WireResponse(200, "application/json", b"x" * 1_048_577)]:
            await self.assert_code(Transport(response), "searchLoans", REQUESTS["searchLoans"],
                                   ErrorCode.INVALID_RESPONSE)

    async def test_transfer_duplicate_json_or_invalid_status_remains_unknown(self):
        for raw in [b'{"status":"success","status":"invented"}', b'{"status":"invented"}']:
            await self.assert_code(Transport(WireResponse(200, "application/json", raw)),
                                   "postTransfer", REQUESTS["postTransfer"], ErrorCode.UNKNOWN)

    async def test_documented_problem_is_redacted_rejection(self):
        raw = json.dumps({"type": "fictional/rejected", "title": "fictional-sensitive",
                          "details": ["fictional-sensitive"]}).encode()
        error = await self.assert_code(Transport(WireResponse(400, "application/problem+json", raw)),
                                       "postTransfer", REQUESTS["postTransfer"], ErrorCode.VENDOR_REJECTED)
        self.assertNotIn("fictional-sensitive", str(error))

    async def test_valid_nullable_receipt_is_not_invented(self):
        raw = b'{"status":"success","receiptId":null,"confirmationNumber":null}'
        result = await self.client(Transport(WireResponse(200, "application/json; charset=utf-8", raw))).call(
            "postTransfer", REQUESTS["postTransfer"])
        self.assertIsNone(result.data["receiptId"])
        self.assertNotIn("success", repr(result))


if __name__ == "__main__":
    unittest.main()
