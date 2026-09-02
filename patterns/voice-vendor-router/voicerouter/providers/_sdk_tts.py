"""Shared base for TTS vendors reached through a synchronous cloud SDK.

The HTTP adapters in this package build a request and read the response body.
The hyperscalers do not work that way: boto3 and google-cloud-* are synchronous
client libraries that sign requests, retry, and hand back bytes. Wrapping them
by hand would mean reimplementing SigV4 or Google's ADC chain, which is exactly
the kind of thing to leave to the vendor's own SDK.

That leaves one problem, and it is the same one NeuTTS had: a synchronous call
inside an async voice loop. `await`ing it directly blocks the event loop for the
whole request, freezing every other call on the process. Everything here runs in
a worker thread.

Subclasses implement `synthesize_blocking(text) -> bytes` and declare what came
back.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Optional

import structlog
from rasa.core.channels.voice_stream.audio_bytes import RasaAudioBytes
from rasa.core.channels.voice_stream.tts.tts_engine import TTSEngine, TTSError

from voicerouter.audio import to_rasa_audio

logger = structlog.get_logger(__name__)


class SdkTTS(TTSEngine):
    """A TTS engine whose transport is a synchronous vendor SDK."""

    #: Rate the vendor is asked to produce, before transcoding.
    source_sample_rate: int = 16000
    #: True when the vendor returns a RIFF/WAVE blob rather than raw PCM.
    returns_wav: bool = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._client: Any = None
        self._lock = asyncio.Lock()

    # ---- subclass hooks -----------------------------------------------------

    def build_client(self) -> Any:
        """Construct the vendor client. Called once, on a worker thread."""
        raise NotImplementedError

    def synthesize_blocking(self, text: str) -> bytes:
        """One utterance, synchronously. Called on a worker thread."""
        raise NotImplementedError

    # ---- lifecycle ----------------------------------------------------------

    async def connect(self, config: Optional[Any] = None) -> None:
        """Build the client once.

        Client construction resolves credentials — an IMDS lookup on EC2, an
        ADC chain on GCP — which is a network round trip you do not want inside
        the first sentence the agent speaks.
        """
        async with self._lock:
            if self._client is not None:
                return
            self._client = await asyncio.to_thread(self.build_client)
            logger.info(f"{self.name()}.client_ready")

    async def close_connection(self) -> None:
        # These SDKs pool connections internally and have no session to close
        # that is worth tearing down between utterances.
        return None

    async def synthesize(
        self, text: str, config: Optional[Any] = None
    ) -> AsyncIterator[RasaAudioBytes]:
        if self._client is None:
            await self.connect()
        try:
            raw = await asyncio.to_thread(self.synthesize_blocking, text)
        except Exception as exc:  # noqa: BLE001 - vendor SDKs raise their own
            raise TTSError(f"{self.name()} synthesis failed: {exc}") from exc
        if not raw:
            raise TTSError(f"{self.name()} returned no audio")
        yield to_rasa_audio(
            raw, self.source_sample_rate, self.audio_format, is_wav=self.returns_wav
        )

    async def send_text_chunk(self, text: str) -> None:
        raise NotImplementedError(
            f"{self.name()} synthesises a whole utterance per request; use synthesize()."
        )

    async def signal_text_done(self) -> None:
        return None

    def engine_bytes_to_rasa_audio_bytes(self, chunk: bytes) -> RasaAudioBytes:
        return to_rasa_audio(chunk, self.source_sample_rate, self.audio_format)
