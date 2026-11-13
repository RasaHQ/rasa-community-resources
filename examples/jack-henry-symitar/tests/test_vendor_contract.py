# SPDX-License-Identifier: MIT
"""Offline controls against privately fetched exact vendor inputs, never a bank."""
import json
from pathlib import Path
import unittest
import tempfile

from contract_inputs import (ContractError, MissingContractInput, OPERATIONS, PINS,
                             SymitarContract, load_inputs)
from vendor_client import ClientError, ErrorCode, SymitarClient, WireResponse


def inputs():
    try:
        return load_inputs()
    except MissingContractInput as error:
        raise unittest.SkipTest("SKIP: " + str(error)) from None


class VendorFreeTests(unittest.TestCase):
    def test_missing_input_stops_launch_with_manual_download_notice(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(MissingContractInput) as caught:
                load_inputs(Path(directory))
        self.assertIn("manually download", str(caught.exception))
        self.assertIn("vendor-inputs/", str(caught.exception))
        self.assertIn("accounts/accounts.yaml", str(caught.exception))

    def test_wrong_or_malformed_present_input_fails_not_skips(self):
        for raw in (b"wrong revision", b"{malformed yaml"):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "accounts").mkdir()
                (root / "accounts/accounts.yaml").write_bytes(raw)
                with self.assertRaises(ContractError) as caught:
                    load_inputs(root)
                self.assertNotIsInstance(caught.exception, MissingContractInput)

    def test_loader_and_client_have_no_collection_runtime_import(self):
        import ast
        root = Path(__file__).resolve().parents[1]
        for file in ("contract_inputs.py", "vendor_client.py"):
            tree = ast.parse((root / file).read_text())
            modules = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    modules.append(node.module or "")
            self.assertFalse(any(name.startswith(("zeo_integrations", "zeocore", "zeo_core", "banking_demo"))
                                 for name in modules))


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

    def test_a_newer_file_that_changes_nothing_used_still_loads_and_says_so(self):
        raw = dict(self.raw)
        raw["loans"] += b"\n"  # different bytes, same content
        contract = SymitarContract(raw)
        self.assertEqual(contract.newer_files, ("loans",))
        self.assertEqual(SymitarContract(self.raw).newer_files, ())

    def test_the_recorded_exchanges_are_valid_on_the_pinned_files_and_cover_every_operation(self):
        from recorded_exchanges import EXCHANGES
        self.assertEqual(self.contract.exchange_problems(), [])
        self.assertEqual({name for name, side, *_ in EXCHANGES if side == "request"}, OPERATIONS)
        self.assertEqual({name for name, side, status, *_ in EXCHANGES if side == "response" and status == 200},
                         OPERATIONS)

    def _edited(self, family, edit):
        import yaml
        document = yaml.safe_load(self.raw[family])
        edit(document)
        raw = dict(self.raw)
        raw[family] = yaml.safe_dump(document).encode()
        return raw

    @staticmethod
    def _resolve(document, node):
        while isinstance(node, dict) and "$ref" in node:
            target = document
            for part in node["$ref"][2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
            node = target
        return node

    def _operation(self, document, name):
        return next(op for methods in document["paths"].values() for op in methods.values()
                    if isinstance(op, dict) and op.get("operationId") == name)

    def _request_root(self, document, name):
        schema = self._operation(document, name)["requestBody"]["content"]["application/json"]["schema"]
        return self._resolve(document, schema)

    def _reply_root(self, document, name):
        schema = self._operation(document, name)["responses"]["200"]["content"]["application/json"]["schema"]
        return self._resolve(document, schema)

    def assert_stops(self, family, edit, prefix):
        from contract_inputs import VendorChanged
        with self.assertRaises(VendorChanged) as caught:
            SymitarContract(self._edited(family, edit))
        self.assertTrue(any(change.startswith(prefix) for change in caught.exception.changes),
                        caught.exception.changes)
        self.assertNotIn("contract_drift", str(caught.exception))

    def test_a_change_the_recorded_traffic_no_longer_fits_stops_and_names_it(self):
        def payoff_amount_type(document):
            body = self._reply_root(document, "calculateLoanPayoffQuote")
            self._resolve(document, body["properties"]["totalPayoffAmount"])["type"] = "number"

        def require_new_field(document):
            body = self._request_root(document, "searchLoans")
            body.setdefault("properties", {})["memberNumbers"] = {"type": "array", "items": {"type": "string"}}
            body["required"] = sorted(set(body.get("required", [])) | {"memberNumbers"})

        def limit_account_number(document):
            body = self._request_root(document, "searchLoans")
            self._resolve(document, body["properties"]["accountNumber"])["maxLength"] = 3

        def amount_max_length_in_all_of(document):
            holder = self._request_root(document, "postTransfer")["properties"]
            holder["amount"] = {"allOf": [holder["amount"]], "maxLength": 1}

        def fewer_items(document):
            body = self._reply_root(document, "searchAccountTransactions")
            self._resolve(document, body["properties"]["transactions"])["maxItems"] = 1

        def remove_transfers(document):
            self._operation(document, "postTransfer")["operationId"] = "postTransferV2"

        cases = (("loans", payoff_amount_type, "calculateLoanPayoffQuote 200 response is no longer valid at totalPayoffAmount"),
                 ("loans", require_new_field, "searchLoans request is no longer valid at the whole body"),
                 ("loans", limit_account_number, "searchLoans request is no longer valid at accountNumber"),
                 ("transfers", amount_max_length_in_all_of, "postTransfer request is no longer valid at amount"),
                 ("transactions", fewer_items, "searchAccountTransactions 200 response is no longer valid at transactions"),
                 ("transfers", remove_transfers, "postTransfer is no longer in the files"))
        for family, edit, prefix in cases:
            with self.subTest(edit=edit.__name__):
                self.assert_stops(family, edit, prefix)

    def test_a_required_field_added_inside_every_oneof_or_anyof_branch_stops(self):
        def history_one_of(document):
            # Every oneOf branch of the history request gains a required field; the
            # branch count and order, outer properties and required list are unchanged.
            root = self._request_root(document, "searchAccountTransactions")
            self.assertTrue(root.get("oneOf"))
            for branch in root["oneOf"]:
                self._resolve(document, branch)["required"] = list(
                    self._resolve(document, branch).get("required", [])) + ["newRequiredField"]

        def transfer_any_of(document):
            self._request_root(document, "postTransfer")["anyOf"] = [
                {"required": ["newRequiredField"]}, {"required": ["otherNewField"]}]

        self.assert_stops("transactions", history_one_of, "searchAccountTransactions request is no longer valid")
        self.assert_stops("transfers", transfer_any_of, "postTransfer request is no longer valid")

    def test_a_rule_on_the_request_root_or_a_nested_object_stops(self):
        def root_rule(document):
            self._request_root(document, "postTransfer")["maxProperties"] = 0

        def root_composed(document):
            self._request_root(document, "postTransfer")["allOf"] = [{"maxProperties": 0}]

        def nested_rule(document):
            donor = self._resolve(document, self._request_root(document, "postTransfer")["properties"]["donor"])
            donor["additionalProperties"] = False
            donor["maxProperties"] = 1

        def nested_composed(document):
            properties = self._request_root(document, "postTransfer")["properties"]
            properties["donor"] = {"allOf": [properties["donor"], {"maxProperties": 1}]}

        for edit, where in ((root_rule, "the whole body"), (root_composed, "the whole body"),
                            (nested_rule, "donor"), (nested_composed, "donor")):
            with self.subTest(edit=edit.__name__):
                self.assert_stops("transfers", edit, "postTransfer request is no longer valid at " + where)

    def test_a_narrowed_enum_on_a_value_the_example_reads_stops(self):
        def narrow_status(document):
            status = self._resolve(document, self._reply_root(document, "postTransfer")["properties"]["status"])
            self.assertIn("success", status["enum"])
            status["enum"] = [value for value in status["enum"] if value != "success"]

        self.assert_stops("transfers", narrow_status, "postTransfer 200 response is no longer valid at status")

    def test_documentation_changes_and_a_new_optional_request_field_still_load(self):
        def describe(document):
            target = self._resolve(document, self._request_root(document, "postTransfer")["properties"]["amount"])
            target["description"] = "Reworded by the vendor."
            target["example"] = "9.99"
            reply = self._resolve(document, self._reply_root(document, "postTransfer")["properties"]["status"])
            reply["description"] = "Reworded by the vendor."
            self._operation(document, "postTransfer")["summary"] = "Reworded summary."

        def new_request_field(document):
            self._request_root(document, "postTransfer")["properties"]["memo"] = {"type": "string"}

        self.assertEqual(SymitarContract(self._edited("transfers", describe)).newer_files, ("transfers",))
        self.assertEqual(SymitarContract(self._edited("transfers", new_request_field)).newer_files, ("transfers",))

    def test_a_relaxed_or_otherwise_changed_reply_stops_even_though_old_replies_still_fit(self):
        def optional(document):
            root = self._reply_root(document, "searchAccountTransactions")
            self.assertTrue(root.get("required"))
            root["required"] = root["required"][1:]

        def nullable(document):
            self._resolve(document, self._reply_root(document, "postTransfer")["properties"]["status"])["nullable"] = True

        def wider_enum(document):
            status = self._resolve(document, self._reply_root(document, "postTransfer")["properties"]["status"])
            status["enum"] = list(status["enum"]) + ["pending-review"]

        def new_reply_field(document):
            paging = self._resolve(document, self._reply_root(document, "searchAccountTransactions")["properties"]["paging"])
            paging["properties"]["previousOffset"] = {"type": "string", "nullable": True}

        for family, edit, operation in (("transactions", optional, "searchAccountTransactions"),
                                        ("transfers", nullable, "postTransfer"),
                                        ("transfers", wider_enum, "postTransfer"),
                                        ("transactions", new_reply_field, "searchAccountTransactions")):
            with self.subTest(edit=edit.__name__):
                self.assert_stops(family, edit,
                                  f"the reply of {operation} changed; review it and record a new version")

    def test_the_reply_digests_match_the_pinned_files(self):
        import yaml
        from contract_inputs import REPLY_SHA256, reply_schema
        found = {}
        for raw in self.raw.values():
            document = yaml.safe_load(raw)
            for methods in document["paths"].values():
                for operation in methods.values():
                    if isinstance(operation, dict) and operation.get("operationId") in OPERATIONS:
                        found[operation["operationId"]] = reply_schema(operation, document)
        self.assertEqual(found, REPLY_SHA256)

    def test_reference_cycles_are_refused_with_a_clear_reason_not_a_hang(self):
        def self_cycle(document):
            document.setdefault("components", {}).setdefault("schemas", {})["Loop"] = {
                "$ref": "#/components/schemas/Loop"}
            self._request_root(document, "postTransfer")["properties"]["amount"] = {"$ref": "#/components/schemas/Loop"}

        def mutual_cycle(document):
            schemas = document.setdefault("components", {}).setdefault("schemas", {})
            schemas["LoopA"] = {"$ref": "#/components/schemas/LoopB"}
            schemas["LoopB"] = {"$ref": "#/components/schemas/LoopA"}
            self._request_root(document, "postTransfer")["properties"]["amount"] = {"$ref": "#/components/schemas/LoopA"}

        for edit in (self_cycle, mutual_cycle):
            with self.subTest(edit=edit.__name__), self.assertRaisesRegex(ContractError, "schema_reference_cycle"):
                SymitarContract(self._edited("transfers", edit))

    def test_a_validator_that_cannot_run_is_could_not_check_never_compatible(self):
        from unittest import mock
        raw = dict(self.raw)
        raw["loans"] += b"\n"
        with mock.patch("recorded_exchanges.EXCHANGES", [("searchLoans", "request", None, None, object())]), \
                mock.patch("contract_inputs.best_match", side_effect=RuntimeError("validator broke")):
            with self.assertRaisesRegex(ContractError, "could_not_check"):
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

    async def test_declared_bodiless_auth_refusal_is_rejected_without_retry(self):
        for status in (401, 403):
            for operation in ("searchLoans", "postTransfer"):
                with self.subTest(status=status, operation=operation):
                    transport = Transport(WireResponse(status, "", b""))
                    await self.assert_code(transport, operation, REQUESTS[operation],
                                           ErrorCode.VENDOR_REJECTED)
                    self.assertEqual(len(transport.requests), 1)

    async def test_body_on_declared_bodiless_response_remains_invalid(self):
        for status in (401, 403):
            for operation, code in (("searchLoans", ErrorCode.INVALID_RESPONSE),
                                    ("postTransfer", ErrorCode.UNKNOWN)):
                with self.subTest(status=status, operation=operation):
                    transport = Transport(WireResponse(status, "application/json", b"{}"))
                    await self.assert_code(transport, operation, REQUESTS[operation], code)
                    self.assertEqual(len(transport.requests), 1)

    async def test_empty_undeclared_or_schema_response_is_not_auth_rejection(self):
        for status in (200, 418):
            with self.subTest(status=status):
                await self.assert_code(Transport(WireResponse(status, "", b"")),
                                       "postTransfer", REQUESTS["postTransfer"], ErrorCode.UNKNOWN)

    async def test_valid_nullable_receipt_is_not_invented(self):
        raw = b'{"status":"success","receiptId":null,"confirmationNumber":null}'
        result = await self.client(Transport(WireResponse(200, "application/json; charset=utf-8", raw))).call(
            "postTransfer", REQUESTS["postTransfer"])
        self.assertIsNone(result.data["receiptId"])
        self.assertNotIn("success", repr(result))


if __name__ == "__main__":
    unittest.main()
