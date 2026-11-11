"""Real loopback MCP capability transport; not native Rasa/user authentication."""

import asyncio
import json
import os
from pathlib import Path
from secrets import token_urlsafe
import socket
import subprocess
import sys
import tempfile
import time
import unittest

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from banking_demo.client import HostClient


class Transport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logs = tempfile.TemporaryFile()
        cls.capability = token_urlsafe(32)
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            cls.port = reservation.getsockname()[1]
        cls.url = f"http://127.0.0.1:{cls.port}"
        # No inherited provider/production keys; only a fresh local test capability.
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG"}}
        env.update(BANKING_HOST_CAPABILITY=cls.capability, PYTHONDONTWRITEBYTECODE="1",
                   PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        cls.child = subprocess.Popen(
            [sys.executable, "-m", "banking_demo.server", "--profile", "jack-henry",
             "--port", str(cls.port), "--domain-fixture"],
            env=env, stdout=cls.logs, stderr=cls.logs,
        )
        deadline = time.monotonic() + 15
        while cls.child.poll() is None:
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=.2):
                    cls.host = HostClient(cls.url, cls.capability)
                    return
            except OSError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(.05)
        cls.child.terminate()
        cls.child.wait(timeout=10)
        cls.logs.seek(0)
        raise AssertionError("owned MCP process failed readiness: " + cls.logs.read().decode())

    @classmethod
    def tearDownClass(cls):
        if cls.child.poll() is None:
            cls.child.terminate()
        cls.child.wait(timeout=10)
        cls.logs.close()

    def call(self, session, tool, args):
        result = asyncio.run(self.host.call(session, tool, args))
        self.assertFalse(result.isError)
        value = result.structuredContent
        if value is None:
            value = json.loads(result.content[0].text)
        return value

    def review(self, session):
        return self.call(session, "banking_review_transfer", {
            "source": "checking-A", "destination": "savings-A",
            "amount": "10.00", "currency": "USD",
        })

    def test_host_control_refuses_without_private_capability(self):
        for token in ("", "wrong-capability"):
            response = httpx.post(self.url + "/host/open", json={"caller": "demo-A"},
                                  headers={"Authorization": "Bearer " + token}, trust_env=False)
            self.assertEqual(response.status_code, 401)
            self.assertNotIn(self.capability, response.text)

    def test_mcp_refuses_unbound_credential(self):
        response = httpx.post(self.url + "/mcp", json={}, trust_env=False)
        self.assertEqual(response.status_code, 401)

    def test_actual_mcp_tool_schemas_exclude_host_proof_fields(self):
        session = self.host.open_session()

        async def tools():
            async with streamablehttp_client(
                self.url + "/mcp", headers={"Authorization": "Bearer " + session.credential}
            ) as streams:
                async with ClientSession(streams[0], streams[1]) as client:
                    await client.initialize()
                    return await client.list_tools()

        actual = asyncio.run(tools())
        self.assertEqual(len(actual.tools), 8)
        self.assertFalse({"confirm", "reset", "open_session", "cancel"} & {t.name for t in actual.tools})
        for tool in actual.tools:
            self.assertFalse({"principal", "session", "verified", "confirmed", "credential"}
                             & set(tool.inputSchema.get("properties", {})))

    def test_reads_resolve_credential_and_keep_other_account_private(self):
        a, b = self.host.open_session(), self.host.open_session("demo-B")
        self.assertNotEqual(a.credential, b.credential)
        self.assertNotIn(a.credential, repr(a))
        self.assertEqual(self.call(a, "banking_balance", {"account": "checking-A"})["state"], "supplied")
        denied = self.call(b, "banking_balance", {"account": "checking-A"})
        self.assertEqual(denied, {"state": "refused", "reason": "account_unavailable"})

    def test_mcp_cannot_confirm_but_host_can_bind_exact_review(self):
        session = self.host.open_session()
        review = self.review(session)
        pending = self.call(session, "banking_submit_transfer", {"review": review["review"]})
        self.assertEqual(pending["reason"], "confirmation_required")
        fields = {k: review[k] for k in ("source", "destination", "amount", "currency")}
        self.host.confirm(session, review["review"], fields)
        outcome = self.call(session, "banking_submit_transfer", {"review": review["review"]})
        self.assertEqual(outcome["state"], "queued")
        self.assertEqual(self.call(session, "banking_submit_transfer", {"review": review["review"]}), outcome)

    def test_different_credential_cannot_read_or_submit_review(self):
        a, b = self.host.open_session(), self.host.open_session()
        review = self.review(a)
        for tool in ("banking_transfer_status", "banking_submit_transfer"):
            self.assertEqual(self.call(b, tool, {"review": review["review"]})["reason"], "review_unavailable")

    def test_cancel_over_host_interface_keeps_mcp_submit_closed(self):
        session = self.host.open_session()
        review = self.review(session)
        self.host.cancel(session, review["review"])
        self.assertEqual(self.call(session, "banking_submit_transfer", {"review": review["review"]})["reason"],
                         "confirmation_required")

    def test_reset_revokes_transport_credential(self):
        session = self.host.open_session()
        self.host.reset(session)
        response = httpx.post(self.url + "/mcp", json={}, trust_env=False,
                              headers={"Authorization": "Bearer " + session.credential})
        self.assertEqual(response.status_code, 401)

    def test_host_admin_token_is_not_a_model_session_credential(self):
        response = httpx.post(self.url + "/mcp", json={}, trust_env=False,
                              headers={"Authorization": "Bearer " + self.capability})
        self.assertEqual(response.status_code, 401)

    def test_host_client_refuses_non_loopback_or_credential_bearing_urls(self):
        for url in ("https://example.com", "http://localhost:9000", "http://user:pass@127.0.0.1:9000",
                    "http://127.0.0.1:9000/?secret=x", "http://127.0.0.1:9000/elsewhere"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                HostClient(url, self.capability)


if __name__ == "__main__":
    unittest.main()
