"""Actual decorated Rasa bindings with the native Strands Agent/tool."""
import importlib.util
import inspect
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

class MantleNetworkBindings(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        path = Path(__file__).resolve().parents[1] / "skills/network_help/tools.py"
        spec = importlib.util.spec_from_file_location("native_network_binding", path)
        self.tools = importlib.util.module_from_spec(spec);spec.loader.exec_module(self.tools)

    async def test_signature_offers_question_not_area_or_tool_name(self):
        self.assertEqual(list(inspect.signature(self.tools.inspect_network_for_user).parameters), ["question", "context"])

    async def test_actual_registered_strands_tool_reached(self):
        with patch("rasa.mantle.orchestration.turn_context.current_turn_context", return_value=SimpleNamespace(sender_id="caller-a")):
            await self.tools.select_network_area(area="north")
            result = await self.tools.inspect_network_for_user(question="Slow connection")
        self.assertEqual(result.llm_response["source"]["id"], "JM-N-101")
        self.assertEqual(self.tools.SPECIALIST.messages, [])

    async def test_two_mocked_contexts_keep_area_mapping_separate(self):
        with patch("rasa.mantle.orchestration.turn_context.current_turn_context", return_value=SimpleNamespace(sender_id="caller-a")):
            await self.tools.select_network_area(area="north")
        with patch("rasa.mantle.orchestration.turn_context.current_turn_context", return_value=SimpleNamespace(sender_id="caller-b")):
            result = await self.tools.inspect_network_for_user(question="Slow connection")
            self.assertEqual(result.llm_response, {"status": "needs_area"})
            await self.tools.select_network_area(area="south")
            result = await self.tools.inspect_network_for_user(question="Slow connection")
            self.assertEqual(result.llm_response["source"]["id"], "JM-S-201")
        self.assertEqual(self.tools.SPECIALIST.messages, [])

if __name__ == "__main__": unittest.main()
