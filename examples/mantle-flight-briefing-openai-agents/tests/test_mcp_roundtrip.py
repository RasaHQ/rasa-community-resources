"""Actual MCP ASGI request path, in process: no listening port or provider."""
from pathlib import Path
import sys
import unittest

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.identity import SENDER_META
from briefing.jobs import Jobs
from briefing.mcp_app import create_app
from briefing.replay import ReplayRunner


class McpRoundtrip(unittest.IsolatedAsyncioTestCase):
    async def test_one_tool_and_authenticated_two_conversation_boundary(self):
        runner = ReplayRunner()
        jobs = Jobs(runner, replacement_plan=runner.replacement_plan, ownership_mode="capability")
        token = "fixture-transport-token-with-no-authority"
        app = create_app(jobs, transport_token=token)
        headers = {"accept": "application/json, text/event-stream",
                   "authorization": "Bearer " + token}
        async with app._app.router.lifespan_context(app._app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                                         base_url="http://127.0.0.1:8942", headers=headers) as client:
                request_id = 0

                async def rpc(method, params):
                    nonlocal request_id
                    request_id += 1
                    response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": request_id,
                                                               "method": method, "params": params})
                    self.assertEqual(response.status_code, 200, response.text)
                    return response.json()["result"]

                await rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                         "clientInfo": {"name": "author-control", "version": "1"}})
                tools = (await rpc("tools/list", {}))["tools"]
                self.assertEqual([tool["name"] for tool in tools], ["briefing"])
                self.assertFalse({"ctx", "user_id", "session_id", "owner"} &
                                 set(tools[0]["inputSchema"]["properties"]))

                async def call(sender, arguments):
                    return await rpc("tools/call", {"name": "briefing", "arguments": arguments,
                                                    "_meta": {SENDER_META: sender}})

                started = await call("conversation-a", {"action": "start", "request": "Replay DEMO101"})
                self.assertFalse(started.get("isError"), started)
                self.assertEqual(started["structuredContent"]["binding"], "capability_id")
                job_id = started["structuredContent"]["briefing_id"]
                self.assertTrue(job_id.startswith("brf_"))
                self.assertEqual(len(job_id), 47)
                await jobs._jobs[job_id].task
                result = await call("conversation-a", {"action": "get", "briefing_id": job_id})
                self.assertEqual(result["structuredContent"]["status"], "complete")
                self.assertEqual(len(result["structuredContent"]["cards"]), 3)
                for action, extra in (("get", {}), ("revise", {"change": "Replay DEMO101 later arrival"})):
                    refused = await call("conversation-b", {"action": action, "briefing_id": "made-up-id", **extra})
                    self.assertTrue(refused.get("isError"), refused)
                absent = await rpc("tools/call", {"name": "briefing", "arguments": {"action": "get"}})
                self.assertTrue(absent.get("isError"), absent)
                # The fallback is deliberately weaker: possession of the real
                # capability grants access even from another conversation.
                possessed = await call("conversation-b", {"action": "get", "briefing_id": job_id})
                self.assertEqual(possessed["structuredContent"]["status"], "complete")
                response = await client.post("/mcp", headers={"authorization": "Bearer invalid"}, json={})
                self.assertEqual(response.status_code, 401)
        await jobs.close()


if __name__ == "__main__":
    unittest.main()
