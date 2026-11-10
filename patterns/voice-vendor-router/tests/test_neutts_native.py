#!/usr/bin/env python3
"""Unit tests for the native NeuTTS engine. No model, no native binaries, no network.

What is tested is what the engine decides on its own: the prompt it builds,
how it splits text, how it turns a stream of codes into gap-free audio, and
that it drives the runtime the way Rasa's TTS contract expects. The native
programs are replaced by a fake that "decodes" each code to a known ramp.

    make test
"""

from __future__ import annotations

import array
import asyncio
import json
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voicerouter.engine import L16_16KHZ, L16_24KHZ  # noqa: E402

from voicerouter.providers import neutts_native as nn  # noqa: E402

HOP = nn.HOP_SAMPLES


def fake_decode(codes, start, end):
    """Each code becomes one frame of constant value code/1000; NeuCodec drops one frame."""
    samples = []
    for code in codes[:-1]:
        samples.extend([code / 1000.0] * HOP)
    end = min(end, len(samples))
    return array.array("f", samples[start:end])


def pcm_values(pcm: bytes) -> list[int]:
    return list(struct.unpack(f"<{len(pcm) // 2}h", pcm))


class PromptTests(unittest.TestCase):
    def test_prompt_is_neutts_2e_format(self):
        got = nn.build_prompt("Ref text.", [7, 8], "Hello ’world’")
        self.assertEqual(
            got,
            "<|TEXT_PROMPT_START|>Ref text. Hello 'world'<|TEXT_PROMPT_END|>"
            "<|SPEECH_GENERATION_START|><|speech_7|><|speech_8|>",
        )

    def test_emotion_token_replaces_the_space(self):
        self.assertIn("Ref.<|HAPPY|>Hi", nn.build_prompt("Ref.", [1], "Hi", "happy"))
        self.assertIn("Ref. Hi", nn.build_prompt("Ref.", [1], "Hi", "neutral"))

    def test_segments_pack_sentences_and_keep_long_ones_whole(self):
        self.assertEqual(nn.split_segments("One. Two! Three?", 100), ["One. Two! Three?"])
        self.assertEqual(nn.split_segments("One two. Three four.", 9), ["One two.", "Three four."])
        long = "word " * 60
        self.assertEqual(len(nn.split_segments(long, 50)), 1)
        self.assertEqual(nn.split_segments("   ", 50), [])

    def test_generation_cap_stays_inside_the_context(self):
        self.assertEqual(nn.max_speech_tokens("x" * 1000, 2048, 300), 2048 - 300 - 8)
        self.assertGreaterEqual(nn.max_speech_tokens("Hi.", 2048, 200), 150)


class SpellNumbersTests(unittest.TestCase):
    """NeuTTS-2E babbles on numerals, so the engine says them in words."""

    def test_references_and_amounts(self):
        self.assertEqual(nn.spell_numbers("R Q, 6 1 5 0."), "R Q, six one five zero.")
        self.assertEqual(nn.spell_numbers("RQ-4417"), "RQ-four four one seven")
        self.assertEqual(nn.spell_numbers("take 10 mg, not 115"), "take ten mg, not one hundred fifteen")
        self.assertEqual(nn.spell_numbers("0.5 mg"), "zero point five mg")
        self.assertEqual(nn.spell_numbers("no digits here"), "no digits here")

    def test_engine_spells_before_it_prompts(self):
        prompts = []
        engine = nn.NeuTTSNative.from_config_dict({}, L16_24KHZ, "en")
        engine._runtime = FakeRuntime()

        async def fake_generate(prompt, n_predict):
            prompts.append(prompt)
            yield [400] * 40

        async def run():
            engine._generate = fake_generate
            engine.connect = _noop
            return [c async for c in engine.synthesize("Reference 6 1 5 0.")]

        asyncio.run(run())
        self.assertIn("Reference six one five zero.", prompts[0])


