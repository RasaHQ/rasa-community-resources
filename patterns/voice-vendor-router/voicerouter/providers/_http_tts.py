"""Shared base for vendors that synthesise over HTTP rather than a websocket.

Rasa's built-in TTS engines all hold a websocket open. Several major vendors do
not work that way: you POST the text and read audio off the response body. That
fits Rasa fine — `synthesize()` only has to be an async iterator of audio — but
three adapters would otherwise repeat the same session handling, error mapping
and transcoding.

Subclasses supply three things: where to post, what to post, and what the audio
coming back looks like.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Optional, Tuple

import aiohttp
import structlog
from rasa.core.channels.voice_stream.audio_bytes import RasaAudioBytes
from rasa.core.channels.voice_stream.tts.tts_engine import TTSEngine, TTSError

from voicerouter.audio import PcmStreamConverter, to_rasa_audio

logger = structlog.get_logger(__name__)


class HttpStreamingTTS(TTSEngine):
    """A TTS engine whose transport is one HTTP request per utterance."""

    #: Sample rate the vendor is asked to produce, before transcoding.
    source_sample_rate: int = 24000
    #: True when the vendor returns a RIFF/WAVE blob rather than raw PCM.
    returns_wav: bool = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._session: Optional[aiohttp.ClientSession] = None

    def request(self, text: str) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
        """Return (url, headers, json_body) for one utterance."""
        raise NotImplementedError

    async def connect(self, config: Optional[Any] = None) -> None:
        """Open a pooled session.

        There is no persistent connection to establish, but creating the session
        here means TCP and TLS are reused across utterances rather than
        renegotiated every time the agent speaks — which is audible.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close_connection(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def synthesize(
        self, text: str, config: Optional[Any] = None
    ) -> AsyncIterator[RasaAudioBytes]:
        if self._session is None or self._session.closed:
            await self.connect()
        assert self._session is not None

        url, headers, body = self.request(text)
        try:
            async with self._session.post(url, json=body, headers=headers) as response:
                if response.status != 200:
                    detail = (await response.text())[:300]
                    raise TTSError(
                        f"{self.name()} returned HTTP {response.status}: {detail}"
                    )
                if self.returns_wav:
                    # A RIFF header only makes sense on the whole blob, so this
                    # shape cannot be yielded chunk by chunk.
                    raw = await response.read()
                    yield to_rasa_audio(
                        raw, self.source_sample_rate, self.audio_format, is_wav=True
                    )
                    return
                # One converter per utterance: it carries the partial frame
                # and the resampler state across chunk boundaries.
                converter = PcmStreamConverter(
                    self.source_sample_rate, self.audio_format
                )
                async for chunk, _ in response.content.iter_chunks():
                    if not chunk:
                        continue
                    converted = converter.feed(chunk)
                    if converted:
                        yield RasaAudioBytes(converted, format=self.audio_format)
        except aiohttp.ClientError as exc:
            raise TTSError(f"{self.name()} request failed: {exc}") from exc

    async def send_text_chunk(self, text: str) -> None:
        raise NotImplementedError(
            f"{self.name()} synthesises a whole utterance per request; use synthesize()."
        )

    async def signal_text_done(self) -> None:
        return None

    def engine_bytes_to_rasa_audio_bytes(self, chunk: bytes) -> RasaAudioBytes:
        return to_rasa_audio(chunk, self.source_sample_rate, self.audio_format)
