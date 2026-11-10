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


class DeepgramVariantTests(unittest.TestCase):
    """The speech variants in ../variants/ and shared/speech-deepgram make the same Deepgram calls.

    Not the shipped build: these files are only used through `make rasa-variant`.
    """

    def setUp(self):
        self._saved = os.environ.get("DEEPGRAM_API_KEY")
        os.environ["DEEPGRAM_API_KEY"] = "test-key"
        sys.path.insert(0, str(TUTORIAL / "shared" / "speech-deepgram"))

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("DEEPGRAM_API_KEY", None)
        else:
            os.environ["DEEPGRAM_API_KEY"] = self._saved

    @staticmethod
    def variant(name: str) -> dict:
        return yaml.safe_load((TUTORIAL / "variants" / f"rasa-{name}.integrations.yml").read_text())

    def test_variants_differ_from_the_build_only_in_speech_engines(self):
        shipped = yaml.safe_load((PROJECT / "integrations.yml").read_text())
        for name, changed in (("deepgram-tts", {"tts"}), ("deepgram", {"asr", "tts"})):
            variant = self.variant(name)
            self.assertEqual(variant["model_groups"], shipped["model_groups"])
            for ch in ("browser_audio", "inspector"):
                a, b = shipped["channels"][ch], variant["channels"][ch]
                self.assertEqual({k: v for k, v in a.items() if k not in changed},
                                 {k: v for k, v in b.items() if k not in changed}, (name, ch))
                for key in changed:
                    self.assertEqual(b[key]["name"], "deepgram", (name, ch, key))
            if name == "deepgram-tts":
                self.assertEqual(variant["channels"]["browser_audio"]["asr"], shipped["channels"]["browser_audio"]["asr"])

    def test_builtin_deepgram_tts_streams_text_input(self):
        from rasa.core.channels.voice_stream.tts.deepgram import DeepgramTTS

        from cedar_speech_deepgram import config as dg

        cfg = dict(self.variant("deepgram-tts")["channels"]["browser_audio"]["tts"])
        cfg.pop("name")
        tts = DeepgramTTS.from_config_dict(cfg, L16_24KHZ, "en")
        self.assertTrue(tts.streaming_input)
        url = tts.get_websocket_url(tts.config)
        self.assertEqual(url.split("?")[0], dg.TTS_ENDPOINT)
        self.assertEqual(dict(p.split("=") for p in url.split("?")[1].split("&")),
                         {k: str(v) for k, v in dg.tts_query().items()})

    def test_builtin_deepgram_asr_query_matches_the_shared_client(self):
        from rasa.core.channels.voice_stream.asr.deepgram import DeepgramASR

        from cedar_speech_deepgram import config as dg

        cfg = dict(self.variant("deepgram")["channels"]["browser_audio"]["asr"])
        cfg.pop("name")
        asr = DeepgramASR.from_config_dict(cfg, L16_24KHZ, "en")
        self.assertEqual(asr._get_api_url().rstrip("?"), dg.ASR_ENDPOINT)
        self.assertEqual(dict(p.split("=") for p in asr._get_query_params().split("&")),
                         {k: str(v) for k, v in dg.asr_query().items()})

    def test_builtin_and_shared_readers_join_turns_identically(self):
        from rasa.core.channels.voice_stream.asr.deepgram import DeepgramASR

        from cedar_speech_deepgram.asr import ResultsReader

        cfg = dict(self.variant("deepgram")["channels"]["browser_audio"]["asr"])
        cfg.pop("name")
        asr = DeepgramASR.from_config_dict(cfg, L16_24KHZ, "en")
        reader = ResultsReader()

        def res(text, is_final, speech_final=False):
            return json.dumps({"type": "Results", "is_final": is_final, "speech_final": speech_final,
                               "channel": {"alternatives": [{"transcript": text}]}})

        frames = [res("I'm Maria", False), res("I'm Maria Alvarez,", True), res("born March", False),
                  res("born March 14th, 1968.", True, True), res("", True, True), res("Yes.", True),
                  json.dumps({"type": "UtteranceEnd"}), json.dumps({"type": "SpeechStarted"})]
        for frame in frames:
            ours = reader.read(frame)
            theirs = asr.engine_event_to_asr_event(frame)
            if theirs is None:
                self.assertIsNone(ours, frame)
            elif isinstance(theirs, NewTranscript):
                self.assertEqual(ours, ("final", theirs.text), frame)
            else:
                self.assertIsInstance(theirs, UserIsSpeaking)
                self.assertEqual(ours, ("partial", theirs.text), frame)


if __name__ == "__main__":
    unittest.main()
