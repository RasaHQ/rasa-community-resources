"""Tests for the tool server's ownership of a running build, with no OpenAI key and no network.

Stand-ins replace the mcp and openai packages and the builder, so the test needs only Python. They check the
reproduced failure: cancelling a request must not free the server while the worker is still running.
"""
import asyncio
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

fastmcp = types.ModuleType("mcp.server.fastmcp")


class FakeFastMCP:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self):
        return lambda function: function


fastmcp.FastMCP = FakeFastMCP
for name in ("mcp", "mcp.server"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["mcp.server.fastmcp"] = fastmcp
openai = types.ModuleType("openai")
openai.OpenAI = object
sys.modules.setdefault("openai", openai)

import builder  # noqa: E402
import builder_server  # noqa: E402


class FixtureTransport(unittest.TestCase):
    def test_fixture_mode_never_dispatches_the_live_builder(self):
        sample = {"mode": "fixture", "build_id": "fixture-1", "saved": True,
                  "file": "/sample.py", "sha256": "ab" * 32, "builder_said": "No Agents session"}
        with patch.object(builder_server, "_fixture_mode", True), \
                patch.object(builder, "build", side_effect=AssertionError("no live dispatch")) as live, \
                patch.object(builder, "build_fixture", return_value=sample):
            result = asyncio.run(builder_server.build_change("a requested change"))
            self.assertEqual(result["mode"], "fixture")
            self.assertEqual(result["file"], sample["file"])
            live.assert_not_called()


class Ownership(unittest.TestCase):
    def setUp(self):
        self.release = threading.Event()
        self.started = threading.Event()
        self.calls = []

        def fake_build(request, show_events=True):
            self.calls.append(request)
            self.started.set()
            self.release.wait(10)
            return {"build_id": "b" + str(len(self.calls)), "saved": True, "sha256": "x", "builder_said": "done"}

        self.original = builder.build
        builder.build = fake_build
        self.addCleanup(setattr, builder, "build", self.original)
        self.addCleanup(self.release.set)

    def test_cancelling_a_request_does_not_free_a_running_build(self):
        async def scenario():
            first = asyncio.ensure_future(builder_server.build_change("one"))
            await asyncio.get_running_loop().run_in_executor(None, self.started.wait, 5)
            first.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first
            second = await builder_server.build_change("two")
            self.assertFalse(second["saved"])
            self.assertIn("already running", second["builder_said"])
            self.assertEqual(self.calls, ["one"], "a second build started while the first was still running")
            self.release.set()
            for _ in range(100):
                if builder_server._running.acquire(blocking=False):
                    builder_server._running.release()
                    break
                await asyncio.sleep(0.05)
            else:
                self.fail("the build was never released after the worker finished")
            third = await builder_server.build_change("three")
            self.assertTrue(third["saved"])

        asyncio.run(scenario())

    def test_a_finished_build_frees_the_server(self):
        self.release.set()
        result = asyncio.run(builder_server.build_change("one"))
        self.assertTrue(result["saved"])
        self.assertTrue(builder_server._running.acquire(blocking=False))
        builder_server._running.release()


if __name__ == "__main__":
    unittest.main()
