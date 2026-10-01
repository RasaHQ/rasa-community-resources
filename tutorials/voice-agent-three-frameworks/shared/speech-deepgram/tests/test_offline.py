"""Offline checks for cedar_speech_deepgram: query, turn joining, TTS messages, the launcher. No network.

    cd ../speech && uv run --python 3.12 python -m unittest discover -s ../speech-deepgram/tests -v
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from websockets.asyncio.server import serve  # noqa: E402

from cedar_speech_deepgram import DeepgramASR, DeepgramTTS, config  # noqa: E402
from cedar_speech_deepgram.asr import ResultsReader  # noqa: E402


def results(text: str, is_final: bool, speech_final: bool = False) -> str:
    return json.dumps({"type": "Results", "is_final": is_final, "speech_final": speech_final,
                       "channel": {"alternatives": [{"transcript": text}]}})


class QueryTests(unittest.TestCase):
    def test_listen_query_is_rasas_default(self):
        self.assertEqual(config.asr_query(), {
            "encoding": "linear16", "sample_rate": 24000, "endpointing": 400, "vad_events": "true",
            "language": "en", "interim_results": "true", "model": "nova-3", "smart_format": "true",
            "utterance_end_ms": 1000})

    def test_speak_query(self):
        self.assertEqual(config.tts_query(), {"model": "aura-2-thalia-en", "encoding": "linear16",
                                              "sample_rate": 24000})


class ReaderTests(unittest.TestCase):
    def test_finals_are_held_until_speech_final(self):
        r = ResultsReader()
        self.assertEqual(r.read(results("I need", False)), ("partial", "I need"))
        self.assertIsNone(r.read(results("I need a refill", True)))
        self.assertEqual(r.read(results("of my lisinopril.", True, speech_final=True)),
                         ("final", "I need a refill of my lisinopril."))
        self.assertEqual(r.held, "")

    def test_utterance_end_flushes_what_was_held(self):
        r = ResultsReader()
        r.read(results("Maria Alvarez", True))
        self.assertEqual(r.read(json.dumps({"type": "UtteranceEnd"})), ("final", "Maria Alvarez"))
        self.assertIsNone(r.read(json.dumps({"type": "UtteranceEnd"})))

    def test_empty_and_other_frames(self):
        r = ResultsReader()
        self.assertIsNone(r.read(results("", False)))
        self.assertIsNone(r.read(results("", True, speech_final=True)))
        self.assertIsNone(r.read(json.dumps({"type": "SpeechStarted"})))
        self.assertEqual(r.read(json.dumps({"type": "Error", "description": "bad"})), ("error", "bad"))


class SocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_asr_sends_audio_and_closes_with_closestream(self):
        seen: list = []

        async def handler(ws):
            seen.append(ws.request.headers.get("Authorization"))
            async for msg in ws:
                seen.append(msg)
                if isinstance(msg, bytes):
                    await ws.send(results("Yes, send it.", True, speech_final=True))
                elif json.loads(msg).get("type") == "CloseStream":
                    break

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            asr = await DeepgramASR(endpoint=f"ws://127.0.0.1:{port}", api_key="k").open()
            await asr.send_audio(b"\x00\x00" * 480)
            event = await asyncio.wait_for(anext(asr.events()), 5)
            await asr.close()
        self.assertEqual((event.text, event.final), ("Yes, send it.", True))
        self.assertEqual(seen[0], "Token k")
        self.assertAlmostEqual(asr.audio_seconds, 0.02)
        self.assertEqual(json.loads(seen[-1]), {"type": "CloseStream"})

    async def test_tts_speaks_flushes_and_reconnects(self):
        got: list = []

        async def handler(ws):
            async for msg in ws:
                got.append(json.loads(msg))
                if got[-1]["type"] == "Flush":
                    await ws.send(b"\x01\x00" * 100)
                    await ws.send(b"\x02\x00" * 50)
                    await ws.send(json.dumps({"type": "Flushed"}))
                    await ws.close()   # as if Deepgram closed the idle socket

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            tts = DeepgramTTS(endpoint=f"ws://127.0.0.1:{port}", api_key="k")
            first = await tts.synthesize("Hello.")
            second = await tts.synthesize("Again.")
            await tts.close()
        self.assertEqual(len(first), 300)
        self.assertEqual(len(second), 300)
        self.assertEqual(got, [{"type": "Speak", "text": "Hello."}, {"type": "Flush"},
                               {"type": "Speak", "text": "Again."}, {"type": "Flush"}])
        self.assertEqual(tts.characters, len("Hello.") + len("Again."))


class LauncherTests(unittest.TestCase):
    def test_server_sees_the_deepgram_classes_under_the_speechmatics_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = Path(tmp) / "server.py"
            server.write_text("import sys\nfrom cedar_speech import SpeechmaticsASR, SpeechmaticsTTS\n"
                              "print(SpeechmaticsASR.__name__, SpeechmaticsTTS.__name__, sys.argv[1:])\n")
            out = subprocess.run([sys.executable, str(HERE / "launch.py"), "server.py", "--port", "1"], cwd=tmp,
                                 capture_output=True, text=True, check=True).stdout
        self.assertIn("DeepgramASR DeepgramTTS ['--port', '1']", out)


if __name__ == "__main__":
    unittest.main()
