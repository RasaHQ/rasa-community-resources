"""Offline checks for cedar_speech: the vendor messages, reply handling and audio. No network.

    uv run python -m unittest tests.test_offline -v
"""

from __future__ import annotations

import array
import json
import math
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cedar_speech import audio, config, protocol  # noqa: E402


def wav(pcm: bytes, rate: int, data_size: int | None = None) -> bytes:
    size = len(pcm) if data_size is None else data_size
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt
            + b"data" + struct.pack("<I", size) + pcm)


class StartRecognitionTests(unittest.TestCase):
    def test_default_message(self):
        msg = protocol.start_recognition()
        self.assertEqual(msg["message"], "StartRecognition")
        self.assertEqual(msg["audio_format"], {"type": "raw", "encoding": "pcm_s16le", "sample_rate": 24000})
        tc = msg["transcription_config"]
        self.assertEqual((tc["language"], tc["operating_point"], tc["max_delay"], tc["enable_partials"]),
                         ("en", "enhanced", 1.0, True))
        self.assertEqual(tc["conversation_config"], {"end_of_utterance_silence_trigger": 0.7})
        self.assertEqual([v["content"] for v in tc["additional_vocab"]], config.ADDITIONAL_VOCAB)

    def test_no_trigger_no_vocab(self):
        tc = protocol.start_recognition(end_of_utterance_silence_trigger=None, additional_vocab=[])[
            "transcription_config"]
        self.assertNotIn("conversation_config", tc)
        self.assertNotIn("additional_vocab", tc)

    def test_end_of_stream_counts_audio_messages(self):
        self.assertEqual(protocol.end_of_stream(12), {"message": "EndOfStream", "last_seq_no": 12})


class ReplyReaderTests(unittest.TestCase):
    @staticmethod
    def msg(kind, text=None):
        body = {"message": kind}
        if text is not None:
            body["metadata"] = {"transcript": text}
        return json.dumps(body)

    def test_segments_join_at_end_of_utterance(self):
        r = protocol.ReplyReader(utterance_mode=True)
        got = [r.read(self.msg("AddPartialTranscript", "")), r.read(self.msg("AddPartialTranscript", "Hi this")),
               r.read(self.msg("AddTranscript", "Hi, this is")), r.read(self.msg("AddTranscript", "Maria.")),
               r.read(self.msg("EndOfUtterance")), r.read(self.msg("EndOfUtterance"))]
        self.assertEqual(got, [None, ("partial", "Hi this"), ("partial", "Hi, this is"),
                               ("partial", "Hi, this is Maria."), ("final", "Hi, this is Maria."), None])

    def test_segment_mode_without_trigger(self):
        r = protocol.ReplyReader(utterance_mode=False)
        self.assertEqual(r.read(self.msg("AddTranscript", "Yes.")), ("final", "Yes."))

    def test_errors_and_noise(self):
        r = protocol.ReplyReader()
        self.assertEqual(r.read(json.dumps({"message": "Error", "type": "not_authorised", "reason": "x"})),
                         ("error", "not_authorised: x"))
        self.assertIsNone(r.read("not json"))
        self.assertIsNone(r.read(json.dumps({"message": "RecognitionStarted"})))


class TTSRequestTests(unittest.TestCase):
    def test_request_shape(self):
        url, headers, body = protocol.tts_request("Hello.", "k", voice="megan")
        self.assertEqual(url, "https://preview.tts.speechmatics.com/generate/megan?output_format=wav_16000")
        self.assertEqual(headers, {"Authorization": "Bearer k"})
        self.assertEqual(body, {"text": "Hello."})


class AudioTests(unittest.TestCase):
    def test_streaming_wav_with_placeholder_size_is_read_to_the_end(self):
        pcm = array.array("h", (int(8000 * math.sin(i / 5)) for i in range(1600))).tobytes()
        got, rate = audio.strip_wav_header(wav(pcm, 16000, data_size=0xFFFFFFFF))
        self.assertEqual((got, rate), (pcm, 16000))

    def test_resampled_to_the_wire_rate(self):
        pcm = b"\x10\x00" * 16000  # one second at 16 kHz
        out = audio.wav_to_pcm(wav(pcm, 16000), 16000, 24000)
        self.assertAlmostEqual(len(out) / 2 / 24000, 1.0, delta=0.01)

    def test_frames(self):
        self.assertEqual([len(f) for f in audio.frames(b"\x00" * 2000, 24000)], [960, 960, 80])


if __name__ == "__main__":
    unittest.main()
