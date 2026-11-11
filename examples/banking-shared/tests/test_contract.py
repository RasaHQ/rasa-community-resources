"""Our two shared-contract mocks, not vendor-wire conformance or native Rasa."""

import json
from secrets import token_urlsafe
import unittest

from jsonschema import Draft202012Validator
from starlette.testclient import TestClient

from banking_demo.contract import CONTRACT, validate
from banking_demo.server import create_app


class Contract(unittest.TestCase):
    def test_all_eight_input_output_schemas_are_valid_and_closed(self):
        self.assertEqual(CONTRACT["version"], "1.0.0")
        self.assertEqual(len(CONTRACT["tools"]), 8)
        for tool in CONTRACT["tools"].values():
            for direction in ("input", "output"):
                Draft202012Validator.check_schema(tool[direction])
                self.assertFalse(tool[direction]["additionalProperties"])

    def exercise(self, profile, *, fault="none"):
        capability = token_urlsafe(32)
        client = TestClient(create_app(profile, capability, fault=fault),
                            base_url="http://127.0.0.1:8940")
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        host_headers = {"Authorization": "Bearer " + capability}

        def open_session():
            response = client.post("/host/open", json={"caller": "demo-A"}, headers=host_headers)
            self.assertEqual(response.status_code, 200)
            return response.json()["credential"]

        credential = open_session()
        headers = {"Authorization": "Bearer " + credential,
                   "Accept": "application/json, text/event-stream"}
        response = client.post("/mcp", headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "our-contract-control", "version": "1.0"},
            },
        })
        self.assertEqual(response.status_code, 200)
        sequence = 1

        def call(tool, arguments):
            nonlocal sequence
            validate(tool, "input", arguments)
            sequence += 1
            response = client.post("/mcp", headers=headers, json={
                "jsonrpc": "2.0", "id": sequence, "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            })
            self.assertEqual(response.status_code, 200)
            result = response.json()["result"]
            self.assertFalse(result.get("isError", False), result)
            value = result.get("structuredContent")
            if value is None:
                value = json.loads(result["content"][0]["text"])
            validate(tool, "output", value)
            self.assertNotIn(credential, json.dumps(value))
            self.assertNotIn(capability, json.dumps(value))
            self.assertEqual(value["profile"], profile)
            return value

        accounts = call("banking_accounts", {})
        self.assertEqual(accounts["accounts"], ["checking-A", "loan-A", "savings-A"])
        for kind in ("available", "ledger"):
            result = call("banking_balance", {"account": "checking-A", "balance_type": kind})
            self.assertEqual(result["state"], "supplied")
            self.assertEqual(result["balance_type"], kind)
        first = call("banking_history", {"account": "checking-A", "page": 1})
        second = call("banking_history", {"account": "checking-A", "page": 2})
        self.assertTrue(first["more"])
        self.assertFalse(second["more"])
        self.assertNotEqual(first["entries"], second["entries"])
        payment = call("banking_loan_payment", {"account": "loan-A"})
        self.assertEqual(payment["due_date"], "2026-01-20")
        quote = call("banking_payoff", {"account": "loan-A", "date": "2026-01-15"})
        self.assertEqual(quote["as_of"], "2026-01-15")
        self.assertEqual(call("banking_payoff", {"account": "loan-A", "date": "2026-01-16"})["state"],
                         "unsupported")
        self.assertEqual(call("banking_balance", {"account": "checking-B"})["reason"], "account_unavailable")
        self.assertEqual(call("banking_review_transfer", {
            "source": "loan-A", "destination": "checking-A", "amount": "10.00", "currency": "USD"
        })["reason"], "unsupported_transfer")
        review = call("banking_review_transfer", {
            "source": "checking-A", "destination": "savings-A", "amount": "10.00", "currency": "USD"
        })
        identifier = review["review"]
        self.assertEqual(call("banking_submit_transfer", {"review": identifier})["reason"], "confirmation_required")
        confirmation = client.post("/host/confirm", headers=host_headers, json={
            "credential": credential, "review": identifier,
            "transfer": {k: review[k] for k in ("source", "destination", "amount", "currency")},
        })
        self.assertEqual(confirmation.status_code, 200)
        outcome = call("banking_submit_transfer", {"review": identifier})
        expected = "unknown" if fault != "none" else ("queued" if profile == "jack-henry" else "accepted")
        self.assertEqual(outcome["state"], expected)
        self.assertEqual(call("banking_submit_transfer", {"review": identifier}), outcome)
        self.assertEqual(call("banking_transfer_status", {"review": identifier}), outcome)
        if fault != "none":
            self.assertEqual(call("banking_review_transfer", {
                "source": "checking-A", "destination": "savings-A", "amount": "10.00", "currency": "USD"
            })["reason"], "outcome_unresolved")

    def test_jack_henry_configuration_conforms_to_our_eight_actions(self):
        self.exercise("jack-henry")

    def test_fiserv_configuration_conforms_to_our_eight_actions(self):
        self.exercise("fiserv")

    def test_our_lost_response_fault_stays_unknown_without_retry(self):
        self.exercise("jack-henry", fault="transfer-response-lost")


if __name__ == "__main__":
    unittest.main()
