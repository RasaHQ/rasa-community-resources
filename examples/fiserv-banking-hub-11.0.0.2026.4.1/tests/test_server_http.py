"""HTTP tests of the naked MCP server and its private host routes. Vendor-free; run in CI."""
from pathlib import Path
import tempfile
import unittest

from starlette.testclient import TestClient

from bh_demo.host import Journal, BankingHubService, UNSOURCED
from bh_demo.permissions import PERMISSIONS
from bh_demo.server import TOOLS, create_app
from tests.fakes import FakeClient

CAPABILITY = "c" * 40
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


class ServerHttp(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.journal = Journal(Path(folder.name) / "journal.sqlite3")
        self.addCleanup(self.journal.close)
        self.client_double = FakeClient()
        service = BankingHubService(self.client_double, self.journal, PERMISSIONS)
        self.http = TestClient(create_app(service, CAPABILITY), base_url="http://127.0.0.1:8000")
        self.http.__enter__()
        self.addCleanup(self.http.__exit__, None, None, None)

    def credential(self):
        reply = self.http.post("/host/open", json={"caller": "demo-A"},
                               headers={"Authorization": "Bearer " + CAPABILITY})
        self.assertEqual(reply.status_code, 200)
        return reply.json()["credential"]

    def rpc(self, credential, method, params, ident=1):
        return self.http.post("/mcp", json={"jsonrpc": "2.0", "id": ident, "method": method, "params": params},
                              headers={**MCP_HEADERS, "Authorization": "Bearer " + credential})

    def test_host_routes_need_the_host_capability(self):
        self.assertEqual(self.http.post("/host/open", json={"caller": "demo-A"}).status_code, 401)
        self.assertEqual(self.http.post("/host/open", json={"caller": "demo-A"},
                                        headers={"Authorization": "Bearer wrong"}).status_code, 401)
        self.credential()

    def test_mcp_needs_a_session_credential(self):
        reply = self.http.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                               headers=MCP_HEADERS)
        self.assertEqual(reply.status_code, 401)

    def test_discovery_is_exactly_seven_tools_without_identity_arguments(self):
        reply = self.rpc(self.credential(), "tools/list", {})
        self.assertEqual(reply.status_code, 200, reply.text[:300])
        tools = reply.json()["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, set(TOOLS))
        self.assertEqual(len(tools), 7)
        for tool in tools:
            fields = set(tool["inputSchema"].get("properties", {}))
            self.assertFalse(fields & {"session", "principal", "credential", "review", "confirmed", "verified"})

    def test_raw_arguments_are_checked_before_the_sdk(self):
        credential = self.credential()
        reply = self.rpc(credential, "tools/call", {"name": "banking_balance",
                                                    "arguments": {"account": "DDA-A", "verified": True}})
        self.assertEqual(reply.json()["error"]["code"], -32602)
        reply = self.rpc(credential, "tools/call", {"name": "banking_submit_transfer", "arguments": {}})
        self.assertEqual(reply.json()["error"]["code"], -32602)

    def test_a_tool_call_returns_only_permitted_aliases(self):
        reply = self.rpc(self.credential(), "tools/call", {"name": "banking_accounts", "arguments": {}})
        self.assertEqual(reply.status_code, 200, reply.text[:300])
        self.assertEqual(reply.json()["result"]["structuredContent"]["accounts"],
                         ["DDA-A", "LOAN-A", "SDA-A"])

    def test_an_unsourced_fact_answers_unavailable_over_mcp(self):
        reply = self.rpc(self.credential(), "tools/call", {"name": "banking_history",
                                                           "arguments": {"account": "DDA-A"}})
        self.assertEqual(reply.json()["result"]["structuredContent"],
                         {"state": "unavailable", "reason": UNSOURCED["history"]})

    def test_confirm_and_submit_are_host_only_and_send_once(self):
        credential = self.credential()
        review = self.rpc(credential, "tools/call", {"name": "banking_review_transfer", "arguments": {
            "source": "DDA-A", "destination": "SDA-A", "amount": "5", "currency": "USD"}})
        result = review.json()["result"]["structuredContent"]
        headers = {"Authorization": "Bearer " + CAPABILITY}
        exact = {key: result[key] for key in ("source", "destination", "amount", "currency")}
        self.assertEqual(self.http.post("/host/confirm", headers=headers, json={
            "credential": credential, "review": result["review"], "transfer": exact}).status_code, 200)
        sent = self.http.post("/host/submit", headers=headers, json={"credential": credential, "review": result["review"]})
        self.assertEqual(sent.json()["state"], "accepted")
        again = self.http.post("/host/submit", headers=headers, json={"credential": credential, "review": result["review"]})
        self.assertEqual(again.status_code, 403)
        self.assertEqual(self.client_double.mock.transfers, 1)


class AdapterHelpers(unittest.TestCase):
    def test_confirmation_reset_and_redaction(self):
        from bh_demo import rasa_adapter as adapter
        for text in ("confirm transfer", "Confirm transfer.", "  CONFIRM  TRANSFER! "):
            self.assertTrue(adapter._is_confirmation(text))
        for text in ("yes", "confirm the transfer", "confirm transfer please", "no"):
            self.assertFalse(adapter._is_confirmation(text))
        self.assertTrue(adapter._is_reset("Log out."))
        safe = adapter._safe({"state": "pending", "review": "secret-handle", "credential": "x", "amount": "5.00"})
        self.assertEqual(safe, {"state": "pending", "amount": "5.00"})


if __name__ == "__main__":
    unittest.main()


class AdapterAssuranceTime(unittest.IsolatedAsyncioTestCase):
    """A 'verify me' turn that called no tool must not become a fresh grant later."""

    async def test_a_stale_phrase_is_passed_with_its_real_age(self):
        import os
        import time
        from types import SimpleNamespace
        from unittest import mock
        from bh_demo import rasa_adapter as adapter

        calls = []

        class FakeHost:
            def __init__(self, origin, capability):
                pass

            def open_session(self, caller):
                return "session"

            def assure(self, session, age):
                calls.append(age)

        def event(text, stamp):
            return SimpleNamespace(as_dict=lambda: {"event": "user", "text": text, "timestamp": stamp})

        now = time.time()
        turn = SimpleNamespace(sender_id="caller-1", turn=SimpleNamespace(text="what is my balance"))
        environ = {"BANKINGHUB_HOST_URL": "http://127.0.0.1:1", "BANKINGHUB_HOST_CAPABILITY": "c" * 40}
        with mock.patch.dict(os.environ, environ), \
                mock.patch("bh_demo.hostclient.HostClient", FakeHost), \
                mock.patch.object(adapter, "current_turn_context", lambda: turn):
            adapter._conversations.clear()
            await adapter._host(SimpleNamespace(events=[event("hello", now - 400)]))
            await adapter._host(SimpleNamespace(events=[event("hello", now - 400), event("verify me", now - 301),
                                                        event("what is my balance", now)]))
        self.assertEqual(len(calls), 1)
        self.assertGreaterEqual(calls[0], 301)
        adapter._conversations.clear()
