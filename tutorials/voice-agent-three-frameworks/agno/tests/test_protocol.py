import unittest
import json
from unittest import mock
from cedar_clinic import refills, instructions
import agent as cedar
from test_agent import ScriptedModel

class FakeTTS:
    async def synthesize(self, text: str) -> bytes:
        return b"\x01\x00" * (24000 * 3 // 2)  # 1.5 s


class ProtocolTests(unittest.TestCase):
    def test_handshake_greeting_markers_text_turn_and_events(self):
        from starlette.testclient import TestClient

        import server

        refills.reset_services()
        cid = "proto-1"
        cedar.CONVERSATIONS[cid] = cedar.Conversation(cid, model=ScriptedModel(["Hello. How can I help?"]))

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
