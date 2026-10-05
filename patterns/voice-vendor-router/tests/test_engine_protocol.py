#!/usr/bin/env python3
"""The router behaves like an engine wherever Rasa's voice channel touches one.

The first version implemented the methods the channel calls and nothing else,
and on rasa-pro 3.21.0.dev5 every routed call died before the caller was heard:
`run_audio_streaming` opens the call with `async with asr_engine, tts_engine:`,
`asr_keep_alive_task` reads `asr_engine.config`, and the channel's
`supports_streaming` returns `tts_engine.streaming_input`. None of those is a
method call, so a call-site scan never saw them.

Where it can, each test runs Rasa's own code against the router instead of
restating what that code does. No network, no credentials.
"""

from __future__ import annotations

import asyncio
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voicerouter.engine import RASA_AVAILABLE
if not RASA_AVAILABLE:
    raise unittest.SkipTest("Native Rasa response/channel contract requires the rasa dependency group")

from rasa.core.channels.voice_stream.audio_bytes import (  # noqa: E402
    L16_16KHZ,
    RasaAudioBytes,
)
from rasa.core.channels.voice_stream.tts.tts_engine import (  # noqa: E402
    StreamState,
    TTSEngine,
    TTSEngineConfig,
    TTSError,
    TTSLanguageMapEntry,
)

from voicerouter.base import BuiltProvider, ProviderSpec, RouterPolicy  # noqa: E402
from voicerouter.health import reset_shared_registries  # noqa: E402
from voicerouter.metrics import reset_shared_metrics  # noqa: E402
from voicerouter.routed_asr import RoutedASR  # noqa: E402
from voicerouter.routed_tts import RoutedTTS  # noqa: E402

FORMAT = L16_16KHZ


def run(coro):
    return asyncio.run(coro)


def built(label, engine):
    return BuiltProvider(ProviderSpec(name=label, label=label, config={}), engine)


class FakeASR:
    """The parts of an ASR engine the router delegates to."""

    def __init__(self, keep_alive_interval=5, fail_connect=False):
        self.config = types.SimpleNamespace(keep_alive_interval=keep_alive_interval)
        self.fail_connect = fail_connect
        self.connected = False
        self.closed = 0
        self.keep_alives = 0

    async def connect(self):
        if self.fail_connect:
            raise ConnectionError("503 Service Unavailable")
        self.connected = True

    async def close_connection(self):
        self.closed += 1
        self.connected = False

    async def send_keep_alive(self):
        self.keep_alives += 1


class StreamingTTS(TTSEngine[TTSEngineConfig]):
    """A real `TTSEngine`, so `start_response` runs Rasa's own response code.

    Each text chunk comes back as one audio chunk of the same bytes.
    """

    streaming_input = True

    def __init__(self, fail_start=False, fail_stream=False):
        super().__init__("en", FORMAT)
        self.fail_start = fail_start
        self.fail_stream = fail_stream
        self.connects = 0
        self.closes = 0
        self._text: asyncio.Queue = asyncio.Queue()

    @classmethod
    def name(cls):
        return "streaming-fake"

    @staticmethod
    def get_default_config(rasa_language):
        return TTSEngineConfig(language_map={"en": TTSLanguageMapEntry(voice="v")})

    async def connect(self, config=None):
        self.connects += 1

    async def close_connection(self):
        self.closes += 1

    async def prepare_response(self, streaming_config=None):
        if self.fail_start:
            raise ConnectionError("503 Service Unavailable")

    async def send_text_chunk(self, text):
        await self._text.put(text)

    async def signal_text_done(self):
        await self._text.put(None)

    async def signal_interrupt(self):
        await self._text.put(None)

    async def stream_audio(self):
        if self.fail_stream:
            raise ConnectionError("503 Service Unavailable")
        while True:
            text = await self._text.get()
            if text is None:
                return
            yield RasaAudioBytes(text.encode(), format=FORMAT)


class WholeMessageTTS(StreamingTTS):
    streaming_input = False


