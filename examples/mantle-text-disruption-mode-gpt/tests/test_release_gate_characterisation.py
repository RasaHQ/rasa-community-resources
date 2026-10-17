"""Characterisation of which recovery tools the shipped skill puts behind the engine's confirmation. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -p "test_release_gate*" -v
The compile tests need rasa and are skipped under a bare python (use the project venv).

This records what the project ships TODAY. It is not a statement of how a recovery skill should be gated: whether
release_hold should sit behind the confirmation is a design decision this file does not make. The retained run it reads
is one synthetic seat hold and a scripted "Yes." written for another moment; a "Yes." to the assistant's offer to release
may be a reasonable answer, so these tests show a gap in permissions, not a passenger who lost a seat or did not consent.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SKILL = PROJECT / "skills" / "disruption_recovery" / "skill.md"
TRACKERS = PROJECT / "case-build" / "results" / "2026-09-30-gpt-5.5-low" / "trackers"
RELEASE_CASE = "adversarial-second-hold-as-backup"
HOLD_CASE = "normal-hold-chicago-morning"
GATE_BLOCK = (
    "      requires_confirmation:\n"
    "        enabled: true\n"
    "        utter_for_confirmation: utter_confirm_hold\n"
)


def tracker(name: str) -> dict:
    return json.loads((TRACKERS / f"{name}.json").read_text())


def tool_results(events: list[dict], tool: str) -> list[dict]:
    """Results of one tool, once each (the tracker records every call as mcp_tool_executed and tool_executed)."""
    seen = []
    for event in events:
        if event.get("event") == "tool_executed" and event.get("tool_name") == tool:
            result = event.get("result")
            seen.append(json.loads(result) if isinstance(result, str) else result)
    return seen


def preceding_user_text(events: list[dict], tool: str) -> str | None:
    last = None
    for event in events:
        if event.get("event") == "user":
            last = event.get("text")
        if event.get("event") == "tool_executed" and event.get("tool_name") == tool:
            return last
    return None


def ran_without_confirmation_step(events: list[dict], tool: str) -> bool:
    """True when the tool's first result is an outcome, not the engine's awaiting_confirmation state."""
    results = tool_results(events, tool)
    return bool(results) and results[0].get("status") != "awaiting_confirmation"


def compiled_gates(skill_path: Path) -> dict:
    from rasa.mantle.skills.markdown_skill_compiler import compile_markdown_skill

    skill = compile_markdown_skill(skill_path)
    return {tool.name: (None if tool.requires_confirmation is None else tool.requires_confirmation.enabled) for tool in skill.tools}


class CompiledGateCharacterisation(unittest.TestCase):
    def setUp(self):
        try:
            import rasa.mantle  # noqa: F401
        except ImportError as exc:
            self.skipTest(f"rasa not importable: {exc}")

    def test_the_shipped_skill_gates_the_hold_and_leaves_the_release_ungated(self):
        gates = compiled_gates(SKILL)
        self.assertIs(gates["hold_recovery_option"], True)
        self.assertIsNone(gates["release_hold"])
        for name in ("check_hold", "get_incident_status", "join_recovery_queue"):
            self.assertIsNone(gates[name], name)

    def test_the_check_can_see_a_gate_when_one_is_added_or_removed(self):
        text = SKILL.read_text()
        self.assertIn(GATE_BLOCK, text)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "disruption_recovery"
            folder.mkdir()
            # Control 1: the release gets the same gate as the hold -> the compiler reports it.
            gated_release = text.replace(
                "tool_constraints:\n", "tool_constraints:\n  - release_hold:\n" + GATE_BLOCK, 1
            )
            (folder / "skill.md").write_text(gated_release)
            self.assertIs(compiled_gates(folder / "skill.md")["release_hold"], True)
            # Control 2: the hold's gate is deleted -> the compiler reports none, with no engine complaint.
            ungated_hold = text.replace(GATE_BLOCK, "")
            (folder / "skill.md").write_text(ungated_hold)
            self.assertIsNone(compiled_gates(folder / "skill.md")["hold_recovery_option"])


class RetainedRunCharacterisation(unittest.TestCase):
    def test_in_the_retained_run_a_yes_was_followed_at_once_by_a_released_hold(self):
        events = tracker(RELEASE_CASE)["events"]
        offers = [e["text"] for e in events if e.get("event") == "bot"]
        self.assertIn("release it first", offers[1])
        self.assertEqual(preceding_user_text(events, "release_hold"), "Yes.")
        self.assertEqual(tool_results(events, "release_hold")[0]["status"], "released")
        self.assertTrue(ran_without_confirmation_step(events, "release_hold"))

    def test_the_engines_hold_in_another_retained_run_waits_for_confirmation_first(self):
        events = tracker(HOLD_CASE)["events"]
        self.assertEqual(tool_results(events, "hold_recovery_option")[0]["status"], "awaiting_confirmation")
        self.assertFalse(ran_without_confirmation_step(events, "hold_recovery_option"))

    def test_the_helper_notices_when_a_release_does_wait(self):
        events = json.loads(json.dumps(tracker(RELEASE_CASE)["events"]))
        for event in events:
            if event.get("event") == "tool_executed" and event.get("tool_name") == "release_hold":
                event["result"] = json.dumps({"status": "awaiting_confirmation"})
        self.assertFalse(ran_without_confirmation_step(events, "release_hold"))


if __name__ == "__main__":
    unittest.main()
