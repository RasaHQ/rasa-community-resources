# concern: voice-adapter
"""Speechmatics text-to-speech, one HTTP POST per utterance.

    tts = SpeechmaticsTTS()                     # one per process; pools the HTTP session
    pcm = await tts.synthesize("Cedar Clinic prescription line.")
    # 16-bit mono PCM at 24 kHz (the wire rate), resampled from the vendor's 16 kHz WAV
    await tts.close()

The API is Speechmatics' preview TTS (``config.TTS_ENDPOINT``). It returns
a whole WAV file per request (``wav_16000``; the only other format it accepts
is ``pcm_16000``), so audio for an utterance arrives in one piece, as it does
in the Rasa version's engine: same URL, same body, same resampling. Split
long replies into sentences before calling it if you want the first sentence
to play sooner; that sentence chunking is voice-loop code and is counted as
such (see COMPARISON-PLAN.md).

Speechmatics documents TTS as "currently in preview and free to use"; no
per-character price was published when this was written.
"""

from __future__ import annotations

import os
import time
from typing import AsyncIterator, Optional

import aiohttp

from cedar_speech import audio, config, protocol


class TTSError(RuntimeError):
    pass


class SpeechmaticsTTS:
    def __init__(self, target_rate: int = config.SAMPLE_RATE, *, voice: str = config.TTS_VOICE,
                 endpoint: str = config.TTS_ENDPOINT, output_format: str = config.TTS_OUTPUT_FORMAT,
                 api_key: Optional[str] = None, timeout_s: float = 30.0) -> None:
        self.target_rate = target_rate
        self.voice = voice
        self.endpoint = endpoint
        self.output_format = output_format
        self._api_key = api_key
        self.timeout_s = timeout_s
        self._session: Optional[aiohttp.ClientSession] = None
        #: Timings of the last request: seconds to response headers and to the whole body.
        self.last_timings: dict = {}
        #: Characters sent, for cost accounting.
        self.characters = 0

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_s))
        return self._session

    async def synthesize(self, text: str) -> bytes:
        """The whole utterance as 16-bit mono PCM at ``target_rate``."""
        key = self._api_key or os.environ.get(config.API_KEY_ENV_VAR, "")
        if not key:
            raise TTSError(f"{config.API_KEY_ENV_VAR} is not set")
        url, headers, body = protocol.tts_request(text, key, voice=self.voice, endpoint=self.endpoint,
                                                  output_format=self.output_format)
        session = await self._ensure_session()
        began = time.monotonic()
        try:
            async with session.post(url, json=body, headers=headers) as response:
                headers_s = time.monotonic() - began
                if response.status != 200:
                    raise TTSError(f"speechmatics returned HTTP {response.status}: {(await response.text())[:300]}")
                raw = await response.read()
        except aiohttp.ClientError as exc:
            raise TTSError(f"speechmatics request failed: {exc}") from exc
        pcm = audio.wav_to_pcm(raw, config.TTS_SOURCE_RATE, self.target_rate)
        self.characters += len(text)
        self.last_timings = {"chars": len(text), "headers_s": round(headers_s, 4),
                             "total_s": round(time.monotonic() - began, 4),
                             "audio_s": round(len(pcm) / 2 / self.target_rate, 3)}
        return pcm

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        """``synthesize`` as an async iterator (one chunk: the API returns a whole file)."""
        yield await self.synthesize(text)

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
