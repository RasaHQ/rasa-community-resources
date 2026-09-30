"""The browser_audio server end to end, offline: a scripted model, a fake TTS, typed caller turns.

    uv run --locked python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from starlette.testclient import TestClient  # noqa: E402

import voice_loop  # noqa: E402
from agent import build_agent  # noqa: E402
from cedar_clinic import instructions, refills  # noqa: E402
from fakes import FakeTTS, ScriptedModel, call, say, yes_no_classifier  # noqa: E402
from server import WS_PATH, create_app  # noqa: E402
from voice_loop import split_sentences  # noqa: E402


class SentenceTests(unittest.TestCase):
    def test_complete_sentences_are_cut_and_the_rest_is_kept(self):
        self.assertEqual(split_sentences("Hello there. How are"), (["Hello there."], "How are"))
        self.assertEqual(split_sentences("One! Two? Three"), (["One!", "Two?"], "Three"))
        self.assertEqual(split_sentences("No end yet"), ([], "No end yet"))


def read_until(ws, predicate, limit=400):
    frames = []
    for _ in range(limit):
        frame = json.loads(ws.receive_text())
        frames.append(frame)
        if predicate(frame):
            return frames
    raise AssertionError("condition not met")


class ServerTests(unittest.TestCase):
    def setUp(self):
        refills.reset_services()
        self.model = ScriptedModel()
        self.model.script = []
        self.model.offered = []
        self.tts = FakeTTS()
        self.app = create_app(build_agent(self.model, classify=yes_no_classifier), self.tts, use_asr=False)

    def events(self, client, cid):
        return client.get(f"/conversations/{cid}/events").json()["events"]

    def wait_turn_end(self, client, cid, n):
        for _ in range(200):
            events = self.events(client, cid)
            if sum(e["event"] == "bot_turn_ended" for e in events) >= n:
                return events
            time.sleep(0.02)
        raise AssertionError(f"no bot_turn_ended #{n}: {events}")

    def test_health_and_unknown_conversation(self):
        with TestClient(self.app) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/conversations/nobody/events").json(), {"events": []})

    def test_a_call_with_the_confirmation_question_on_one_turn_and_the_answer_on_the_next(self):
        self.model.script = [
            call("verify_patient", full_name="Maria Alvarez", date_of_birth="1968-03-14"),
            call("select_medication", medication_name="lisinopril"),
            call("send_refill_request", record_id="CC-RX-2041"),
            say("Your request reference is R Q, one two three four. It is awaiting prescribing team review."),
        ]
        cid = "test-call-1"
        with TestClient(self.app) as client:
            with client.websocket_connect(WS_PATH, headers={"X-Rasa-Sender-Id": cid}) as ws:
                self.assertEqual(json.loads(ws.receive_text()), {"type": "handshake", "sample_rate": 24000})
                greeting = read_until(ws, lambda f: "latency" in f)
                self.assertIn("audio", greeting[1])
                for frame in greeting:
                    if "marker" in frame:
                        ws.send_text(json.dumps({"marker": frame["marker"]}))
                self.wait_turn_end(client, cid, 1)

                ws.send_text(json.dumps({"text": "I'm Maria Alvarez, born March 14th, 1968. Lisinopril, please."}))
                events = self.wait_turn_end(client, cid, 2)
                bots = [e["text"] for e in events if e["event"] == "bot"]
                self.assertEqual(bots[0], instructions.GREETING)
                self.assertEqual(bots[1], voice_loop.FILLERS["verify_patient"])
                self.assertEqual(bots[-1], refills.confirmation_question(
                    "lisinopril ten milligram tablets, one tablet once a day"))
                frames = read_until(ws, lambda f: "latency" in f)
                latency = frames[-1]["latency"]
                self.assertEqual(set(latency), {"rasa_processing_latency_ms", "tts_first_byte_latency_ms",
                                                "tts_complete_latency_ms"})

                ws.send_text(json.dumps({"text": "Yes, please send it."}))
                events = self.wait_turn_end(client, cid, 3)
                bots = [e["text"] for e in events if e["event"] == "bot"]
                self.assertTrue(bots[-1].startswith("Your request reference is"))
                users = [e for e in events if e["event"] == "user"]
                self.assertEqual(len(users), 2)

    def test_a_declined_confirmation_speaks_the_shared_decline(self):
        self.model.script = [
            call("verify_patient", full_name="Maria Alvarez", date_of_birth="1968-03-14"),
            call("select_medication", medication_name="albuterol"),
            call("send_refill_request", record_id="CC-RX-2043"),
            say("Is there anything else I can help with?"),
        ]
        cid = "test-call-2"
        with TestClient(self.app) as client:
            with client.websocket_connect(WS_PATH, headers={"X-Rasa-Sender-Id": cid}) as ws:
                ws.receive_text()
                self.wait_turn_end(client, cid, 1)
                ws.send_text(json.dumps({"text": "Maria Alvarez, March 14th, 1968, my albuterol inhaler."}))
                self.wait_turn_end(client, cid, 2)
                ws.send_text(json.dumps({"text": "No."}))
                events = self.wait_turn_end(client, cid, 3)
                bots = [e["text"] for e in events if e["event"] == "bot"]
                self.assertIn(refills.DECLINED_TEXT, bots)

    def test_barge_in_is_off(self):
        self.assertFalse(voice_loop.INTERRUPTIONS_ENABLED)
        self.assertEqual(voice_loop.SILENCE_TIMEOUT_S, 30.0)


if __name__ == "__main__":
    unittest.main()
