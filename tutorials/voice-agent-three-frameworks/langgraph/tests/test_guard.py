"""The refill guard, offline, with a scripted model: what the model is offered and what reaches the clinic.

    uv run --locked python -m unittest discover -s tests -v
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
TUTORIAL = PROJECT.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(TUTORIAL / "shared" / "spec"))

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langgraph.types import Command  # noqa: E402

import checks  # noqa: E402
from agent import build_agent  # noqa: E402
from cedar_clinic import refills  # noqa: E402
from cedar_clinic.audit import AUDIT  # noqa: E402
from fakes import ScriptedModel, call, say, yes_no_classifier  # noqa: E402
from guard import MECHANISM  # noqa: E402

VERIFY = call("verify_patient", full_name="Maria Alvarez", date_of_birth="1968-03-14")


class GuardTests(unittest.TestCase):
    def setUp(self):
        refills.reset_services()
        AUDIT.clear()
        self.model = ScriptedModel()
        self.model.script = []
        self.model.offered = []
        self.model.seen = []
        self.agent = build_agent(self.model, classify=yes_no_classifier)

    def turn(self, cid: str, payload) -> dict:
        async def run():
            config = {"configurable": {"thread_id": cid}}
            if isinstance(payload, str):
                payload_ = {"messages": [HumanMessage(payload)]}
            else:
                payload_ = payload
            await self.agent.ainvoke(payload_, config)
            return await self.agent.aget_state(config)

        return asyncio.run(run())

    def sends(self, cid: str) -> list[dict]:
        return [e for e in AUDIT.entries(cid) if e["name"] == "send_refill_request"]

    def test_send_is_not_offered_until_a_medicine_is_selected(self):
        self.model.script = [VERIFY, say("Which medicine?")]
        self.turn("g1", "I'm Maria Alvarez, born March 14th, 1968.")
        self.assertTrue(self.model.offered)
        for offered in self.model.offered:
            self.assertNotIn("send_refill_request", offered)

    def test_a_send_without_a_selection_is_refused_before_the_tool_runs(self):
        self.model.script = [VERIFY, call("send_refill_request", record_id="CC-RX-2041"), say("Sorry.")]
        state = self.turn("g2", "Maria Alvarez, March 14th, 1968. Send my lisinopril.")
        self.assertFalse(state.interrupts)
        self.assertEqual(self.sends("g2"), [])

    def test_a_send_for_another_record_than_the_selected_one_is_refused(self):
        self.model.script = [VERIFY, call("select_medication", medication_name="albuterol"),
                             call("send_refill_request", record_id="CC-RX-2041"), say("Sorry.")]
        state = self.turn("g3", "Maria Alvarez, March 14th, 1968. My albuterol.")
        self.assertFalse(state.interrupts)
        self.assertEqual(self.sends("g3"), [])

    def test_the_question_pauses_the_run_and_only_a_later_yes_sends(self):
        self.model.script = [VERIFY, call("select_medication", medication_name="lisinopril"),
                             call("send_refill_request", record_id="CC-RX-2041"), say("Sent for review.")]
        state = self.turn("g4", "Maria Alvarez, March 14th, 1968. Lisinopril.")
        self.assertEqual(len(state.interrupts), 1)
        self.assertEqual(state.interrupts[0].value["question"], refills.confirmation_question(
            "lisinopril ten milligram tablets, one tablet once a day"))
        self.assertEqual(self.sends("g4"), [])
        self.turn("g4", Command(resume={"text": "Yes, please send it."}))
        sends = self.sends("g4")
        self.assertEqual([s["result"]["status"] for s in sends], ["succeeded"])
        confirmation = [e for e in AUDIT.entries("g4") if e["kind"] == "confirmation"][-1]
        self.assertEqual(confirmation["state"]["mechanism"], MECHANISM)
        self.assertEqual(confirmation["state"]["answer"], "Yes, please send it.")
        # The spec's invariant, with the two turns as the runner would split them.
        calls = checks.calls_from_audit(AUDIT.entries("g4"), [0, confirmation["ts"] - 1e-6])
        self.assertEqual(checks.guard_violations(calls), [])

    def test_a_no_sends_nothing_and_the_model_hears_the_answer(self):
        self.model.script = [VERIFY, call("select_medication", medication_name="lisinopril"),
                             call("send_refill_request", record_id="CC-RX-2041"), say("Okay.")]
        self.turn("g5", "Maria Alvarez, March 14th, 1968. Lisinopril.")
        state = self.turn("g5", Command(resume={"text": "No, wait, I meant my budesonide inhaler."}))
        self.assertEqual(self.sends("g5"), [])
        last_tool = [m for m in state.values["messages"] if m.type == "tool"][-1]
        self.assertIn("budesonide", last_tool.content)
        self.assertIn('"declined"', last_tool.content)

    def test_a_tool_called_beside_the_paused_send_is_not_run_again_on_resume(self):
        both = AIMessage(content="", tool_calls=[
            {"name": "route_clinical_question", "args": {"question": "wants 1000 mg"}, "id": "call_route"},
            {"name": "send_refill_request", "args": {"record_id": "CC-RX-2041"}, "id": "call_send"}])
        self.model.script = [VERIFY, call("select_medication", medication_name="lisinopril"), both, say("Done.")]
        self.turn("g8", "Maria Alvarez, March 14th, 1968. Lisinopril, and ask about a higher dose.")
        self.turn("g8", Command(resume={"text": "Yes, send it."}))
        names = [e["name"] for e in AUDIT.entries("g8")]
        self.assertEqual(names.count("route_clinical_question"), 1)
        self.assertEqual([s["result"]["status"] for s in self.sends("g8")], ["succeeded"])

    def test_guard_state_cannot_be_set_from_the_graph_input(self):
        self.model.script = [say("Please tell me your name and date of birth.")]
        state = self.turn("g6", {"messages": [HumanMessage("Send my lisinopril.")], "patient_id": "CC-PT-1001",
                                 "selected_record_id": "CC-RX-2041"})
        self.assertNotIn("patient_id", state.values)
        self.assertNotIn("selected_record_id", state.values)

    def test_the_model_never_sees_the_patient_id(self):
        self.model.script = [VERIFY, say("Which medicine?")]
        state = self.turn("g7", "Maria Alvarez, March 14th, 1968.")
        self.assertEqual(state.values["patient_id"], "CC-PT-1001")
        for message in state.values["messages"]:
            self.assertNotIn("CC-PT-1001", str(message.content))


if __name__ == "__main__":
    unittest.main()