class ProtocolTestCase(unittest.TestCase):
    def setUp(self):
        reset_shared_registries()
        reset_shared_metrics()


class TestAsyncContextManager(ProtocolTestCase):
    """`voice_channel.run_audio_streaming`: `async with asr_engine, tts_engine:`."""

    def test_both_routers_enter_and_leave_like_rasas_engines(self):
        asr_engine = FakeASR()
        tts_engine = StreamingTTS()
        asr = RoutedASR([built("a", asr_engine)], RouterPolicy())
        tts = RoutedTTS([built("t", tts_engine)], RouterPolicy())

        async def call():
            async with asr, tts:
                self.assertTrue(asr_engine.connected)
                self.assertEqual(tts_engine.connects, 1)

        run(call())
        self.assertEqual(asr_engine.closed, 1)
        self.assertEqual(tts_engine.closes, 1)

    def test_entering_fails_over_like_connect(self):
        dead, alive = FakeASR(fail_connect=True), FakeASR()
        asr = RoutedASR([built("dead", dead), built("alive", alive)], RouterPolicy())

        async def call():
            async with asr as entered:
                self.assertIs(entered, asr)
                self.assertEqual(asr.active_provider, "alive")

        run(call())

    def test_an_error_inside_the_call_still_closes_and_propagates(self):
        asr_engine = FakeASR()
        tts_engine = StreamingTTS()
        asr = RoutedASR([built("a", asr_engine)], RouterPolicy())
        tts = RoutedTTS([built("t", tts_engine)], RouterPolicy())

        async def call():
            async with asr, tts:
                raise RuntimeError("caller hung up")

        with self.assertRaises(RuntimeError):
            run(call())
        self.assertEqual(asr_engine.closed, 1)
        self.assertEqual(tts_engine.closes, 1)


class TestAsrConfig(ProtocolTestCase):
    """`asr_keep_alive_task` reads `asr_engine.config.keep_alive_interval`."""

    def test_rasas_keep_alive_task_runs_against_the_router(self):
        from rasa.core.channels.voice_stream.voice_channel import VoiceInputChannel

        engine = FakeASR(keep_alive_interval=0.01)
        asr = RoutedASR([built("a", engine)], RouterPolicy())

        async def call():
            task = asyncio.create_task(VoiceInputChannel.asr_keep_alive_task(None, asr))
            await asyncio.sleep(0.1)
            self.assertFalse(task.done(), "keep-alive task died")
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        run(call())
        self.assertGreater(engine.keep_alives, 0)

    def test_interval_is_the_shortest_any_provider_needs(self):
        # The interval is read once per call; a failover target that needs
        # pinging more often must not idle out.
        from rasa.core.channels.voice_stream.asr.asr_engine import ASREngineConfig

        primary = FakeASR()
        primary.config = ASREngineConfig(keep_alive_interval=8, language_map={})
        backup = FakeASR(keep_alive_interval=3)
        asr = RoutedASR([built("p", primary), built("b", backup)], RouterPolicy())
        self.assertEqual(asr.config.keep_alive_interval, 3)
        # The rest of the config is the active provider's, left untouched.
        self.assertEqual(primary.config.keep_alive_interval, 8)
        self.assertIsInstance(asr.config, ASREngineConfig)


class TestStreamingFlag(ProtocolTestCase):
    """`VoiceOutputChannel.supports_streaming` returns `tts_engine.streaming_input`."""

    def _supports_streaming(self, tts):
        from rasa.core.channels.voice_stream.voice_channel import VoiceOutputChannel

        return VoiceOutputChannel.supports_streaming.fget(
            types.SimpleNamespace(tts_engine=tts)
        )

    def test_reports_the_active_providers_flag(self):
        streaming = RoutedTTS([built("s", StreamingTTS())], RouterPolicy())
        whole = RoutedTTS([built("w", WholeMessageTTS())], RouterPolicy())
        self.assertIs(self._supports_streaming(streaming), True)
        self.assertIs(self._supports_streaming(whole), False)

    def test_flag_follows_a_failover(self):
        # The channel reads it again after start_response for exactly this.
        tts = RoutedTTS(
            [built("s", StreamingTTS(fail_start=True)), built("w", WholeMessageTTS())],
            RouterPolicy(),
        )
        self.assertTrue(tts.streaming_input)
        run(tts.start_response())
        self.assertEqual(tts.active_provider, "w")
        self.assertFalse(tts.streaming_input)


