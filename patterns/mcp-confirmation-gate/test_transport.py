"""Real loopback MCP transport control; does not test model or engine gating."""
import asyncio
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mock_server import CANARY, DESCRIPTION


class Transport(unittest.TestCase):
    def test_description_and_result_reach_real_mcp_client(self):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        with tempfile.TemporaryFile() as log:
            child = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("mock_server.py")),
                 "--port", str(port)], stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 10
                while True:
                    if child.poll() is not None:
                        self.fail("Owned mock server exited before readiness")
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=.2):
                            break
                    except OSError:
                        if time.monotonic() >= deadline:
                            self.fail("Owned mock server did not become ready")
                        time.sleep(.05)

                async def read():
                    async with streamablehttp_client(f"http://127.0.0.1:{port}/mcp") as streams:
                        async with ClientSession(streams[0], streams[1]) as session:
                            await session.initialize()
                            tools = await session.list_tools()
                            self.assertEqual([t.name for t in tools.tools], ["read_case"])
                            self.assertEqual(tools.tools[0].description, DESCRIPTION)
                            self.assertNotIn(CANARY, tools.tools[0].description)
                            result = await session.call_tool("read_case", {})
                            self.assertFalse(result.isError)
                            self.assertEqual(result.structuredContent["value"], CANARY)
                            self.assertEqual(result.structuredContent["completion_step"],
                                             "record_local_canary")
                    # Exercise Mantle's actual MCP binding and shared pool too.
                    # The bootstrap stand-in contains only the two native input
                    # fields; this is not a trained model archive or chat turn.
                    from rasa.mantle.config.mcp import parse_mcp_servers
                    from rasa.mantle.tools.mcp_import_spec import try_parse_mcp_tool_import
                    from rasa.mantle.tools.mcp_runtime import MCPRuntime
                    settings = parse_mcp_servers([{"name": "fictional_support",
                                                   "url": f"http://127.0.0.1:{port}/mcp"}])
                    reference = try_parse_mcp_tool_import("mcp/fictional_support:read_case")
                    runtime = MCPRuntime()
                    try:
                        await runtime.prepare(SimpleNamespace(
                            mcp_servers=settings, mcp_tool_allowlist={"review_case": [reference]}))
                        self.assertTrue(runtime.has_mcp_tool("review_case", "read_case"))
                        self.assertFalse(runtime.has_mcp_tool("review_case", "record_local_canary"))
                        self.assertEqual(runtime.mcp_tool_schemas["review_case"]["read_case"].description,
                                         DESCRIPTION)
                        result = await runtime.call_mcp_tool("fictional_support", "read_case", {})
                        self.assertEqual(result.llm_response["value"], CANARY)
                    finally:
                        await runtime.close()
                with patch.dict(os.environ, {"NO_PROXY": "127.0.0.1,localhost",
                                             "no_proxy": "127.0.0.1,localhost",
                                             "LANGFUSE_TRACING_ENABLED": "false"}):
                    asyncio.run(read())
            finally:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
