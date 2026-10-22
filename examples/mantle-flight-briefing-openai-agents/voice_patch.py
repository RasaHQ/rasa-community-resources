"""Deepgram Flux turn-taking fixes for the Inspector voice path (sow: software-factories-masterclass-SOW-02).

Three defects in the pinned engine, each patched in memory (nothing under site-packages is edited):

1. EndOfTurn dropped its own words. _DeepgramV2.parse_event commits only the text collected from
   earlier Update frames, so a short turn that arrives as StartOfTurn then EndOfTurn lost them.
   The patch falls back to the transcript carried by the EndOfTurn frame itself.
2. A closed socket ended the listener for good. stream_asr_events swallowed the close and stopped;
   later audio was dropped at DEBUG level. The patch reconnects (bounded) while the engine still
   owns the socket, and logs each reconnect at WARNING.
3. Flux accepts no KeepAlive, so a quiet gap (the bot speaking, a file test) let Deepgram idle the
   socket. The patch sends 80 ms of silence when nothing has been sent for IDLE_SILENCE_SECONDS.

Call install() once, in the process that runs the voice channel. It is idempotent.
"""
import json
import time

import structlog

logger = structlog.get_logger(__name__)

IDLE_SILENCE_SECONDS = 4.0
MAX_RECONNECTS = 5
_MARK = "_zeocore_voice_patch"


def _silence(engine) -> bytes:
    rate = getattr(engine.audio_format, "sample_rate", 16000)
    frame = int(rate * 0.08)
    if engine._handler._encoding_for(engine.audio_format) == "mulaw":
        return b"\xff" * frame
    return bytes(frame * 2)


def install() -> bool:
    from websockets.protocol import State

    from rasa.core.channels.voice_stream.asr.asr_event import NewTranscript
    from rasa.core.channels.voice_stream.asr.deepgram import engine as dg

    if getattr(dg.DeepgramASR, _MARK, False):
        return False

    original_parse = dg._DeepgramV2.parse_event
    original_send = dg.DeepgramASR.send_audio_chunks
    original_keep = dg.DeepgramASR.send_keep_alive
    original_stream = dg.DeepgramASR.stream_asr_events

    def parse_event(self, message):
        event = original_parse(self, message)
        if event is not None:
            return event
        try:
            data = message if isinstance(message, dict) else json.loads(message)
        except (TypeError, ValueError):
            return None
        if data.get("type") == "TurnInfo" and data.get("event") == "EndOfTurn":
            words = (data.get("transcript") or "").strip()
            if words:
                return NewTranscript(text=words)
        return None

    async def send_audio_chunks(self, chunk):
        self._zeocore_last_sent = time.monotonic()
        await original_send(self, chunk)

    async def send_keep_alive(self):
        if not isinstance(self._handler, dg._DeepgramV2):
            await original_keep(self)
            return
        last = getattr(self, "_zeocore_last_sent", None)
        if last is None:
            self._zeocore_last_sent = time.monotonic()
            return
        if time.monotonic() - last < IDLE_SILENCE_SECONDS:
            return
        async with self._get_engine_lock():
            socket = self.asr_socket
            if socket is not None and socket.state is State.OPEN:
                await socket.send(_silence(self))
                self._zeocore_last_sent = time.monotonic()

    async def stream_asr_events(self):
        reconnects = 0
        while True:
            ended = self.asr_socket
            async for event in original_stream(self):
                yield event
            # A deliberate close nulls asr_socket; only a remote close leaves a CLOSED socket behind.
            if ended is None or self.asr_socket is not ended or ended.state is not State.CLOSED:
                return
            if reconnects >= MAX_RECONNECTS:
                logger.warning("deepgram.reconnect.giving_up", attempts=reconnects)
                return
            reconnects += 1
            logger.warning("deepgram.reconnect", attempt=reconnects, reason="remote_close")
            async with self._get_engine_lock():
                self.asr_socket = await self.open_websocket_connection()
            if isinstance(self._handler, dg._DeepgramV2):
                self._handler._accumulated_transcript = ""

    dg._DeepgramV2.parse_event = parse_event
    dg.DeepgramASR.send_audio_chunks = send_audio_chunks
    dg.DeepgramASR.send_keep_alive = send_keep_alive
    dg.DeepgramASR.stream_asr_events = stream_asr_events
    setattr(dg.DeepgramASR, _MARK, True)
    return True
