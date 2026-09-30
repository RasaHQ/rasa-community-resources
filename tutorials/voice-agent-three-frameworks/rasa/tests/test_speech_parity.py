"""The Rasa version and shared/speech make identical Speechmatics calls.

The Rasa version reaches Speechmatics through its custom engine classes
(engines/speechmatics.py); the LangGraph and Strands versions through
shared/speech (cedar_speech). Offline: the same settings, the same
StartRecognition message, the same reply handling, the same TTS request and
the same audio conversion. No network.
"""

from __future__ import annotations

import asyncio
import json
import os
import struct
import sys
import unittest
from pathlib import Path

import yaml

PROJECT = Path(__file__).resolve().parent.parent
TUTORIAL = PROJECT.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(TUTORIAL / "shared" / "speech"))

from cedar_speech import audio as shared_audio  # noqa: E402
from cedar_speech import config as shared_config  # noqa: E402
from cedar_speech import protocol  # noqa: E402
from engines import speechmatics as engine  # noqa: E402
from rasa.core.channels.voice_stream.asr.asr_event import NewTranscript, UserIsSpeaking  # noqa: E402
from rasa.core.channels.voice_stream.audio_bytes import L16_24KHZ  # noqa: E402


_SAVED_KEY = None


def setUpModule():  # noqa: N802
    # The engines refuse to build without the key; these tests never call out.
    global _SAVED_KEY
    _SAVED_KEY = os.environ.get("SPEECHMATICS_API_KEY")
    os.environ["SPEECHMATICS_API_KEY"] = "test-key"


def tearDownModule():  # noqa: N802
    if _SAVED_KEY is None:
        os.environ.pop("SPEECHMATICS_API_KEY", None)
    else:
        os.environ["SPEECHMATICS_API_KEY"] = _SAVED_KEY


def channel() -> dict:
    return yaml.safe_load((PROJECT / "integrations.yml").read_text())["channels"]["browser_audio"]


class SettingsTests(unittest.TestCase):
    def test_asr_settings_match(self):
        asr = channel()["asr"]
        self.assertEqual(asr["endpoint"], shared_config.ASR_ENDPOINT)
        for key in ("operating_point", "max_delay", "enable_partials", "end_of_utterance_silence_trigger"):
            self.assertEqual(asr[key], shared_config.ASR_SETTINGS[key], key)
        self.assertEqual(asr["language_map"]["en"]["language"], shared_config.ASR_SETTINGS["language"])
        self.assertEqual(asr["additional_vocab"], shared_config.ADDITIONAL_VOCAB)

    def test_tts_settings_match(self):
        c = channel()
        tts = c["tts"]
        self.assertEqual(c["sample_rate"], shared_config.SAMPLE_RATE)
        self.assertEqual(tts["endpoint"], shared_config.TTS_ENDPOINT)
        self.assertEqual(tts["output_format"], shared_config.TTS_OUTPUT_FORMAT)
        self.assertEqual(tts["language_map"]["en"]["voice"], shared_config.TTS_VOICE)

    def test_inspector_uses_the_same_engines(self):
        channels = yaml.safe_load((PROJECT / "integrations.yml").read_text())["channels"]
        self.assertEqual(channels["inspector"]["asr"], channels["browser_audio"]["asr"])
        self.assertEqual(channels["inspector"]["tts"], channels["browser_audio"]["tts"])


class MessageParityTests(unittest.TestCase):
    def asr_engine(self):
        return engine.SpeechmaticsASR.from_config_dict(channel()["asr"], L16_24KHZ, "en")

    def test_start_recognition_is_identical(self):
        self.assertEqual(self.asr_engine()._start_recognition_message(), protocol.start_recognition())

    def test_replies_are_read_identically(self):
        rasa_engine = self.asr_engine()
        reader = protocol.ReplyReader(utterance_mode=True)
        replies = [
            {"message": "RecognitionStarted"},
            {"message": "AddPartialTranscript", "metadata": {"transcript": ""}},
            {"message": "AddPartialTranscript", "metadata": {"transcript": "Hi this"}},
            {"message": "AddTranscript", "metadata": {"transcript": "Hi, this is"}},
            {"message": "AddTranscript", "metadata": {"transcript": "Theo Lindqvist."}},
            {"message": "EndOfUtterance"},
            {"message": "EndOfUtterance"},
            {"message": "AddTranscript", "metadata": {"transcript": "Yes."}},
            {"message": "EndOfUtterance"},
        ]
        for reply in replies:
            raw = json.dumps(reply)
            ours = rasa_engine.engine_event_to_asr_event(raw)
            theirs = reader.read(raw)
            if ours is None:
                self.assertIsNone(theirs, reply)
            elif isinstance(ours, NewTranscript):
                self.assertEqual(theirs, ("final", ours.text), reply)
            else:
                self.assertIsInstance(ours, UserIsSpeaking)
                self.assertEqual(theirs[0], "partial", reply)

    def test_tts_request_is_identical(self):
        tts = engine.SpeechmaticsTTS.from_config_dict(channel()["tts"], L16_24KHZ, "en")
        tts._set_current_language_config("en")
        self.assertEqual(tts.request("Hello."), protocol.tts_request("Hello.", "test-key"))

    def test_audio_conversion_is_identical(self):
        pcm = b"".join(struct.pack("<h", (i * 97) % 20000 - 10000) for i in range(16000))
        fmt = struct.pack("<HHIIHH", 1, 1, 16000, 32000, 2, 16)
        wav = b"RIFF" + struct.pack("<I", 0xFFFFFFFF) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"data" \
            + struct.pack("<I", 0xFFFFFFFF) + pcm
        ours = engine.to_rasa_audio(wav, 16000, L16_24KHZ).data
        self.assertEqual(ours, shared_audio.wav_to_pcm(wav, 16000, 24000))


if __name__ == "__main__":
    unittest.main()
