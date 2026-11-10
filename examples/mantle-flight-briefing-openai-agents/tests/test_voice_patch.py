"""Offline regression tests for voice_patch (no network, no key). Run with the Rasa venv python."""
import asyncio
import json
import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import voice_patch  # noqa: E402
from websockets.protocol import State  # noqa: E402

from rasa.core.channels.voice_stream.asr.asr_event import NewTranscript, UserIsSpeaking  # noqa: E402
from rasa.core.channels.voice_stream.asr.deepgram.engine import DeepgramASR  # noqa: E402
from rasa.core.channels.voice_stream.audio_bytes import L16_48KHZ, RasaAudioBytes  # noqa: E402

voice_patch.install()


def turn(event, text=""):
    return json.dumps({"type": "TurnInfo", "event": event, "transcript": text})


def engine():
    with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "offline-test-placeholder"}):
        return DeepgramASR.from_config_dict(
            {"language_map": {"en": {"model": "flux-general-en"}}}, L16_48KHZ, "en"
        )


class FakeSocket:
    def __init__(self, frames=(), state=State.OPEN, close_at_end=True):
        self.frames, self.state, self.sent, self.close_at_end = list(frames), state, [], close_at_end

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for frame in self.frames:
            yield frame
        if self.close_at_end:
            self.state = State.CLOSED  # the server hangs up after its frames

    async def send(self, data):
        self.sent.append(data)

    async def close(self):
        self.state = State.CLOSED


async def collect(asr, limit=20):
    out = []
    async for event in asr.stream_asr_events():
        out.append(event)
        if len(out) >= limit:
            break
    return out


class VoicePatchTests(unittest.TestCase):
    def test_install_is_idempotent(self):
        self.assertFalse(voice_patch.install())

    def test_end_of_turn_without_update_keeps_its_own_words(self):
        asr = engine()
        self.assertIsNone(asr.engine_event_to_asr_event(turn("StartOfTurn")))
        event = asr.engine_event_to_asr_event(turn("EndOfTurn", "yes that one"))
        self.assertEqual(event, NewTranscript(text="yes that one"))

    def test_end_of_turn_with_updates_still_uses_the_accumulated_text(self):
        asr = engine()
        asr.engine_event_to_asr_event(turn("StartOfTurn"))
        self.assertIsInstance(asr.engine_event_to_asr_event(turn("Update", "which flights")), UserIsSpeaking)
        event = asr.engine_event_to_asr_event(turn("EndOfTurn", "which flights are in the air"))
        self.assertEqual(event, NewTranscript(text="which flights"))

    def test_empty_end_of_turn_is_still_nothing(self):
        asr = engine()
        self.assertIsNone(asr.engine_event_to_asr_event(turn("EndOfTurn", "")))

    def test_three_turns_across_a_remote_close_all_arrive(self):
        asr = engine()
        sockets = [
            FakeSocket([turn("StartOfTurn"), turn("Update", "which flights"), turn("EndOfTurn", "which flights")]),
            FakeSocket([turn("StartOfTurn"), turn("EndOfTurn", "yes that one")]),  # no Update, new socket
            FakeSocket([turn("StartOfTurn"), turn("Update", "the first one"), turn("EndOfTurn", "the first one")]),
        ]
        asr.asr_socket = sockets[0]
        opened = []

        async def reopen():
            opened.append(1)
            return sockets[len(opened)] if len(opened) < len(sockets) else FakeSocket([])

        asr.open_websocket_connection = reopen
        events = asyncio.run(collect(asr))
        texts = [e.text for e in events if isinstance(e, NewTranscript)]
        self.assertEqual(texts, ["which flights", "yes that one", "the first one"])
        self.assertGreaterEqual(len(opened), 2)  # the hang-ups between turns, then bounded retries

    def test_a_deliberate_close_does_not_reconnect(self):
        asr = engine()
        asr.asr_socket = FakeSocket([turn("StartOfTurn"), turn("EndOfTurn", "bye")])

        async def run():
            gen = asr.stream_asr_events()
            first = await gen.__anext__()
            asr.asr_socket = None  # close_connection() nulls the socket on teardown
            rest = [e async for e in gen]
            return first, rest

        async def boom():
            raise AssertionError("reconnected after a deliberate close")

        asr.open_websocket_connection = boom
        first, rest = asyncio.run(run())
        self.assertEqual(first, NewTranscript(text="bye"))
        self.assertEqual(rest, [])

    def test_a_stream_that_ends_with_the_socket_still_open_does_not_reconnect(self):
        asr = engine()
        asr.asr_socket = FakeSocket([turn("StartOfTurn"), turn("EndOfTurn", "ok")], close_at_end=False)

        async def boom():
            raise AssertionError("reconnected although the socket was still open")

        asr.open_websocket_connection = boom
        self.assertEqual(asyncio.run(collect(asr)), [NewTranscript(text="ok")])

    def test_reconnects_are_bounded(self):
        asr = engine()
        asr.asr_socket = FakeSocket([])
        count = []

        async def reopen():
            count.append(1)
            return FakeSocket([])

        asr.open_websocket_connection = reopen
        asyncio.run(collect(asr))
        self.assertEqual(len(count), voice_patch.MAX_RECONNECTS)

    def test_flux_gets_silence_after_an_idle_gap_and_not_before(self):
        asr = engine()
        asr.asr_socket = FakeSocket()
        asyncio.run(asr.send_audio_chunks(RasaAudioBytes(b"\x01\x00", L16_48KHZ)))
        asyncio.run(asr.send_keep_alive())
        self.assertEqual(len(asr.asr_socket.sent), 1)  # just the audio, no silence yet
        asr._zeocore_last_sent -= 3.0
        asyncio.run(asr.send_keep_alive())
        self.assertEqual(len(asr.asr_socket.sent), 1)  # 3 s idle is not enough
        asr._zeocore_last_sent -= 1.5
        asyncio.run(asr.send_keep_alive())
        self.assertEqual(len(asr.asr_socket.sent), 2)
        self.assertEqual(asr.asr_socket.sent[1], bytes(int(48000 * 0.08) * 2))


if __name__ == "__main__":
    unittest.main()
