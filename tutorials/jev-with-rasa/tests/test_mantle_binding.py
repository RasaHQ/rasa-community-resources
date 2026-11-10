"""Invoke real decorated Mantle tools against a real loopback worker."""
import importlib.util
import inspect
from http.server import HTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch, AsyncMock
from rasa.shared.core.events import UserUttered
from typesafe_sdk import RetryPolicy, TypeSafeClient
from jacaranda_jev.accounts import Accounts
from jacaranda_jev.scripted import scripted_transport
from jacaranda_jev.selector import MODEL, Selector
from jacaranda_jev.server import handler


class MantleBindings(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        path = Path(__file__).resolve().parents[1] / "mantle/skills/recent_transactions/tools.py"
        spec = importlib.util.spec_from_file_location("jev_mantle_tools", path)
        self.tools = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tools)
        self.accounts = Accounts()
        transport, self.requests = scripted_transport()
        self.client = TypeSafeClient(api_key="scripted-local-test", base_url="https://scripted.invalid",
                                    transport=transport, model=MODEL, retry=RetryPolicy(max_retries=0))
        self.server = HTTPServer(("127.0.0.1", 0), handler(Selector(self.client, self.accounts)))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        original = self.tools.urlopen
        def local(request, **kwargs):
            from urllib.request import Request
            request = Request(f"http://127.0.0.1:{self.server.server_port}{request.full_url.removeprefix("http://127.0.0.1:5029")}", data=request.data,
                              headers=dict(request.headers), method=request.method)
            return original(request, **kwargs)
        self.redirect = patch.object(self.tools, "urlopen", side_effect=local)
        self.redirect.start()
        self.context = patch("rasa.mantle.orchestration.turn_context.current_turn_context",
                             return_value=SimpleNamespace(sender_id="sender-a"))
        self.context.start()
        self.tool_context = SimpleNamespace(events=[UserUttered("Show my current account", timestamp=1)],
                                            send=AsyncMock(), is_cancelled=False)

    async def asyncTearDown(self):
        self.context.stop()
        self.redirect.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.client.close()

    async def test_tool_does_not_offer_owner_or_account_id(self):
        self.assertEqual(set(inspect.signature(self.tools.propose_recent_transactions).parameters), {"context"})
        self.assertEqual(set(inspect.signature(self.tools.read_confirmed_transactions).parameters), {"context"})

    async def test_unbound_sender_is_refused_before_worker(self):
        result = await self.tools.propose_recent_transactions(context=self.tool_context)
        self.assertEqual(result.llm_response, {"status": "needs_demo_code"})
        self.assertEqual(self.requests, [])

    async def test_actual_mantle_tool_reaches_native_sdk_and_read(self):
        await self.tools.select_demo("111111")
        result = await self.tools.propose_recent_transactions(context=self.tool_context)
        self.assertEqual(result.llm_response["status"], "confirmation_requested")
        self.assertEqual(self.accounts.reads, [])
        self.tool_context.send.assert_awaited_once_with("I can read your current account. Shall I use that account?")
        self.tool_context.events.append(UserUttered("yes", timestamp=2))
        read = await self.tools.read_confirmed_transactions(context=self.tool_context)
        self.assertEqual(read.llm_response["status"], "transactions")
        self.assertEqual(self.accounts.reads, ["A-CURRENT"])
        self.assertEqual(len(self.requests), 1)

    async def test_demo_identity_cannot_be_rebound(self):
        await self.tools.select_demo("111111")
        self.assertEqual((await self.tools.select_demo("222222")).llm_response,
                         {"status": "demo_identity_changed"})

    async def test_other_sender_has_no_inherited_binding(self):
        await self.tools.select_demo("111111")
        with patch("rasa.mantle.orchestration.turn_context.current_turn_context",
                   return_value=SimpleNamespace(sender_id="sender-b")):
            self.assertEqual((await self.tools.propose_recent_transactions(context=self.tool_context)).llm_response,
                             {"status": "needs_demo_code"})

    async def test_worker_connection_error_does_not_invent_rows(self):
        from urllib.error import URLError
        await self.tools.select_demo("111111")
        with patch.object(self.tools, "urlopen", side_effect=URLError("scripted offline")):
            self.assertEqual((await self.tools.propose_recent_transactions(context=self.tool_context)).llm_response,
                             {"status": "worker_unavailable"})


    async def test_same_user_event_cannot_confirm_its_own_proposal(self):
        await self.tools.select_demo("111111")
        await self.tools.propose_recent_transactions(context=self.tool_context)
        result = await self.tools.read_confirmed_transactions(context=self.tool_context)
        self.assertEqual(result.llm_response["status"], "needs_confirmation")
        self.assertEqual(self.accounts.reads, [])

    async def test_non_confirmation_does_not_read(self):
        await self.tools.select_demo("111111")
        await self.tools.propose_recent_transactions(context=self.tool_context)
        self.tool_context.events.append(UserUttered("savings instead", timestamp=2))
        result = await self.tools.read_confirmed_transactions(context=self.tool_context)
        self.assertEqual(result.llm_response["status"], "needs_confirmation")
        self.assertEqual(self.accounts.reads, [])

    async def test_actual_no_cancels_without_reading(self):
        await self.tools.select_demo("111111")
        await self.tools.propose_recent_transactions(context=self.tool_context)
        self.tool_context.events.append(UserUttered("no", timestamp=2))
        result = await self.tools.read_confirmed_transactions(context=self.tool_context)
        self.assertEqual(result.llm_response["status"], "proposal_cancelled")
        self.assertEqual(self.accounts.reads, [])

    async def test_interrupted_proposal_is_not_bound_for_confirmation(self):
        await self.tools.select_demo("111111")
        self.tool_context.is_cancelled = True
        result = await self.tools.propose_recent_transactions(context=self.tool_context)
        self.assertEqual(result.llm_response["status"], "interrupted")
        self.assertEqual(self.tools.PROPOSALS, {})
        self.tool_context.send.assert_not_awaited()

    async def test_expiry_cancels_exact_worker_token_and_later_confirm_is_refused(self):
        await self.tools.select_demo("111111")
        await self.tools.propose_recent_transactions(context=self.tool_context)
        key = self.tools.sender()
        token, owner, _ = self.tools.PROPOSALS[key]
        body = {"owner": owner, "conversation": key, "token": token}
        self.tool_context.events.extend([UserUttered("support instead", timestamp=2),
                                        UserUttered("Yes", timestamp=3)])
        calls = []
        native = self.tools.request_worker
        def record(path, payload):
            calls.append((path, dict(payload)))
            return native(path, payload)
        with patch.object(self.tools, "request_worker", side_effect=record):
            result = await self.tools.read_confirmed_transactions(context=self.tool_context)
        self.assertEqual(result.llm_response["status"], "proposal_expired")
        self.assertEqual(calls, [("/cancel", body)])
        self.assertNotIn(key, self.tools.PROPOSALS)
        # Actual HTTP confirmation reaches the same worker with the exact token.
        self.assertEqual(native("/confirm", body)["status"], "proposal_changed")
        self.assertEqual(self.accounts.reads, [])
        self.assertEqual(len(self.requests), 1)

    async def test_lost_cancel_removes_local_copy_but_worker_token_remains(self):
        await self.tools.select_demo("111111")
        await self.tools.propose_recent_transactions(context=self.tool_context)
        key = self.tools.sender()
        token, owner, _ = self.tools.PROPOSALS[key]
        self.tool_context.events.extend([UserUttered("support instead", timestamp=2),
                                        UserUttered("Yes", timestamp=3)])
        with patch.object(self.tools, "request_worker", return_value={"status": "worker_unavailable"}) as failed:
            result = await self.tools.read_confirmed_transactions(context=self.tool_context)
        self.assertEqual(result.llm_response["status"], "proposal_expired")
        failed.assert_called_once_with("/cancel", {"owner": owner, "conversation": key, "token": token})
        self.assertNotIn(key, self.tools.PROPOSALS)
        self.assertEqual(self.accounts.reads, [])
        # Native worker still holds it. Explicitly cancel it for fixture cleanup.
        body = {"owner": owner, "conversation": key, "token": token}
        self.assertEqual(self.tools.request_worker("/cancel", body)["status"], "proposal_cancelled")
        self.assertEqual(self.tools.request_worker("/confirm", body)["status"], "proposal_changed")

if __name__ == "__main__":
    unittest.main()
