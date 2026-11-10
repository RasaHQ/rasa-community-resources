"""Actual pinned Mantle invoker with fixture channel context; no model."""
import importlib.util
import json
import unittest
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rasa.mantle.orchestration.tool_execution.invoker import ToolInvoker
from shop_adviser.return_records import RETURNS


class RefundBinding(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        file = Path(__file__).resolve().parents[1] / "skills/refund_check/tools.py"
        spec = importlib.util.spec_from_file_location("refund_bindings", file)
        self.tools = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tools)
        self.tracker = SimpleNamespace(active_frame=None,
            memory_scope=lambda: ("refund_check", "refund_check"),
            recording_write=lambda **kwargs: nullcontext())
        self.invoker = ToolInvoker(mcp_runtime=None, tool_timeout=20,
            verbatim_trigger_evaluator=SimpleNamespace(queue_tool_outcome=lambda **kwargs: None))

    async def ask(self, sender, **arguments):
        with patch("rasa.mantle.orchestration.turn_context.current_turn_context",
                   return_value=SimpleNamespace(sender_id=sender)):
            return json.loads(await self.invoker.call_builder_tool(
                self.tools.check_return, "check_return", arguments, self.tracker))

    async def test_actual_invoker_returns_offer_for_both_conversations_of_same_demo_customer(self):
        for sender in ["willow-a-chat", "willow-a-voice"]:
            self.assertEqual(await self.ask(sender, order_ref="WS-RETURN-01"),
                             {"status": "full_refund_offer", "amount_minor": 1299, "currency": "GBP"})

    async def test_actual_invoker_keeps_other_customers_order_indistinguishable_from_missing(self):
        self.assertEqual(await self.ask("willow-b-chat", order_ref="WS-RETURN-01"),
                         {"status": "unknown_order"})
        self.assertEqual(await self.ask("willow-b-chat", order_ref="missing"),
                         {"status": "unknown_order"})

    async def test_unknown_sender_does_not_lookup_an_order(self):
        with patch.object(self.tools, "find_return", side_effect=AssertionError("lookup must not run")):
            self.assertEqual(await self.ask("unknown", order_ref="WS-RETURN-01"),
                             {"status": "unknown_demo_sender"})

    async def test_model_cannot_supply_amount_or_customer_as_tool_arguments(self):
        for extra in [{"amount_minor": 1}, {"customer_id": "customer-b"}]:
            result = await self.ask("willow-a-chat", order_ref="WS-RETURN-01", **extra)
            self.assertIn("error", result)
            self.assertNotIn("amount_minor", result)

    async def test_each_call_uses_the_record_looked_up_for_that_call(self):
        self.assertEqual((await self.ask("willow-a-chat", order_ref="WS-RETURN-01"))["amount_minor"], 1299)
        with patch.object(self.tools, "find_return", return_value=replace(RETURNS["WS-RETURN-01"], paid_minor=675)):
            self.assertEqual((await self.ask("willow-a-chat", order_ref="WS-RETURN-01"))["amount_minor"], 675)

    async def test_review_and_inspection_are_statuses_not_payment_receipts(self):
        self.assertEqual(await self.ask("willow-a-chat", order_ref="WS-RETURN-LATE"),
                         {"status": "staff_review", "reason": "outside_automatic_window"})
        self.assertEqual(await self.ask("willow-a-chat", order_ref="WS-RETURN-PENDING"),
                         {"status": "awaiting_inspection"})


if __name__ == "__main__":
    unittest.main()
