"""Presentation controls exercise the pinned SDK payload and listen consumer."""
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from lib import reply_policy as policy
from rasa.mantle.hooks.payloads import ModelResponsePayload


class ReplyPolicyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        policy._delivered.clear()
        self.native=SimpleNamespace(sender_id="caller",turn=object(),is_cancelled=False)
        self.patch=patch.object(policy,"current_turn_context",return_value=self.native)
        self.patch.start();self.addCleanup(self.patch.stop)
        self.addCleanup(policy._delivered.clear)

    def payload(self):
        return ModelResponsePayload(sender_id="caller",text="Here is the review again. Confirm the old transfer.",
            tool_calls=[{"id":"duplicate","tool_name":"banking_review_transfer","tool_args":{},"type":"function"}])

    async def test_actual_sdk_ends_silently_after_one_delivered_host_reply(self):
        from rasa.mantle.orchestration.orchestrator import Orchestrator
        from rasa.shared.providers.llm.llm_response import LLMToolCall
        policy.remember_delivery()
        reply=await policy.keep_host_reply_once(self.payload())
        self.assertIsNone(reply.text)
        self.assertEqual([call["tool_name"] for call in reply.tool_calls],["listen"])
        consumer=SimpleNamespace(_dispatch_tool_calls=AsyncMock(),
            _completed_or_cancelled=lambda result,**kw:result)
        with patch("rasa.mantle.orchestration.orchestrator.current_turn_context",return_value=self.native):
            result=await Orchestrator._handle_llm_response(consumer,reply.text,
                [LLMToolCall(**call) for call in reply.tool_calls],None,None,None,0,None,True,streamed=False)
        self.assertEqual(result.iteration_count,1)
        self.assertEqual(consumer._dispatch_tool_calls.await_count,1)
        self.assertEqual(consumer._dispatch_tool_calls.call_args.args[0][0].tool_name,"listen")

    async def test_actual_snapshot_loader_registers_and_invokes_our_hook(self):
        # Other snapshot tests intentionally evict lib modules. Use a fresh
        # consumer process, with the SDK's real ContextVar, rather than an old
        # test import or a mocked loader.
        from pathlib import Path
        import subprocess
        import sys
        program = """
import asyncio
from pathlib import Path
from types import SimpleNamespace
from rasa.mantle.hooks.loader import load_hooks
from rasa.mantle.hooks.payloads import ModelResponsePayload
from rasa.mantle.orchestration.turn_context import _current_turn_ctx
registry=load_hooks(Path.cwd())
assert registry.modifier_count==1
from lib import reply_policy
_current_turn_ctx.set(SimpleNamespace(sender_id="caller",turn=object(),is_cancelled=False))
reply_policy.remember_delivery()
reply=asyncio.run(registry.all_hooks()[0].func(ModelResponsePayload(sender_id="caller",text="duplicate")))
assert reply.text is None
assert [call["tool_name"] for call in reply.tool_calls]==["listen"]
"""
        result=subprocess.run([sys.executable,"-c",program],cwd=Path(__file__).resolve().parents[1],
                              capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    async def test_ordinary_response_and_next_turn_are_unchanged(self):
        payload=self.payload()
        self.assertIs(await policy.keep_host_reply_once(payload),payload)
        policy.remember_delivery();self.native.turn=object()
        self.assertIs(await policy.keep_host_reply_once(payload),payload)

    async def test_sender_and_age_do_not_leak_a_reply_marker(self):
        policy.remember_delivery()
        other=self.payload().model_copy(update={"sender_id":"other"})
        self.assertIs(await policy.keep_host_reply_once(other),other)
        with patch.object(policy.time,"monotonic",return_value=10**12):
            payload=self.payload()
            self.assertIs(await policy.keep_host_reply_once(payload),payload)

    async def test_cancelled_turn_cannot_mark_delivery(self):
        self.native.is_cancelled=True
        policy.remember_delivery()
        self.assertFalse(policy.delivery_pending())
        self.assertEqual(policy._delivered,{})
