"""Live round trip on Speechmatics: TTS speaks a sentence, realtime ASR hears a caller fixture.

Billed (a few seconds of realtime audio; TTS is in free preview). Skipped
unless SPEECHMATICS_API_KEY is set; the key is taken from the environment or
the repository's .env the same way the companion's tooling loads it, and
never printed.

    uv run python -m unittest tests.test_live -v
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import os
import re
import sys
import time
import unittest
import wave
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[5] / "scripts"))

with contextlib.redirect_stdout(io.StringIO()):
    from check_project import _load_dotenv  # noqa: E402

    _load_dotenv(HERE.parents[3] / "rasa")

from cedar_speech import SpeechmaticsASR, SpeechmaticsTTS, config  # noqa: E402

CALLER = HERE.parents[2] / "spec" / "caller-audio" / "aura-2-athena-en-627c5676d6dc.wav"


@unittest.skipUnless(os.environ.get(config.API_KEY_ENV_VAR), f"{config.API_KEY_ENV_VAR} not set")
class LiveTests(unittest.TestCase):
    def test_tts_returns_speech_at_the_wire_rate(self):
        async def run():
            tts = SpeechmaticsTTS()
            try:
                return await tts.synthesize("Your request reference is R Q, two three six seven."), tts.last_timings
            finally:
                await tts.close()

        pcm, timings = asyncio.run(run())
        self.assertGreater(len(pcm) / 2 / config.SAMPLE_RATE, 1.5)
        print(f"\n  TTS: {timings}")

    def test_asr_hears_a_caller_fixture_as_one_utterance(self):
        with wave.open(str(CALLER)) as w:
            self.assertEqual(w.getframerate(), config.SAMPLE_RATE)
            pcm = w.readframes(w.getnframes())

        async def run():
            finals, partials = [], 0
            async with SpeechmaticsASR() as asr:
                async def pump():
                    frame = config.SAMPLE_RATE // 50 * 2
                    for chunk in [pcm[i:i + frame] for i in range(0, len(pcm), frame)] + [b"\x00" * frame] * 150:
                        await asr.send_audio(chunk)
                        await asyncio.sleep(0.02)

                feeder = asyncio.create_task(pump())
                began = time.monotonic()

                async def listen():
                    nonlocal partials
                    async for event in asr.events():
                        if event.final:
                            finals.append(event.text)
                            return
                        partials += 1

                await asyncio.wait_for(listen(), timeout=30)
                feeder.cancel()
                return finals, partials, time.monotonic() - began, asr.audio_seconds

        finals, partials, took, seconds = asyncio.run(run())
        text = re.sub(r"[^a-z0-9 ]", " ", " ".join(finals).lower())
        self.assertEqual(len(finals), 1)
        for word in ("maria", "lisinopril", "refill"):
            self.assertIn(word, text, finals)
        print(f"\n  ASR final: {finals}  partials: {partials}  audio sent: {seconds:.1f} s  wall: {took:.1f} s")


if __name__ == "__main__":
    unittest.main()
