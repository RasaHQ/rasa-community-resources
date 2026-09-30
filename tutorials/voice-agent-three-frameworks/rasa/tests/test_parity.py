"""The Rasa version says what the shared parts say, and marks its concerns.

Offline: no model, no network, no licence. Run in this project's venv:

    uv run --locked python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

import yaml

PROJECT = Path(__file__).resolve().parent.parent
TUTORIAL = PROJECT.parent
sys.path.insert(0, str(TUTORIAL / "shared" / "clinic"))
sys.path.insert(0, str(TUTORIAL / "shared" / "spec"))

from cedar_clinic import instructions, refills  # noqa: E402
from cedar_clinic.tools import TOOL_SPECS  # noqa: E402

TOOLS_PY = PROJECT / "skills" / "request_refill" / "tools.py"


def _squash(text: str) -> str:
    return " ".join(str(text).split())


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    _, front, _body = text.split("---", 2)
    return yaml.safe_load(front)


class InstructionParityTests(unittest.TestCase):
    def test_agent_yml_uses_the_shared_persona_rules_and_voice_rules(self):
        agent = yaml.safe_load((PROJECT / "agent.yml").read_text())
        self.assertEqual(_squash(agent["agent"]["persona"]), _squash(instructions.PERSONA))
        self.assertEqual(agent["rules"], instructions.RULES)
        self.assertEqual(_squash(agent["prompts"]["voice_rules"]), _squash(instructions.VOICE_RULES))

    def test_greeting_confirmation_and_denial_are_the_shared_words(self):
        project = yaml.safe_load((PROJECT / "responses.yml").read_text())["responses"]
        self.assertEqual(_squash(project["utter_greet"][0]["text"]), _squash(instructions.GREETING))
        skill = yaml.safe_load((PROJECT / "skills" / "request_refill" / "responses.yml").read_text())["responses"]
        question = _squash(skill["utter_confirm_refill_request"][0]["text"])
        self.assertEqual(question.replace("{selected_medication_label}", "X"),
                         _squash(refills.confirmation_question("X")))
        self.assertEqual(_squash(skill["utter_refill_request_not_sent"][0]["text"]), refills.DECLINED_TEXT)


class ToolParityTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(TOOLS_PY.read_text())
        self.functions = {n.name: n for n in self.tree.body if isinstance(n, ast.AsyncFunctionDef)}

    def test_the_model_tools_are_the_shared_five(self):
        self.assertEqual(set(self.functions), set(TOOL_SPECS))

    def test_descriptions_come_from_tool_specs(self):
        for name, node in self.functions.items():
            decorator = node.decorator_list[0]
            kw = {k.arg: k.value for k in decorator.keywords}
            self.assertEqual(ast.unparse(kw["description"]), f"TOOL_SPECS['{name}']['description']", name)

    def test_parameters_and_their_docs_match_tool_specs(self):
        for name, node in self.functions.items():
            params = [a.arg for a in node.args.args if a.arg != "context"]
            self.assertEqual(params, list(TOOL_SPECS[name]["parameters"]), name)
            doc = ast.get_docstring(node) or ""
            for param, spec in TOOL_SPECS[name]["parameters"].items():
                match = re.search(rf"^\s*{param}: (.+)$", doc, re.MULTILINE)
                self.assertIsNotNone(match, f"{name}: no Args entry for {param}")
                self.assertEqual(match.group(1).strip(), spec["description"], f"{name}.{param}")

    def test_no_tool_takes_a_dose(self):
        for name, node in self.functions.items():
            for arg in node.args.args:
                self.assertNotRegex(arg.arg, r"dose|strength|quantity|mg|approve|patient_id", f"{name}({arg.arg})")


class GuardConfigurationTests(unittest.TestCase):
    def test_send_is_gated_on_the_selection_and_the_caller_confirmation(self):
        front = _frontmatter(PROJECT / "skills" / "request_refill" / "skill.md")
        constraints = {k: v for item in front["tool_constraints"] for k, v in item.items()}
        send = constraints["send_refill_request"]
        self.assertEqual(send["requires"], "session.request_refill.selected_record_id")
        self.assertTrue(send["requires_confirmation"]["enabled"])
        self.assertEqual(send["requires_confirmation"]["utter_for_confirmation"], "utter_confirm_refill_request")

    def test_guard_memory_is_never_model_settable(self):
        def settable(node) -> bool:
            if isinstance(node, dict):
                return bool(node.get("llm_settable")) or any(settable(v) for v in node.values())
            return False

        for path in (PROJECT / "memory.yml", PROJECT / "skills" / "request_refill" / "memory.yml"):
            self.assertFalse(settable(yaml.safe_load(path.read_text())), path)

    def test_barge_in_is_off_on_both_voice_channels(self):
        channels = yaml.safe_load((PROJECT / "integrations.yml").read_text())["channels"]
        for name in ("browser_audio", "inspector"):
            self.assertFalse(channels[name]["interruptions"]["enabled"], name)


class ConcernMarkerTests(unittest.TestCase):
    """Every counted file declares its concern (see COMPARISON-PLAN.md)."""

    def test_every_counted_file_is_tagged(self):
        from count_concerns import counted_files, file_concern

        files = counted_files(PROJECT)
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=str(path.relative_to(PROJECT))):
                self.assertIsNotNone(file_concern(path), "no `concern:` or `concern-begin:` marker")


if __name__ == "__main__":
    unittest.main()
