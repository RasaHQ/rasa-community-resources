"""Actual locked framework/protocol checks; synthetic inputs and no providers."""
import os
from pathlib import Path
import socket
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from shop_demo.mcp_client import ShopClient
from shop_demo.models import Basket, BasketItem

PROJECT = Path(__file__).resolve().parent.parent


class NativeChecks(unittest.IsolatedAsyncioTestCase):
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