class Pcm16Tests(unittest.TestCase):
    def test_clipping_and_scale(self):
        self.assertEqual(pcm_values(nn.float_to_pcm16([0.0, 1.0, -1.0, 2.0, -3.0, 0.5])),
                         [0, 32767, -32767, 32767, -32767, 16384])


class StreamAssemblerTests(unittest.TestCase):
    def run_stream(self, generated, ref=None, **kw):
        ref = ref if ref is not None else list(range(1000, 1060))
        a = nn.StreamAssembler(ref, fake_decode, **kw)
        chunks = []
        for code in generated:
            chunks.extend(a.push([code]))
        chunks.append(a.finish())
        return a, chunks

    def test_constant_signal_comes_out_whole_and_unchanged(self):
        # Every generated code decodes to the same value, so a correct
        # cross-fade must return exactly that value for every sample.
        generated = [500] * 93
        a, chunks = self.run_stream(generated)
        values = [v for c in chunks for v in pcm_values(c)]
        self.assertEqual(set(values), {round(0.5 * 32767)})
        # All generated frames but the codec's dropped last one are released.
        self.assertEqual(len(values), (len(generated) - 1) * HOP)

    def test_first_chunk_waits_for_lookforward(self):
        a = nn.StreamAssembler([1] * 60, fake_decode, first_chunk_frames=10, chunk_frames=25, lookforward=5)
        self.assertEqual(a.push([2] * 14), [])
        out = a.push([2])
        self.assertEqual(len(out), 1)
        self.assertEqual(len(pcm_values(out[0])), 10 * HOP)

    def test_audio_is_in_order_and_has_no_gap_or_overlap(self):
        # A ramp: frame i of the generated speech has value i. Released audio
        # must visit every frame once, in order (cross-fades only mix
        # neighbouring frames).
        generated = list(range(1, 121))
        a, chunks = self.run_stream(generated, ref=[0] * 60)
        values = [v for c in chunks for v in pcm_values(c)]
        self.assertEqual(len(values), (len(generated) - 1) * HOP)
        frames = [values[i * HOP] for i in range(len(values) // HOP)]
        self.assertEqual(frames, sorted(frames))
        self.assertEqual(frames[0], round(1 / 1000 * 32767))

    def test_short_utterance_is_one_final_chunk(self):
        a, chunks = self.run_stream([300] * 12)
        self.assertEqual(a.chunks_decoded, 1)
        self.assertEqual(len(b"".join(chunks)) // 2, 11 * HOP)

    def test_lookback_uses_the_reference_codes(self):
        seen = []

        def spy(codes, start, end):
            seen.append((list(codes), start, end))
            return fake_decode(codes, start, end)

        ref = list(range(2000, 2060))
        a = nn.StreamAssembler(ref, spy)
        a.push([7] * 30)
        codes, start, end = seen[0]
        self.assertEqual(codes[:51], ref[-51:])
        self.assertEqual(start, 51 * HOP)
        self.assertEqual(end - start, 27 * HOP)


class FakeRuntime:
    started = True
    server_url = "http://127.0.0.1:1"
    context_tokens = 2048

    def __init__(self):
        self.decode_calls = 0

    def speaker(self, name):
        assert name == "sophie"
        return "Reference.", list(range(100, 160))

    def decode(self, codes, start, end):
        self.decode_calls += 1
        return fake_decode(codes, start, end)


class EngineTests(unittest.TestCase):
    def make(self, fmt=L16_24KHZ, **config):
        engine = nn.NeuTTSNative.from_config_dict(config, fmt, "en")
        engine._runtime = FakeRuntime()
        engine._session = object()
        return engine

    def synth(self, engine, text, codes_per_event=1, n=80):
        async def fake_generate(prompt, n_predict):
            self.assertIn(text.split()[0], prompt)
            codes = [400] * n
            for i in range(0, len(codes), codes_per_event):
                yield codes[i:i + codes_per_event]

        engine._generate = fake_generate

        async def run():
            engine.connect = _noop  # the runtime is faked
            return [chunk async for chunk in engine.synthesize(text)]

        return asyncio.run(run())

    def test_streams_audio_in_the_channel_format(self):
        engine = self.make()
        chunks = self.synth(engine, "Hello there.")
        self.assertGreater(len(chunks), 1)
        total = sum(len(c.data) for c in chunks) // 2
        self.assertEqual(total, 79 * HOP)
        self.assertTrue(all(c.format == L16_24KHZ for c in chunks))
        self.assertEqual(engine.last_timings["segments"], 1)
        self.assertIsNotNone(engine.last_timings["first_audio_s"])

    def test_resamples_for_a_16khz_channel(self):
        chunks = self.synth(self.make(fmt=L16_16KHZ), "Hello there.")
        total = sum(len(c.data) for c in chunks) // 2
        self.assertAlmostEqual(total, 79 * HOP * 2 / 3, delta=4)

    def test_no_codes_is_an_error_not_silence(self):
        engine = self.make()
        with self.assertRaises(nn.TTSError):
            self.synth(engine, "Hello.", n=0)

    def test_default_voice_is_sophie_and_no_credentials_are_needed(self):
        engine = nn.NeuTTSNative.from_config_dict({}, L16_24KHZ, "en")
        self.assertEqual(engine._speaker_name(), "sophie")
        self.assertEqual(nn.NeuTTSNative.required_env_vars, ())
        self.assertEqual(nn.NeuTTSNative.name(), "neutts-native")

    def test_engine_has_the_contract_rasa_calls(self):
        engine = nn.NeuTTSNative.from_config_dict({}, L16_24KHZ, "en")
        for attr in ("config", "__aenter__", "__aexit__", "connect", "close_connection", "synthesize"):
            self.assertTrue(hasattr(engine, attr), attr)
        self.assertFalse(engine.streaming_input)


class RuntimeDecodeProtocolTests(unittest.TestCase):
    """The binary protocol spoken to neucodec_decoder --serve, against a fake child."""

    def test_request_and_reply_framing(self):
        import io

        reply_samples = array.array("f", [0.25, -0.5])
        reply = b"NCDA" + struct.pack("<II", 0, 2) + reply_samples.tobytes()

        class Child:
            def __init__(self):
                self.stdin = io.BytesIO()
                self.stdout = io.BytesIO(reply)

            def poll(self):
                return None

        runtime = nn.NativeRuntime(Path("."), Path("."), Path("b"), Path("d"), None, 99, 2048, 4, False, 1.0)
        runtime._decoder = Child()
        got = runtime.decode([5, 6, 7], 10, 20)
        self.assertEqual(list(got), [0.25, -0.5])
        sent = runtime._decoder.stdin.getvalue()
        self.assertEqual(sent[:4], b"NCDQ")
        self.assertEqual(struct.unpack("<III", sent[4:16]), (3, 10, 20))
        self.assertEqual(struct.unpack("<3i", sent[16:]), (5, 6, 7))

    def test_error_reply_raises(self):
        import io

        class Child:
            stdin = io.BytesIO()
            stdout = io.BytesIO(b"NCDA" + struct.pack("<II", 1, 4) + b"boom")

            def poll(self):
                return None

        runtime = nn.NativeRuntime(Path("."), Path("."), Path("b"), Path("d"), None, 99, 2048, 4, False, 1.0)
        runtime._decoder = Child()
        with self.assertRaisesRegex(nn.TTSError, "boom"):
            runtime.decode([1], 0, 1)

    def test_models_lock_is_read_for_verification(self):
        lock = nn._read_lock(nn._DEFAULT_NATIVE / "models.lock")
        self.assertEqual(lock["backbone.file"], "neutts-2e-Q4_0.gguf")
        self.assertEqual(len(lock["decoder.sha256"]), 64)
        json.dumps(lock)


async def _noop(*_a, **_k):
    return None


if __name__ == "__main__":
    unittest.main()
