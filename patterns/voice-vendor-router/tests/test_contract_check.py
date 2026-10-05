#!/usr/bin/env python3
"""The contract check catches what broke routed calls on rasa-pro 3.21.0.dev5.

It used to scan for `<kind>_engine.<name>(` only, and passed while every
routed call died on a missing `__aenter__`, then on a missing `config`. These
tests pin the check to the kinds of use a call-site scan cannot see: attribute
reads, attribute writes and the async context-manager protocol.

    make test
"""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voicerouter.engine import RASA_AVAILABLE
from voicerouter import contract  # noqa: E402


def _write(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")


class TestScanner(unittest.TestCase):
    """Classification of each kind of use, on a synthetic Rasa tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _write(self.root, "core/channels/voice_stream/voice_channel.py", """
            async def run(asr_engine, tts_engine):
                async with asr_engine, tts_engine:
                    interval = getattr(asr_engine.config, "keep_alive_interval", 5)
                    await asr_engine.send_keep_alive()
                    self.tts_engine.stream_state = State.SENDING
                    if self.tts_engine.stream_state == State.INTERRUPTED:
                        return self.tts_engine.streaming_input
                    async with self._get_engine_lock():
                        pass
            # async with asr_engine_from_config(...) as engine: is not an entry
        """)
        _write(self.root, "tracing/voice/recorders/tts/span_attributes.py", """
            def engine_attributes(engine):
                return {"provider": engine.name(), "lang": engine.current_language_config}
        """)

    def test_calls_reads_writes_and_protocols_are_told_apart(self):
        asr = contract.scan("asr", self.root)
        tts = contract.scan("tts", self.root)
        self.assertEqual(asr.calls, {"send_keep_alive"})
        self.assertEqual(asr.reads, {"config"})
        self.assertEqual(asr.protocols, {contract.ASYNC_CONTEXT_MANAGER})
        self.assertEqual(tts.writes, {"stream_state"})
        self.assertEqual(tts.reads, {"stream_state", "streaming_input", "current_language_config"})
        self.assertEqual(tts.calls, {"name"})
        self.assertEqual(tts.protocols, {contract.ASYNC_CONTEXT_MANAGER})

    def test_each_use_says_where_it_was_found(self):
        asr = contract.scan("asr", self.root)
        self.assertEqual(
            asr.where("reads", "config"), "core/channels/voice_stream/voice_channel.py:4"
        )
        self.assertEqual(
            asr.where("protocols", contract.ASYNC_CONTEXT_MANAGER),
            "core/channels/voice_stream/voice_channel.py:3",
        )


@unittest.skipUnless(RASA_AVAILABLE, "Installed Rasa source contract requires the rasa dependency group")
class TestInstalledRasa(unittest.TestCase):
    """What the pinned wheel actually uses, including the uses that broke calls."""

    def test_the_uses_that_broke_routed_calls_are_found(self):
        asr = contract.required_surface("asr")
        tts = contract.required_surface("tts")
        self.assertIn(contract.ASYNC_CONTEXT_MANAGER, asr.protocols)
        self.assertIn(contract.ASYNC_CONTEXT_MANAGER, tts.protocols)
        self.assertIn("config", asr.reads)
        self.assertIn("streaming_input", tts.reads)
        self.assertLessEqual({"stream_state", "stop_streaming_output_audio_chunks"}, tts.writes)
        self.assertIn("current_language_config", tts.reads)


class MethodsOnlyASR:
    """The shape of RoutedASR before the fix: every method, nothing else."""

    @classmethod
    def from_config_dict(cls, *a): ...
    @classmethod
    def name(cls): ...
    current_language_config = None
    async def connect(self): ...
    async def close_connection(self): ...
    async def send_audio_chunks(self, chunk): ...
    async def send_keep_alive(self): ...
    async def stream_asr_events(self): ...
    async def set_language(self, language): ...


class MethodsOnlyTTS:
    """The shape of RoutedTTS before the fix."""

    @classmethod
    def from_config_dict(cls, *a): ...
    @classmethod
    def name(cls): ...
    current_language_config = None
    async def connect(self): ...
    async def close_connection(self): ...
    async def synthesize(self, text): ...
    async def start_response(self, streaming_config=None): ...
    def interrupt(self): ...
    async def set_language(self, language): ...


@unittest.skipUnless(RASA_AVAILABLE, "Installed Rasa source contract requires the rasa dependency group")
class TestFindsWhatIsMissing(unittest.TestCase):
    def test_the_pre_fix_router_shape_fails_the_check(self):
        asr_gaps = contract.missing(MethodsOnlyASR, contract.required_surface("asr"))
        tts_gaps = contract.missing(MethodsOnlyTTS, contract.required_surface("tts"))
        joined_asr, joined_tts = " | ".join(asr_gaps), " | ".join(tts_gaps)
        self.assertIn("async context-manager protocol", joined_asr)
        self.assertIn("attribute config", joined_asr)
        self.assertIn("async context-manager protocol", joined_tts)
        for name in ("streaming_input", "stream_state", "stop_streaming_output_audio_chunks"):
            self.assertIn(f"attribute {name}", joined_tts)

    def _surface(self, **parts):
        surface = contract.Surface("tts")
        for part, items in parts.items():
            for item in items:
                surface.note(part, item, "voice_channel.py:1")
        return surface

    def test_a_read_only_property_is_not_writable(self):
        class ReadOnly:
            @property
            def stream_state(self):
                return None

        gaps = contract.missing(ReadOnly, self._surface(writes={"stream_state"}))
        self.assertEqual(len(gaps), 1)
        self.assertIn("read-only property", gaps[0])

    def test_a_settable_property_or_class_attribute_is_writable(self):
        class Settable:
            flag = False

            @property
            def stream_state(self):
                return None

            @stream_state.setter
            def stream_state(self, value):
                pass

        self.assertEqual(
            contract.missing(Settable, self._surface(writes={"stream_state", "flag"})), []
        )

    def test_a_synchronous_enter_is_not_the_async_protocol(self):
        class SyncEnter:
            def __aenter__(self):
                return self

            def __aexit__(self, *exc):
                return False

        gaps = contract.missing(
            SyncEnter, self._surface(protocols={contract.ASYNC_CONTEXT_MANAGER})
        )
        self.assertEqual(len(gaps), 1)

    def test_a_property_is_not_a_method(self):
        class PropertyNotMethod:
            @property
            def synthesize(self):
                return None

        gaps = contract.missing(PropertyNotMethod, self._surface(calls={"synthesize"}))
        self.assertIn("method synthesize()", gaps[0])

    def test_the_routers_pass(self):
        self.assertEqual(contract.check(verbose=False), [])


if __name__ == "__main__":
    unittest.main()
