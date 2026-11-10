"""The LangGraph version says what the shared parts say, and marks its concerns.

Offline: no model, no network.

    uv run --locked python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
TUTORIAL = PROJECT.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(TUTORIAL / "shared" / "spec"))

from langchain_core.utils.function_calling import convert_to_openai_tool  # noqa: E402

import agent  # noqa: E402
import voice_loop  # noqa: E402
from cedar_clinic import instructions  # noqa: E402
from cedar_clinic.tools import TOOL_SPECS, json_schema  # noqa: E402


class InstructionParityTests(unittest.TestCase):
    def test_the_system_prompt_is_the_shared_text_with_the_shared_procedure(self):
        self.assertEqual(agent.SYSTEM_PROMPT, instructions.system_prompt(instructions.PROCEDURE))

    def test_the_greeting_is_the_shared_greeting(self):
        source = (PROJECT / "voice_loop.py").read_text()
        self.assertIn("instructions.GREETING", source)
        self.assertNotIn("Cedar Clinic prescription line.", source)

    def test_model_and_reasoning_effort(self):
        self.assertEqual(agent.MODEL, "gpt-5.5-2026-04-23")
        self.assertEqual(agent.REASONING_EFFORT, "low")
        model = agent.make_model(api_key="offline")
        self.assertEqual(model.reasoning_effort, "low")


class ToolParityTests(unittest.TestCase):
    def test_the_model_tools_are_the_shared_five(self):
        self.assertEqual([t.name for t in agent.TOOLS], list(TOOL_SPECS))

    def test_names_descriptions_and_parameters_are_tool_specs(self):
        for tool in agent.TOOLS:
            with self.subTest(tool=tool.name):
                sent = convert_to_openai_tool(tool)["function"]
                shared = json_schema(tool.name)
                self.assertEqual(sent["description"], shared["description"])
                self.assertEqual(sent["parameters"]["required"], shared["parameters"]["required"])
                self.assertEqual(
                    {k: {"type": v["type"], "description": v["description"]}
                     for k, v in sent["parameters"]["properties"].items()},
                    shared["parameters"]["properties"])

    def test_no_tool_takes_a_patient_id_or_a_dose(self):
        for tool in agent.TOOLS:
            for param in convert_to_openai_tool(tool)["function"]["parameters"]["properties"]:
                self.assertNotRegex(param, r"dose|strength|quantity|mg|approve|patient_id", f"{tool.name}({param})")


class VoiceSettingsTests(unittest.TestCase):
    def test_barge_in_off_and_silence_check_in_at_thirty_seconds(self):
        self.assertFalse(voice_loop.INTERRUPTIONS_ENABLED)
        self.assertEqual(voice_loop.SILENCE_TIMEOUT_S, 30.0)
        self.assertEqual(voice_loop.SAMPLE_RATE, 24000)


class ConcernMarkerTests(unittest.TestCase):
    """Every counted file declares its concern (see COMPARISON-PLAN.md)."""

    def test_every_counted_file_is_tagged(self):
        from count_concerns import counted_files, file_concern

        files = counted_files(PROJECT)
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=str(path.relative_to(PROJECT))):
                self.assertIsNotNone(file_concern(path, PROJECT), "no `concern:` or `concern-begin:` marker")


if __name__ == "__main__":
    unittest.main()