class TestPlaybackFlags(ProtocolTestCase):
    """`stream_state` and `stop_streaming_output_audio_chunks` are read and written."""

    def test_writes_reach_every_provider_and_reads_come_from_the_active_one(self):
        a, b = StreamingTTS(), StreamingTTS()
        tts = RoutedTTS([built("a", a), built("b", b)], RouterPolicy())
        tts.stream_state = StreamState.SENDING_RESPONSE_CHUNKS
        tts.stop_streaming_output_audio_chunks = True
        self.assertEqual(
            [a.stream_state, b.stream_state], [StreamState.SENDING_RESPONSE_CHUNKS] * 2
        )
        self.assertEqual(
            [a.stop_streaming_output_audio_chunks, b.stop_streaming_output_audio_chunks],
            [True, True],
        )
        b.stream_state = StreamState.INTERRUPTED
        tts._active_index = 1
        self.assertEqual(tts.stream_state, StreamState.INTERRUPTED)

    def test_barge_in_is_seen_by_the_channel_and_by_a_failover_target(self):
        a, b = StreamingTTS(), StreamingTTS()
        tts = RoutedTTS([built("a", a), built("b", b)], RouterPolicy())

        async def barge_in():
            await tts.interrupt()  # the channel awaits what interrupt() returns

        run(barge_in())
        self.assertEqual(tts.stream_state, StreamState.INTERRUPTED)
        self.assertTrue(tts.stop_streaming_output_audio_chunks)
        # A provider that takes over mid-utterance must not play on.
        self.assertTrue(b.stop_streaming_output_audio_chunks)


class TestStreamedResponses(ProtocolTestCase):
    """`start_response` goes through Rasa's own `TTSResponse` on the provider."""

    def _speak(self, tts, words):
        async def speak():
            response = await tts.start_response()
            for word in words:
                await response.write(word)
            await response.finish()
            return [bytes(chunk.data) async for chunk in response]

        return run(speak())

    def test_text_in_audio_out_through_the_active_provider(self):
        tts = RoutedTTS([built("a", StreamingTTS())], RouterPolicy())
        self.assertEqual(self._speak(tts, ["Hello", " there"]), [b"Hello", b" there"])
        self.assertEqual(tts.metrics_snapshot()[0]["successes"], 1)

    def test_a_provider_that_cannot_start_is_routed_around(self):
        tts = RoutedTTS(
            [built("dead", StreamingTTS(fail_start=True)), built("alive", StreamingTTS())],
            RouterPolicy(),
        )
        self.assertEqual(self._speak(tts, ["Hi"]), [b"Hi"])
        self.assertEqual(tts.active_provider, "alive")
        self.assertIsNotNone(tts._health.get("dead").opened_at)

    def test_a_stream_that_dies_marks_its_provider_for_the_next_response(self):
        tts = RoutedTTS(
            [built("flaky", StreamingTTS(fail_stream=True)), built("steady", StreamingTTS())],
            RouterPolicy(),
        )
        with self.assertRaises(ConnectionError):
            self._speak(tts, ["Hi"])
        self.assertNotIn(0, tts._connected)
        self.assertEqual(tts._candidates()[0], 1)
        self.assertEqual(self._speak(tts, ["Again"]), [b"Again"])
        self.assertEqual(tts.active_provider, "steady")

    def test_no_provider_left_is_a_tts_error(self):
        tts = RoutedTTS([built("dead", StreamingTTS(fail_start=True))], RouterPolicy())
        with self.assertRaises(TTSError):
            run(tts.start_response())


if __name__ == "__main__":
    unittest.main()
