"""Host, guard, journal, fault-mapping, server and adapter tests that run in CI without the archive."""
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from decimal import Decimal

import httpx
from starlette.testclient import TestClient

from journal import Journal
from silverlake_demo import client as client_module
from silverlake_demo.contract import NS, SOAP_ENV
from silverlake_demo.permissions import PERMISSIONS
from silverlake_demo.server import TOOLS, create_app
from silverlake_demo.service import SilverLakeService
from tests import test_service
from tests.fakes import FakeClient, FakeFixture


class ServiceWithoutArchive(test_service.ServiceTests):
    @classmethod
    def setUpClass(cls):
        cls.contract = None

    def build(self, fault="none"):
        original = test_service.Fixture
        test_service.Fixture = FakeFixture
        try:
            return super().build(fault)
        finally:
            test_service.Fixture = original


class StubContract:
    actions = {"XferAdd": "http://jackhenry.com/ws/XferAdd"}

    def validate(self, element):
        pass


def fault_reply(side, code=None):
    env = ET.Element("{%s}Envelope" % SOAP_ENV)
    body = ET.SubElement(env, "{%s}Body" % SOAP_ENV)
    fault = ET.SubElement(body, "{%s}Fault" % SOAP_ENV)
    ET.SubElement(fault, "faultcode").text = "soap:" + side
    ET.SubElement(fault, "faultstring").text = "x"
    if code:
        ET.SubElement(ET.SubElement(fault, "detail"), "{%s}ErrCode" % NS).text = code
    return httpx.Response(500, content=ET.tostring(env))


class TransferFaultMapping(unittest.TestCase):
    def client(self, reply):
        return client_module.SilverLakeClient(StubContract(), "http://127.0.0.1:9", transport=httpx.MockTransport(
            lambda request: reply))

    def test_only_client_faults_and_listed_business_codes_are_refusals(self):
        args = (("1", "D"), ("2", "S"), Decimal("5"))
        self.assertEqual(self.client(fault_reply("Client")).transfer(*args), "refused")
        self.assertEqual(self.client(fault_reply("Server", "100199")).transfer(*args), "refused")
        for reply in (fault_reply("Server"), fault_reply("Server", "999999"), httpx.Response(200, content=b"<x/>")):
            with self.assertRaises(client_module.UnknownOutcome):
                self.client(reply).transfer(*args)


class ServerHttp(unittest.TestCase):
    CAPABILITY = "c" * 40
    MCP = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        journal = Journal(Path(folder.name) / "journal", "silverlake-mock", initialize=True)
        self.addCleanup(journal.close)
        self.double = FakeClient()
        service = SilverLakeService(self.double, journal, PERMISSIONS)
        self.http = TestClient(create_app(service, self.CAPABILITY), base_url="http://127.0.0.1:8000")
        self.http.__enter__()
        self.addCleanup(self.http.__exit__, None, None, None)

    def credential(self):
        reply = self.http.post("/host/open", json={"caller": "demo-A"},
                               headers={"Authorization": "Bearer " + self.CAPABILITY})
        self.assertEqual(reply.status_code, 200)
        return reply.json()["credential"]

    def rpc(self, credential, method, params):
        return self.http.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                              headers={**self.MCP, "Authorization": "Bearer " + credential})

    def test_host_routes_and_mcp_need_their_own_credentials(self):
        self.assertEqual(self.http.post("/host/open", json={"caller": "demo-A"}).status_code, 401)
        reply = self.http.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                               headers=self.MCP)
        self.assertEqual(reply.status_code, 401)

    def test_discovery_is_exactly_seven_tools_and_extra_arguments_are_refused(self):
        credential = self.credential()
        tools = self.rpc(credential, "tools/list", {}).json()["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, set(TOOLS))
        self.assertEqual(len(tools), 7)
        reply = self.rpc(credential, "tools/call", {"name": "banking_balance",
                                                    "arguments": {"account": "checking-A", "verified": True}})
        self.assertEqual(reply.json()["error"]["code"], -32602)

    def test_review_arm_and_send_once_through_host_routes(self):
        credential = self.credential()
        review = self.rpc(credential, "tools/call", {"name": "banking_review_transfer", "arguments": {
            "source": "checking-A", "destination": "savings-A", "amount": "5", "currency": "USD"}})
        draft = review.json()["result"]["structuredContent"]["review"]
        host = {"Authorization": "Bearer " + self.CAPABILITY}
        self.assertEqual(self.http.post("/host/arm", headers=host, json={
            "credential": credential, "review": draft, "turn": 3}).status_code, 200)
        sent = self.http.post("/host/send", headers=host, json={
            "credential": credential, "utterance": "Confirm transfer.", "turn": 4})
        self.assertEqual(sent.json()["state"], "accepted")
        again = self.http.post("/host/send", headers=host, json={
            "credential": credential, "utterance": "confirm transfer", "turn": 5})
        self.assertEqual(again.status_code, 403)
        self.assertEqual(self.double.mock.transfers, 1)


class AdapterHelpers(unittest.TestCase):
    def test_confirmation_reset_and_redaction(self):
        from silverlake_demo import rasa_adapter as adapter
        self.assertTrue(adapter._is_confirmation("Confirm transfer."))
        self.assertFalse(adapter._is_confirmation("confirm the transfer"))
        self.assertTrue(adapter._is_reset("Log out."))
        self.assertTrue(adapter._is_assure("Verify me."))
        safe = adapter._safe({"state": "pending", "review": "handle", "credential": "x", "say": "s"})
        self.assertEqual(safe, {"state": "pending", "say": "s"})


if __name__ == "__main__":
    unittest.main()


class AdapterAssuranceTime(unittest.IsolatedAsyncioTestCase):
    """A 'verify me' turn that called no tool must not become a fresh grant later."""

    async def test_a_stale_phrase_is_passed_with_its_real_age(self):
        import os
        import time
        from types import SimpleNamespace
        from unittest import mock
        from silverlake_demo import rasa_adapter as adapter

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
        environ = {"SILVERLAKE_HOST_URL": "http://127.0.0.1:1", "SILVERLAKE_HOST_CAPABILITY": "c" * 40}
        with mock.patch.dict(os.environ, environ), \
                mock.patch("silverlake_demo.hostclient.HostClient", FakeHost), \
                mock.patch.object(adapter, "current_turn_context", lambda: turn):
            adapter._conversations.clear()
            first = SimpleNamespace(events=[event("hello", now - 400)])
            await adapter._host(first)  # opens the conversation; nothing to assure
            later = SimpleNamespace(events=[event("hello", now - 400), event("verify me", now - 301),
                                            event("what is my balance", now)])
            await adapter._host(later)
        self.assertEqual(len(calls), 1)
        self.assertGreaterEqual(calls[0], 301)  # the host gets the real age, so no fresh grant
        adapter._conversations.clear()
