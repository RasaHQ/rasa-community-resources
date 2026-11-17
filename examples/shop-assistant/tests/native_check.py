"""Actual locked framework/protocol checks; synthetic inputs and no providers."""
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from shop_demo.mcp_client import ShopClient
from shop_demo.models import Basket, BasketItem

PROJECT = Path(__file__).resolve().parent.parent


class NativeChecks(unittest.IsolatedAsyncioTestCase):
    async def test_operator_product_question_reaches_catalog_through_native_rasa(self):
        from datetime import datetime, timezone
        from shop_demo.assistant import Assistant
        from shop_demo.conversation import Incoming
        from shop_demo.models import Product
        from shop_demo.operations import Catalog

        class CatalogClient:
            calls = 0

            async def catalog(self):
                self.calls += 1
                return Catalog(currency="MXN", products=(
                    Product(code="NOTEBOOK", name="Notebook", price_cents=12900, stock=12),))

        completions = []
        selected_tools = []

        async def complete(*args, **kwargs):
            completions.append(kwargs)
            functions = {tool["function"]["name"]: tool["function"]
                         for tool in kwargs["tools"]}
            question_present = "What products are available?" in json.dumps(kwargs["messages"])
            if "record_discovered_facts" in functions:
                # Rasa's post-turn memory pass has no configured fields here.
                name, arguments = "record_discovered_facts", "{}"
            elif not question_present:
                # The native session-start turn precedes the user's question.
                name, arguments = "listen", "{}"
            elif "product_catalog" not in functions:
                name, arguments = "activate", '{"target_id":"shopping"}'
            elif "product_catalog" not in selected_tools:
                name, arguments = "product_catalog", "{}"
            else:
                name, arguments = "listen", "{}"
            self.assertIn(name, functions)
            selected_tools.append(name)
            return ModelResponse(model="gpt-4o-mini", choices=[{
                "index": 0, "finish_reason": "tool_calls",
                "message": {"role": "assistant", "content": None, "tool_calls": [{
                    "id": f"synthetic-{len(completions)}", "type": "function",
                    "function": {"name": name, "arguments": arguments}}]}}])

        client = CatalogClient()
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-never-a-real-key",
                "RASA_TELEMETRY_ENABLED": "false", "LITELLM_LOCAL_MODEL_COST_MAP": "True"}), \
                    patch.object(socket.socket, "connect", side_effect=AssertionError("No network in native catalog control")), \
                    patch("rasa.utils.licensing.validate_license_from_env"), \
                    patch("rasa.shared.providers.llm._base_litellm_client.acompletion", side_effect=complete):
                from litellm import ModelResponse
                async with Assistant(client, project=PROJECT, state_directory=Path(directory),
                        clock=lambda: now) as assistant:
                    answer = await assistant.respond(Incoming(update_id=1, message_id=1,
                        chat_id=7, date=int(now.timestamp()), text="What products are available?"), None)
        self.assertEqual(client.calls, 1)
        self.assertIn("NOTEBOOK: Notebook, MXN 129.00", answer)
        self.assertIn("activate", selected_tools)
        self.assertEqual(selected_tools.count("product_catalog"), 1)
        self.assertLessEqual(len(completions), 5)
        functions = {tool["function"]["name"]: tool["function"]
                     for request in completions for tool in request["tools"]}
        for name in ("product_catalog", "price_basket", "order_progress", "ask_basket_details"):
            self.assertNotIn("context", functions[name]["parameters"].get("properties", {}))

    async def test_owned_agent_process_exits_within_five_seconds_after_close(self):
        from child_exit_control import require_process_exit
        code, transcript = await require_process_exit([sys.executable, '-B',
            str(PROJECT / 'tests/agent_exit_check.py')], cwd=PROJECT)
        self.assertEqual(code, 0, transcript)

    async def test_invalid_token_stops_before_mcp_without_printing_secret(self):
        from pydantic import SecretStr
        from shop_demo.launcher import StartupConfigurationError, telegram_client
        secret = "synthetic-malformed-token-never-print"
        with patch.object(socket.socket, "connect", side_effect=AssertionError("No request for an invalid token")):
            with self.assertRaises(StartupConfigurationError) as caught:
                telegram_client(SecretStr(secret))
        self.assertIn("TELEGRAM_BOT_TOKEN", str(caught.exception))
        self.assertIn("BotFather", str(caught.exception))
        self.assertNotIn(secret, str(caught.exception))

    async def test_installed_telegram_contract_preserves_updates_and_send_receipts(self):
        import httpx
        from pydantic import SecretStr
        from zeo_integrations.telegram.direct import TelegramClient
        from shop_demo.conversation import Conversation
        from datetime import datetime, timezone
        import tomllib

        configured = tomllib.loads((PROJECT / "pyproject.toml").read_text())["project"]["dependencies"]
        pin = next(value for value in configured if value.startswith("zeo-integrations @")).rsplit("@", 1)[1]
        installed = json.loads(importlib.metadata.distribution("zeo-integrations").read_text("direct_url.json"))
        self.assertEqual(installed["vcs_info"]["commit_id"], pin)
        original = {"update_id": 7, "message": {"message_id": 1, "date": 1,
            "chat": {"id": 7, "type": "private"},
            "from": {"id": 7, "is_bot": False, "first_name": "Synthetic"}, "text": "catalog"}}
        unsupported = {"update_id": 8, "message": {"chat": "malformed"}}
        calls = []

        def transport(request):
            method = request.url.path.rsplit("/", 1)[1]
            calls.append(method)
            if method == "getUpdates":
                return httpx.Response(200, json={"ok": True, "result": [original, unsupported]})
            self.assertEqual(method, "sendMessage")
            payload = json.loads(request.content)
            return httpx.Response(200, json={"ok": True, "result": {
                "message_id": 2, "date": 2, "chat": {"id": payload["chat_id"], "type": "private"},
                "text": payload["text"]}})

        with tempfile.TemporaryDirectory() as directory:
            async with TelegramClient(SecretStr("1:" + "synthetic_" * 3),
                    transport=httpx.MockTransport(transport)) as telegram:
                updates = await telegram.get_updates(offset=None, limit=20, timeout=10)
                self.assertEqual(updates[0].raw_payload, original)
                self.assertEqual(updates[1].raw_payload, unsupported)
                self.assertEqual(updates[1].unsupported_reason, "invalid_message")
                conversation = Conversation(Path(directory) / "conversation.sqlite3", chat_id=7,
                    telegram=telegram, assistant=object(), orders=object(),
                    clock=lambda: datetime.now(timezone.utc))
                try:
                    conversation.retain([update.raw_payload for update in updates])
                    sent = await conversation.send("installed-contract", "Synthetic reply")
                    self.assertEqual((sent.message_id, sent.chat_id, sent.date, sent.text),
                                     (2, 7, 2, "Synthetic reply"))
                    self.assertEqual(await conversation.send("installed-contract", "Synthetic reply"), sent)
                    self.assertEqual(conversation.offset(), 9)
                    self.assertEqual(calls, ["getUpdates", "sendMessage"])
                finally:
                    conversation.close()

    async def test_installed_telegram_cancellation_leaves_send_held_without_retry(self):
        import httpx
        from pydantic import SecretStr
        from zeo_integrations.telegram.direct import TelegramClient
        from shop_demo.conversation import Conversation
        from datetime import datetime, timezone

        started = asyncio.Event()
        calls = []

        async def transport(request):
            calls.append(request.url.path.rsplit("/", 1)[1])
            started.set()
            await asyncio.Event().wait()

        with tempfile.TemporaryDirectory() as directory:
            async with TelegramClient(SecretStr("1:" + "synthetic_" * 3),
                    transport=httpx.MockTransport(transport)) as telegram:
                conversation = Conversation(Path(directory) / "conversation.sqlite3", chat_id=7,
                    telegram=telegram, assistant=object(), orders=object(),
                    clock=lambda: datetime.now(timezone.utc))
                try:
                    task = asyncio.create_task(conversation.send("cancel-contract", "Synthetic reply"))
                    await asyncio.wait_for(started.wait(), timeout=2)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    self.assertEqual(conversation.db.execute(
                        "SELECT receipt FROM outgoing WHERE key='cancel-contract'").fetchone(), (None,))
                    self.assertEqual(calls, ["sendMessage"])
                finally:
                    conversation.close()

    async def test_native_processor_load_and_close_without_conversation(self):
        from datetime import datetime, timezone
        from shop_demo.assistant import Assistant
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-never-a-real-key",
                "RASA_TELEMETRY_ENABLED": "false"}), patch("rasa.utils.licensing.validate_license_from_env"), \
                patch.object(socket.socket, "connect", side_effect=AssertionError("No network during native load")):
                async with Assistant(object(), project=PROJECT, state_directory=Path(directory),
                    clock=lambda: datetime.now(timezone.utc)) as assistant:
                    self.assertIsNotNone(assistant.agent)
                    manager = assistant.agent.privacy_manager
                if manager is not None:
                    self.assertFalse(manager.can_consume_from_tracker_queue)
                    self.assertFalse(manager.background_scheduler.running)
                self.assertIsNone(assistant.agent)

    async def test_mcp1_client_calls_mcp2_core_server_and_replays_original(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {"PATH": os.environ["PATH"], "SHOP_TEST_STATE": directory,
                   "PYTHONPATH": str(PROJECT) + os.pathsep + str(PROJECT / "tests")}
            async with ShopClient(os.environ["SHOP_TEST_SERVER_PYTHON"],
                arguments=["-B", str(PROJECT / "tests/mcp_fixture.py")],
                environment=env, directory=PROJECT) as client:
                catalog = await client.catalog()
                self.assertEqual(catalog.currency, "MXN")
                self.assertEqual(catalog.products[0].code, "NOTEBOOK")
                quote = await client.quote(Basket(items=(BasketItem(code="NOTEBOOK", quantity=2),)))
                self.assertEqual(quote.total_cents, 25800)
                placed = await client.place(quote.reference, "protocol-test:1")
                self.assertEqual(await client.place(quote.reference, "protocol-test:1"), placed)
                self.assertEqual(await client.lookup(str(placed.number)), placed)
                catalog = await client.catalog()
                self.assertEqual(catalog.products[0].stock, 10)

    async def test_native_archive_validates_skill_without_embedding_environment_key(self):
        from rasa.mantle.model_archive.snapshot import package_model_archive
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-never-a-real-key",
                "RASA_TELEMETRY_ENABLED": "false"}), patch.object(socket.socket, "connect",
                    side_effect=AssertionError("No network during the archive check")):
                result = package_model_archive(str(PROJECT / "agent.yml"), directory,
                    fixed_model_name="shop-test", validate=True)
            self.assertEqual(result.code, 0)
            with tarfile.open(result.model) as archive:
                members = [m for m in archive.getmembers() if m.isfile()]
                payloads = {m.name: archive.extractfile(m).read() for m in members}
            self.assertTrue(any("skills/shopping/skill.md" in name for name in payloads))
            self.assertTrue(any("skills/shopping/tools.py" in name for name in payloads))
            self.assertTrue(any(b"${OPENAI_API_KEY}" in data for data in payloads.values()))
            self.assertFalse(any(b"synthetic-never-a-real-key" in data for data in payloads.values()))


if __name__ == "__main__":
    unittest.main()
