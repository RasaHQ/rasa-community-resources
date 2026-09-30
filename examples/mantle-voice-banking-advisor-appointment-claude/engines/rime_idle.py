"""Rasa's built-in Rime engine, reopening its websocket after an idle gap.

Why. Rime's streaming websocket stops producing audio once it has carried no
data for about 30 seconds. Rasa's ``RimeTTS`` (rasa-pro 3.21.0.dev5,
``rasa/core/channels/voice_stream/tts/rime.py``) opens one socket per call and
never reopens it, and it sends no keep-alive. On a voice call the socket is
idle while the bot's last reply plays out, the caller speaks, speech-to-text
finalises and the model thinks, so a long reply followed by an answer can pass
30 seconds. The next reply then fails: in this build's estimate call the
engine logged "TTS response no longer accepts text", then "WebSocket
connection not established", and the call ended
(case-build/results/estimate/). The Northgate dispute build saw the same two
errors after declines.

What was measured, through Rasa's own ``RimeTTS`` class with no Rasa code
changed (the probes are described in the README): a second synthesis 5 or 25
seconds after the first worked; after 35 seconds it returned 0 bytes. One
synthesis every 10 seconds kept a socket working past 49 seconds, so it is
idle time, not connection age. aiohttp heartbeat pings every 10 seconds did
not keep it alive. (Rasa's Deepgram Flux TTS engine opens its socket with
``heartbeat=30.0``; the Rime engine has none, and pings would not help here.)

The fix is to reopen the socket before a response when it has been idle for
longer than ``IDLE_RECONNECT_S``. Everything else is the built-in engine.
Each reopen is logged as ``northgate.rime_idle_reconnect`` so the harness can
count them; a reopen adds one websocket handshake to that reply's first byte.
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, List, Optional

import structlog

from rasa.core.channels.voice_stream.audio_bytes import RasaAudioBytes
from rasa.core.channels.voice_stream.tts.rime import RimeTTS, RimeTTSConfig

structlogger = structlog.get_logger()

# Below the ~30 s after which Rime's socket went quiet, with margin.
IDLE_RECONNECT_S = 20.0


class RimeTTSReconnectOnIdle(RimeTTS):
    """``RimeTTS`` that reopens its websocket after ``IDLE_RECONNECT_S`` without traffic."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_traffic: Optional[float] = None

    def _touch(self) -> None:
        self._last_traffic = time.monotonic()

    def idle_seconds(self) -> Optional[float]:
        return None if self._last_traffic is None else time.monotonic() - self._last_traffic

    def needs_reconnect(self) -> bool:
        idle = self.idle_seconds()
        return self.ws is None or self.ws.closed or (idle is not None and idle > IDLE_RECONNECT_S)

    async def connect(self, config: Optional[RimeTTSConfig] = None) -> None:
        await super().connect(config)
        self._touch()

    async def _reopen_if_idle(self) -> None:
        if self.needs_reconnect():
            idle = self.idle_seconds()
            structlogger.info("northgate.rime_idle_reconnect",
                              idle_s=None if idle is None else round(idle, 1))
            await self._reconnect_with_lock()

    async def prepare_response(self, streaming_config: Any = None) -> None:
        await super().prepare_response(streaming_config)
        await self._reopen_if_idle()

    async def send_text_chunk(self, text: str) -> None:
        await super().send_text_chunk(text)
        self._touch()

    async def signal_text_done(self) -> None:
        await super().signal_text_done()
        self._touch()

    async def stream_audio(self) -> AsyncIterator[RasaAudioBytes]:
        async for chunk in super().stream_audio():
            self._touch()
            yield chunk

    async def synthesize(self, text: str, config: Optional[RimeTTSConfig] = None) -> AsyncIterator[RasaAudioBytes]:
        # The built-in checks the socket before start_response gets to reopen it.
        await self._reopen_if_idle()
        async for chunk in super().synthesize(text, config):
            yield chunk

    @classmethod
    def from_config_dict(
        cls,
        config: Any,
        format: Any,
        rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "RimeTTSReconnectOnIdle":
        return cls(
            rasa_language=rasa_language,
            format=format,
            config=RimeTTSConfig.model_validate(config),
            additional_languages=additional_languages,
        )
