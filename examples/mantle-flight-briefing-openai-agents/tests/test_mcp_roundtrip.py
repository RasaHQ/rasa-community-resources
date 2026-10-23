"""Actual MCP ASGI request path, in process: no listening port or provider."""
from pathlib import Path
import sys
import unittest
import os
import json
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.identity import SENDER_META
from briefing.jobs import Jobs, Owner
from briefing.mcp_app import create_app
from briefing.replay import ReplayRunner
from project.lib.capability_logging import contains_api_key


class McpRoundtrip(unittest.IsolatedAsyncioTestCase):
    async def test_local_display_delegates_board_to_core_without_mcp_capability_in_url(self):
        from types import ModuleType
        module = ModuleType('zeo_core.adapters.widget_html')
        seen = []
        def render(cards, *, document=False, title='Briefing', place=None):
            seen.append((cards, document, title))
            return '<p>REPLAY shared renderer contract control</p>'
        module.render_snapshot_html = render
        jobs = Jobs(ReplayRunner(), ownership_mode='capability')
        started = await jobs.briefing(Owner('mantle', 'renderer-control'), action='start', request='Replay DEMO101')
        await jobs._jobs[started['job_id']].task
        self.assertTrue(jobs.display_snapshot())
        app = create_app(jobs, transport_token='synthetic-transport-with-no-real-authority')
        with patch.dict(sys.modules, {'zeo_core.adapters.widget_html': module}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                                        base_url='http://127.0.0.1:8942') as client:
                response = await client.get('/cards')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.text, '<p>REPLAY shared renderer contract control</p>')
                self.assertEqual(len(seen), 1)
                self.assertTrue(seen[0][1])
                refused = await client.get('/cards?briefing_id=brf_synthetic')
                self.assertEqual(refused.status_code, 400)
                self.assertEqual(len(seen), 1)
                self.assertNotIn('brf_synthetic', refused.text)
                private = await client.post('/mcp', json={})
                self.assertEqual(private.status_code, 401)
        await jobs.close()

    async def test_synthetic_keys_refused_in_meta_and_arguments_without_echo(self):
        runner = ReplayRunner()
        jobs = Jobs(runner, replacement_plan=runner.replacement_plan, ownership_mode='capability')
        token = 'synthetic-transport-with-no-real-authority'
        app = create_app(jobs, transport_token=token)
        key = 'sk-' + 'syntheticOnly' * 4
        async with app._app.router.lifespan_context(app._app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://127.0.0.1:8942',
                    headers={'accept': 'application/json, text/event-stream', 'authorization': 'Bearer ' + token}) as client:
                for index, (arguments, meta) in enumerate([
                    ({'action': 'start', 'request': 'Replay DEMO101'}, {'provider_key': key}),
                    ({'action': 'start', 'request': key}, {}),
                    ({'action': 'get', 'api_key': key}, {}),
                ]):
                    response = await client.post('/mcp', json={'jsonrpc': '2.0', 'id': index + 1,
                        'method': 'tools/call', 'params': {'name': 'briefing', 'arguments': arguments, '_meta': meta}})
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(any(key[i:i + 8] in response.text for i in range(len(key) - 7)), 'planted key fragment escaped')
                    self.assertIn('error', response.json())
                self.assertEqual(jobs._jobs, {})

    async def test_key_bearing_extra_argument_refused_before_framework_parsing(self):
        from briefing.mcp_app import _MantlePeer
        called = False
        async def framework(scope, receive, send):
            nonlocal called
            called = True
            raise AssertionError('framework must not parse or log credential input')
        token = 'synthetic-transport-token-with-no-authority'
        key = 'sk-proj-' + 'uniqueSyntheticCanary' * 5
        app = _MantlePeer(framework, token)
        with patch.dict(os.environ, {'OPENAI_API_KEY': key}, clear=True):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://127.0.0.1',
                    headers={'authorization': 'Bearer ' + token}) as client:
                for value in (key, key[15:70]):
                    payload = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                        'params': {'name': 'briefing', 'arguments': {'extra': 'long prefix ' * 20 + value}}})
                    # Unicode-escaped input is decoded before the framework too.
                    payload = payload.replace('s', chr(92) + 'u0073')
                    response = await client.post('/mcp', content=payload)
                    self.assertFalse(called)
                    self.assertEqual(response.json()['error']['code'], -32602)
                    self.assertFalse(any(key[i:i + 8] in response.text for i in range(len(key) - 7)),
                                     'planted key fragment escaped')

    async def test_source_card_and_transcript_do_not_echo_synthetic_key(self):
        from project.lib.card_text import render_cards
        runner = ReplayRunner()
        jobs = Jobs(runner, replacement_plan=runner.replacement_plan, ownership_mode='capability')
        from briefing.jobs import Owner
        owner = Owner('mantle', 'capability-possession')
        try:
            started = await jobs.briefing(owner, action='start', request='Replay DEMO101')
            await jobs._jobs[started['job_id']].task
            snapshot = await jobs.briefing(owner, action='get', job_id=started['job_id'])
            key = 'sk-' + 'syntheticOnly' * 4
            snapshot['cards'][0]['data_ref']['source'] = key
            text = render_cards(snapshot)
            self.assertFalse(any(key[i:i + 8] in text for i in range(len(key) - 7)), 'planted card fragment escaped')
            self.assertIn('credential redacted', text)
        finally:
            await jobs.close()

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
                self.assertEqual([tool["name"] for tool in tools], ["briefing", "find_flights"])
                self.assertFalse(tools[0]["inputSchema"].get("additionalProperties", True))
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
                self.assertEqual(result["structuredContent"]["progress"][1:4], ["flight", "weather", "timeline"])
                unchanged = result["structuredContent"]
                for action, extra in (("get", {}), ("revise", {"change": "Replay DEMO101 later arrival"})):
                    refused = await call("conversation-b", {"action": action, "briefing_id": "made-up-id", **extra})
                    self.assertTrue(refused.get("isError"), refused)
                absent = await rpc("tools/call", {"name": "briefing", "arguments": {"action": "get"}})
                self.assertTrue(absent.get("isError"), absent)
                after_refusals = await call("conversation-a", {"action": "get", "briefing_id": job_id})
                self.assertEqual(after_refusals["structuredContent"], unchanged)
                for arguments in (
                    {"action": "list"},
                    {"action": "get", "briefing_id": job_id, "job_id": job_id},
                    {"action": "get", "briefing_id": job_id, "user_id": "invented"},
                    {"action": "revise", "briefing_id": job_id, "request": "extra", "change": "Replay DEMO101 later arrival"},
                ):
                    refused = await call("conversation-b", arguments)
                    self.assertTrue(refused.get("isError"), "unsupported argument combination was accepted")
                # The fallback is deliberately weaker: possession of the real
                # capability grants access even from another conversation.
                possessed = await call("conversation-b", {"action": "get", "briefing_id": job_id})
                self.assertEqual(possessed["structuredContent"]["status"], "complete")
                revised = await call("conversation-b", {"action": "revise", "briefing_id": job_id,
                                                         "change": "Replay DEMO101 later arrival"})
                self.assertFalse(revised.get("isError"), revised)
                await jobs._jobs[job_id].task
                shared = await call("conversation-b", {"action": "get", "briefing_id": job_id})
                self.assertEqual(shared["structuredContent"]["revision"], 2)
                pending = await call("conversation-a", {"action": "start", "request": "Replay DEMO101 missing inputs"})
                pending_id = pending["structuredContent"]["briefing_id"]
                await jobs._jobs[pending_id].task
                question = await call("conversation-a", {"action": "get", "briefing_id": pending_id})
                self.assertEqual(question["structuredContent"]["status"], "needs_input")
                self.assertEqual(question["structuredContent"]["needs_input"]["field"], "meeting_time")
                for answer in ("2026-10-22T21:00:00Z", "45 minutes"):
                    resumed = await call("conversation-a", {"action": "revise", "briefing_id": pending_id, "change": answer})
                    self.assertEqual(resumed["structuredContent"]["briefing_id"], pending_id)
                    await jobs._jobs[pending_id].task
                finished = await call("conversation-a", {"action": "get", "briefing_id": pending_id})
                self.assertEqual(finished["structuredContent"]["status"], "complete")
                timeline = next(card for card in finished["structuredContent"]["cards"]
                                if card["event"]["component"] == "arrival_timeline")
                self.assertEqual(timeline["data_ref"]["payload"]["margin_minutes"], 165)
                response = await client.post("/mcp", headers={"authorization": "Bearer invalid"}, json={})
                self.assertEqual(response.status_code, 401)
        await jobs.close()


if __name__ == "__main__":
    unittest.main()
