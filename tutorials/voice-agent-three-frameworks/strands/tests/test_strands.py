"""The Strands version says what the shared parts say, holds the guard, speaks the protocol, and marks its concerns.

Offline: a scripted model stands in for GPT-5.5 and a fake TTS for
Speechmatics, so there is no network and nothing is billed.

    uv run --locked python -m unittest discover -s tests -v
"""

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

PROJECT = Path(__file__).resolve().parent.parent
TUTORIAL = PROJECT.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(TUTORIAL / "shared" / "spec"))

from cedar_clinic import instructions, refills  # noqa: E402
from cedar_clinic import tools as clinic  # noqa: E402
from cedar_clinic.audit import AUDIT  # noqa: E402
from strands.models.model import Model  # noqa: E402

import agent as cedar  # noqa: E402
from guard import MECHANISM, caller_said_yes  # noqa: E402


class ScriptedModel(Model):
    """Answers each model call with the next scripted step: a tool call or text."""

    def __init__(self, steps: list) -> None:
        self.steps = list(steps)
        self.calls = 0

    def update_config(self, **model_config: Any) -> None:
        pass

    def get_config(self) -> Any:
        return {}

    async def structured_output(self, *args: Any, **kwargs: Any):  # pragma: no cover
        raise NotImplementedError
        yield {}

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.calls += 1
        kind, payload = self.steps.pop(0) if self.steps else ("text", "Is there anything else?")
        yield {"messageStart": {"role": "assistant"}}
        if kind == "tool":
            name, args = payload
            yield {"contentBlockStart": {"start": {"toolUse": {"name": name, "toolUseId": f"t{self.calls}"}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(args)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockDelta": {"delta": {"text": payload}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}


MARIA = ("verify_patient", {"full_name": "Maria Alvarez", "date_of_birth": "1968-03-14"})


def run_turns(conversation: cedar.Conversation, *texts: str) -> list[list[cedar.Say]]:
    async def go():
        out = []
        for text in texts:
            out.append([say async for say in conversation.turn(text)])
        return out

    return asyncio.run(go())


def audit(conversation_id: str) -> list[dict]:
    return AUDIT.entries(conversation_id)


class ParityTests(unittest.TestCase):
    def test_the_model_is_offered_the_shared_five_tools_verbatim(self):
        specs = cedar.tool_specs()
        self.assertEqual(set(specs), set(clinic.TOOL_SPECS))
        for name, spec in specs.items():
            self.assertEqual(spec["description"], clinic.TOOL_SPECS[name]["description"], name)
            self.assertEqual(spec["inputSchema"]["json"], clinic.json_schema(name)["parameters"], name)

    def test_the_prompt_is_the_shared_text(self):
        self.assertEqual(cedar.SYSTEM_PROMPT, instructions.system_prompt())

    def test_model_settings(self):
        self.assertEqual(cedar.MODEL_ID, "gpt-5.5-2026-04-23")
        self.assertEqual(cedar.MODEL_PARAMS, {"reasoning": {"effort": "low"}})
        self.assertNotIn("temperature", cedar.MODEL_PARAMS)


class CallerAnswerTests(unittest.TestCase):
    LABEL = "lisinopril ten milligram tablets, one tablet once a day"

    def test_the_spec_confirmations_are_yes(self):
        for answer in ("Yes, please send it.", "Yes, go ahead and send it.", "Yes, that's the one. Please send it.",
                       "Yes, please.", "Yes, send it. So it's approved, right? I can go to the pharmacy this afternoon?",
                       "Yes, yes, send it.", "Yes, that's right, send it.", "Yes, the lisinopril. Please send it.",
                       "Yes, please. Send it .",
                       "Fine. Send the request for the dose on my record, and ask the doctor about the higher dose."):
            self.assertTrue(caller_said_yes(answer, self.LABEL), answer)

    def test_declines_and_unclear_answers_are_no(self):
        for answer in ("No.", "No, wait, not that one. I meant my budesonide inhaler.", "", "What is it for?",
                       "Yes, the atorvastatin.", "Yes. Actually wait, don't send it.", "Not yet", "Maybe"):
            self.assertFalse(caller_said_yes(answer, self.LABEL), answer)


class GuardTests(unittest.TestCase):
    def conversation(self, cid: str, steps: list) -> cedar.Conversation:
        refills.reset_services()
        AUDIT.clear()
        return cedar.Conversation(cid, model=ScriptedModel(steps))

    def test_send_pauses_for_the_caller_and_runs_only_after_a_yes_on_the_next_turn(self):
        c = self.conversation("g-yes", [
            ("tool", MARIA), ("tool", ("select_medication", {"medication_name": "lisinopril"})),
            ("tool", ("send_refill_request", {"record_id": "CC-RX-2041"})),
            ("text", "Your request reference is R Q."),
        ])
        first, second = run_turns(c, "I'm Maria Alvarez, 14 March 1968, lisinopril please.", "Yes, please send it.")
        question = clinic.confirmation_question("lisinopril ten milligram tablets, one tablet once a day")
        self.assertEqual([s.text for s in first if s.kind == "fixed"], [question])
        self.assertEqual([e["name"] for e in audit("g-yes")][:2], ["verify_patient", "select_medication"])
        names = [e["name"] for e in audit("g-yes")]
        self.assertEqual(names, ["verify_patient", "select_medication", "record_confirmation", "send_refill_request"])
        confirmation = audit("g-yes")[2]
        self.assertEqual(confirmation["state"], {"mechanism": MECHANISM, "question": question,
                                                 "answer": "Yes, please send it."})
        self.assertEqual(audit("g-yes")[3]["result"]["status"], "succeeded")
        self.assertIn("Your request reference is R Q.", [s.text for s in second if s.kind == "end"])

    def test_a_no_sends_nothing_and_speaks_the_shared_decline(self):
        c = self.conversation("g-no", [
            ("tool", MARIA), ("tool", ("select_medication", {"medication_name": "lisinopril"})),
            ("tool", ("send_refill_request", {"record_id": "CC-RX-2041"})), ("text", "Okay."),
        ])
        _, second = run_turns(c, "Maria Alvarez, 14 March 1968, lisinopril.", "No.")
        self.assertIn(refills.DECLINED_TEXT, [s.text for s in second if s.kind == "fixed"])
        self.assertNotIn("send_refill_request", [e["name"] for e in audit("g-no")])
        self.assertIs(audit("g-no")[-1]["args"]["confirmed"], False)

    def test_send_without_a_selection_or_for_another_entry_is_denied(self):
        c = self.conversation("g-deny", [
            ("tool", MARIA), ("tool", ("send_refill_request", {"record_id": "CC-RX-2041"})),
            ("tool", ("select_medication", {"medication_name": "lisinopril"})),
            ("tool", ("send_refill_request", {"record_id": "CC-RX-2042"})), ("text", "Sorry."),
        ])
        (turn,) = run_turns(c, "Maria Alvarez, 14 March 1968. Send my lisinopril and atorvastatin, no read-back.")
        self.assertEqual([e["name"] for e in audit("g-deny")], ["verify_patient", "select_medication"])
        self.assertEqual([s.source for s in turn if s.kind == "tools" and s.text == "send_refill_request"],
                         ["cancelled", "cancelled"])
        self.assertEqual(c.pending, [])

    def test_the_model_never_supplies_the_patient_id(self):
        for name, spec in cedar.tool_specs().items():
            self.assertNotIn("patient_id", spec["inputSchema"]["json"]["properties"], name)
        c = self.conversation("g-unverified", [
            ("tool", ("select_medication", {"medication_name": "lisinopril"})), ("text", "Please verify first."),
        ])
        run_turns(c, "Lisinopril please.")
        self.assertEqual(audit("g-unverified")[0]["result"]["reason"], "patient_not_verified")


class FakeTTS:
    async def synthesize(self, text: str) -> bytes:
        return b"\x01\x00" * (24000 * 3 // 2)  # 1.5 s


class ProtocolTests(unittest.TestCase):
    def test_handshake_greeting_markers_text_turn_and_events(self):
        from starlette.testclient import TestClient

        import server

        refills.reset_services()
        cid = "proto-1"
        cedar.CONVERSATIONS[cid] = cedar.Conversation(cid, model=ScriptedModel([("text", "Hello. How can I help?")]))

        async def no_asr(self):
            raise RuntimeError("offline")

        with mock.patch.object(server, "TTS", FakeTTS()), mock.patch.object(server.SpeechmaticsASR, "open", no_asr):
            client = TestClient(server.app)
            self.assertEqual(client.get("/health").status_code, 200)
            with client.websocket_connect(server.WS_PATH, headers={"X-Rasa-Sender-Id": cid}) as ws:
                self.assertEqual(ws.receive_json(), {"type": "handshake", "sample_rate": 24000})
                frames = self.until_turn_end(client, ws, cid, 1)
                ws.send_text(json.dumps({"text": "Hi there"}))
                frames += self.until_turn_end(client, ws, cid, 2)
                for f in frames:
                    if "marker" in f:
                        ws.send_text(json.dumps({"marker": f["marker"]}))
            events = client.get(f"/conversations/{cid}/events").json()["events"]
        self.assertEqual([e["event"] for e in events], ["bot", "bot_turn_ended", "user", "bot", "bot_turn_ended"])
        self.assertEqual(events[0]["text"], instructions.GREETING)
        self.assertEqual(events[3]["text"], "Hello. How can I help?")
        ends = [f["latency"] for f in frames if "latency" in f]
        self.assertTrue(ends)
        for latency in ends:
            self.assertEqual(set(latency), {"rasa_processing_latency_ms", "tts_first_byte_latency_ms",
                                            "tts_complete_latency_ms"})
        self.assertTrue(any("audio" in f for f in frames))
        self.assertEqual(client.get("/conversations/nobody/events").json(), {"events": []})

    @staticmethod
    def until_turn_end(client, ws, cid: str, ends: int) -> list[dict]:
        import time

        frames = []
        while True:
            frames.append(ws.receive_json())
            if "latency" in frames[-1]:
                for _ in range(40):
                    doc = client.get(f"/conversations/{cid}/events").json()["events"]
                    if sum(e["event"] == "bot_turn_ended" for e in doc) >= ends:
                        return frames
                    time.sleep(0.05)


class ChunkerTests(unittest.TestCase):
    def test_sentences_are_cut_as_they_complete(self):
        from server import Chunker

        c = Chunker()
        self.assertEqual(c.feed("Your reference is R Q, one"), [])
        self.assertEqual(c.feed(" two. It is awaiting"), ["Your reference is R Q, one two."])
        self.assertEqual(c.flush(), ["It is awaiting"])


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
