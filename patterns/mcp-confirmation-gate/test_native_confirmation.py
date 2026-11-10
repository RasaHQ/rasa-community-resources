"""Pinned native gate/invoker controls with an in-memory tracker stand-in.

These drive explicit resolution arguments, not model interpretations of consent.
They do not exercise the full orchestrator or an MCP-originated model decision.
"""
import json
import unittest
from contextlib import nullcontext
from types import SimpleNamespace

from rasa.mantle.orchestration.tool_execution.constraints import ToolConfirmationGate
from rasa.mantle.orchestration.tool_execution.invoker import ToolInvoker
from rasa.mantle.skills.conditions import GatedTool, RequiresConfirmation
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from mock_server import CANARY


class MemoryTracker:
    active_frame = None

    def __init__(self):
        self.pending_tool_confirmation = None
        self.events = []

    def memory_scope(self):
        return "review_case", "review_case"

    def recording_write(self, **kwargs):
        return nullcontext()

    def pending_tool_confirmation_for_active_frame(self):
        return self.pending_tool_confirmation

    def set_pending_tool_confirmation(self, pending):
        self.pending_tool_confirmation = pending

    def clear_pending_tool_confirmation(self):
        self.pending_tool_confirmation = None

    def apply_events(self, events):
        self.events.extend(events)


class NativeConfirmation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.recorded = []

        @tool(description="Record only a fictional canary in this test's memory.")
        async def record_local_canary(value: str, context: ToolContext = None) -> ToolResult:
            self.recorded.append(value)
            return ToolResult(llm_response={"status": "recorded", "value": value})

        self.func = record_local_canary
        self.tracker = MemoryTracker()
        self.invoker = ToolInvoker(
            mcp_runtime=None, tool_timeout=20,
            verbatim_trigger_evaluator=SimpleNamespace(queue_tool_outcome=lambda **kw: None))
        self.gate = ToolConfirmationGate(
            tool_funcs={"review_case": {"record_local_canary": self.func}},
            tool_invoker=self.invoker,
            resolve_utterance=lambda *args: None)
        self.constraint = GatedTool(
            name="record_local_canary",
            requires_confirmation=RequiresConfirmation(enabled=True))

    def pause(self, value=CANARY):
        result = self.gate.gate_builder_tool(
            tool_gate=self.constraint, tool_name="record_local_canary",
            tool_args={"value": value}, tracker_handle=self.tracker,
            skill_id="review_case")
        self.assertEqual(self.recorded, [])
        self.assertIsNotNone(self.tracker.pending_tool_confirmation)
        return result

    async def test_same_turn_resolution_cannot_run_tool(self):
        self.pause()
        result, complete = await self.gate.dispatch_resolve({"confirmed": True}, self.tracker)
        self.assertFalse(complete)
        self.assertIn("same turn", result)
        self.assertEqual(self.recorded, [])

    async def test_later_true_runs_stored_arguments_once(self):
        self.pause()
        self.gate.begin_user_turn()
        result, complete = await self.gate.dispatch_resolve(
            {"confirmed": True, "value": "REPLACEMENT-MUST-NOT-WIN"}, self.tracker)
        self.assertTrue(complete)
        self.assertEqual(json.loads(result)["value"], CANARY)
        self.assertEqual(self.recorded, [CANARY])
        self.assertIsNone(self.tracker.pending_tool_confirmation)
        _, complete = await self.gate.dispatch_resolve({"confirmed": True}, self.tracker)
        self.assertFalse(complete)
        self.assertEqual(self.recorded, [CANARY])

    async def test_later_false_cancels_without_execution(self):
        self.pause()
        self.gate.begin_user_turn()
        _, complete = await self.gate.dispatch_resolve({"confirmed": False}, self.tracker)
        self.assertTrue(complete)
        self.assertEqual(self.recorded, [])
        self.assertIsNone(self.tracker.pending_tool_confirmation)

    async def test_truthy_string_is_not_boolean_confirmation(self):
        self.pause()
        self.gate.begin_user_turn()
        _, complete = await self.gate.dispatch_resolve({"confirmed": "yes"}, self.tracker)
        self.assertFalse(complete)
        self.assertEqual(self.recorded, [])
        self.assertIsNotNone(self.tracker.pending_tool_confirmation)

    async def test_pending_recall_cannot_replace_stored_canary(self):
        self.pause()
        self.pause("REPLACEMENT-MUST-NOT-WIN")
        self.assertEqual(self.tracker.pending_tool_confirmation.tool_args, {"value": CANARY})
        self.assertEqual(self.recorded, [])

    async def test_ungated_native_invoker_records_immediately(self):
        result = await self.invoker.call_builder_tool(
            self.func, "record_local_canary", {"value": CANARY}, self.tracker)
        self.assertEqual(json.loads(result)["value"], CANARY)
        self.assertEqual(self.recorded, [CANARY])


if __name__ == "__main__":
    unittest.main()
