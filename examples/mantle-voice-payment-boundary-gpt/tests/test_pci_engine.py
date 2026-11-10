"""Offline checks for the card-redacting Deepgram engine. Needs the project's venv (it imports Rasa); skipped otherwise.

    uv run --locked python -m unittest tests.test_pci_engine -v

Feeds the engine Deepgram Flux (v2) frames as Rasa's websocket loop would and
checks what Rasa receives. No network: the engine is never connected.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

try:
    os.environ.setdefault("DEEPGRAM_API_KEY", "offline-test")
    from engines import deepgram_pci
    from rasa.core.channels.voice_stream.asr.asr_event import NewTranscript, UserIsSpeaking
    from rasa.core.channels.voice_stream.asr.deepgram import DeepgramASR
    from rasa.core.channels.voice_stream.audio_bytes import L16_16KHZ
except ImportError:  # plain python3 without the project's venv
    deepgram_pci = None

from lib import payments as wp  # noqa: E402
from lib.pci import PLACEHOLDER  # noqa: E402

CONFIG = {"language_map": {"en": {"model": "flux-general-en"}}, "eot_threshold": 0.7, "eot_timeout_ms": 5000}


def turn(event: str, transcript: str = "") -> str:
    return json.dumps({"type": "TurnInfo", "event": event, "transcript": transcript})


@unittest.skipIf(deepgram_pci is None, "Rasa is not importable; run with the project's venv")
class RedactingEngineTests(unittest.TestCase):
    def engine(self):
        os.environ.pop(wp.REDACTION_FLAG, None)
        return deepgram_pci.DeepgramRedactingCardDetails.from_config_dict(CONFIG, L16_16KHZ, "en")

    def said(self, engine, transcript: str):
        events = [engine.engine_event_to_asr_event(turn("StartOfTurn")),
                  engine.engine_event_to_asr_event(turn("Update", transcript)),
                  engine.engine_event_to_asr_event(turn("EndOfTurn", transcript))]
        return [e for e in events if e is not None]

    def test_is_the_built_in_flux_engine(self):
        engine = self.engine()
        self.assertIsInstance(engine, DeepgramASR)
        self.assertEqual(engine.name(), "deepgram")
        self.assertEqual(engine.config.version, "v2")

    def test_creating_it_marks_the_recorder_excluded(self):
        self.engine()
        self.assertTrue(wp.redaction_active())

    def test_card_number_never_reaches_rasa(self):
        engine = self.engine()
        partial, final = self.said(engine, "my card number is 4111 1111 1111 1111")
        self.assertIsInstance(partial, UserIsSpeaking)
        self.assertIsInstance(final, NewTranscript)
        for event in (partial, final):
            self.assertEqual(event.text, f"my card number is {PLACEHOLDER}")
        self.assertEqual(engine.removals, 1)

    def test_second_breath_is_removed_then_the_order_number_is_kept(self):
        engine = self.engine()
        self.said(engine, "card number four one one one, one one one one")
        _, final = self.said(engine, "one one one one, one one one one")
        self.assertEqual(final.text, PLACEHOLDER)
        _, final = self.said(engine, "1111")
        self.assertEqual(final.text, PLACEHOLDER)
        _, final = self.said(engine, "okay text me the link for W S one zero five one seven")
        self.assertEqual(final.text, "okay text me the link for W S one zero five one seven")

    def test_ordinary_turns_pass_unchanged(self):
        engine = self.engine()
        _, final = self.said(engine, "Yes, send it.")
        self.assertEqual(final.text, "Yes, send it.")
        self.assertEqual(engine.removals, 0)


if __name__ == "__main__":
    unittest.main()
