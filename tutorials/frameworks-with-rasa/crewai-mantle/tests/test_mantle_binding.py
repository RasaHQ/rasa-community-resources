"""Actual decorated Mantle tools reach the native crew with a scripted model."""

import importlib.util
import inspect
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from crew_transport import CrewProcess


class MantleClaimBindings(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        file = Path(__file__).resolve().parents[1] / "skills/claim_checklist/tools.py"
        spec = importlib.util.spec_from_file_location("claim_bindings", file)
        self.tools = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tools)
        self.tools.WORKER = CrewProcess(fixture=True)

    async def test_only_question_is_exposed_to_research_tool(self):
        self.assertEqual(
            list(inspect.signature(self.tools.research_claim_documents).parameters),
            ["question", "context"],
        )

    async def test_actual_native_crew_reached(self):
        with patch(
            "rasa.mantle.orchestration.turn_context.current_turn_context",
            return_value=SimpleNamespace(sender_id="caller-a"),
        ):
            await self.tools.select_claim_type(claim_type="vehicle")
            result = await self.tools.research_claim_documents(
                question="What documents?"
            )
        self.assertEqual(result.llm_response["status"], "ready")
        self.assertEqual(result.llm_response["source"]["source_id"], "HC-V-101")

    async def test_mocked_senders_keep_selection_separate(self):
        path = "rasa.mantle.orchestration.turn_context.current_turn_context"
        with patch(path, return_value=SimpleNamespace(sender_id="caller-a")):
            await self.tools.select_claim_type(claim_type="vehicle")
        with patch(path, return_value=SimpleNamespace(sender_id="caller-b")):
            result = await self.tools.research_claim_documents(
                question="What documents?"
            )
            self.assertEqual(result.llm_response["status"], "needs_claim_type")
            await self.tools.select_claim_type(claim_type="travel")
            result = await self.tools.research_claim_documents(
                question="What documents?"
            )
            self.assertEqual(result.llm_response["source"]["source_id"], "HC-T-201")

    async def test_recorded_tool_failure_is_withheld(self):
        self.tools.WORKER = CrewProcess(fixture=True, unavailable=True)
        with patch(
            "rasa.mantle.orchestration.turn_context.current_turn_context",
            return_value=SimpleNamespace(sender_id="caller-a"),
        ):
            await self.tools.select_claim_type(claim_type="vehicle")
            result = await self.tools.research_claim_documents(
                question="What documents?"
            )
        self.assertEqual(result.llm_response["status"], "incomplete")
        self.assertNotIn("checklist", result.llm_response)
