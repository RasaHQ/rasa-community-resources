# concern: voice-adapter
"""Deepgram Aura-2 text-to-speech over the /v1/speak WebSocket.

The same interface as ``cedar_speech.SpeechmaticsTTS``:

    tts = DeepgramTTS()                              # one per process; keeps one socket open
    pcm = await tts.synthesize("Cedar Clinic prescription line.")   # 24 kHz PCM16
    await tts.close()

The messages are those of Rasa's built-in engine (``DeepgramTTS``): ``Speak``
with the text, then ``Flush``, and audio frames until ``Flushed``. Deepgram
streams the audio, so ``stream()`` yields it as it arrives, but the LangGraph
and Strands voice loops call ``synthesize()`` once per sentence and play the
whole sentence, as they do with Speechmatics. Rasa instead streams the
model's text into the socket as it is generated (its engine reports
``streaming_input``), which these two loops were not written to do.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import AsyncIterator, Optional
from urllib.parse import urlencode

from websockets.asyncio.client import ClientConnection, connect

from cedar_speech_deepgram import config


class TTSError(RuntimeError):
    pass


class DeepgramTTS:
    def __init__(self, target_rate: int = config.SAMPLE_RATE, *, endpoint: str = config.TTS_ENDPOINT,
                 api_key: Optional[str] = None, timeout_s: float = 30.0) -> None:
        self.target_rate = target_rate
        self.url = f"{endpoint}?{urlencode(config.tts_query(target_rate))}"
        self._api_key = api_key
        self.timeout_s = timeout_s
        self._socket: Optional[ClientConnection] = None
        self._lock = asyncio.Lock()
        #: Timings of the last request: seconds to the first audio frame and to Flushed.
        self.last_timings: dict = {}
        #: Characters sent, for cost accounting (Aura-2 bills per character).
        self.characters = 0

    async def _connect(self) -> ClientConnection:
        if self._socket is None:
            key = self._api_key or os.environ.get(config.API_KEY_ENV_VAR, "")
            if not key:
                raise TTSError(f"{config.API_KEY_ENV_VAR} is not set")
            self._socket = await connect(self.url, additional_headers={"Authorization": f"Token {key}"})
        return self._socket

    async def _speak(self, text: str) -> AsyncIterator[bytes]:
        socket = await self._connect()
        await socket.send(json.dumps({"type": "Speak", "text": text}))
        await socket.send(json.dumps({"type": "Flush"}))
        while True:
            raw = await asyncio.wait_for(socket.recv(), timeout=self.timeout_s)
            if isinstance(raw, bytes):
                yield raw
                continue
            kind = json.loads(raw).get("type")
            if kind == "Flushed":
                return
            if kind == "Error":
                raise TTSError(f"deepgram speak: {raw[:300]}")

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        """The utterance as 16-bit mono PCM at ``target_rate``, frame by frame as Deepgram sends it."""
        async with self._lock:
            began = time.monotonic()
            first = None
            size = 0
            for attempt in (1, 2):
                try:
                    async for chunk in self._speak(text):
                        first = first or time.monotonic()
                        size += len(chunk)
                        yield chunk
                    break
                except Exception as exc:
                    # A socket Deepgram closed while idle: reconnect once, unless audio already went out.
                    await self._drop()
                    if attempt == 2 or size:
                        raise TTSError(f"deepgram speak failed: {exc}") from exc
            self.characters += len(text)
            self.last_timings = {"chars": len(text), "headers_s": round((first or time.monotonic()) - began, 4),
                                 "total_s": round(time.monotonic() - began, 4),
                                 "audio_s": round(size / 2 / self.target_rate, 3)}

    async def synthesize(self, text: str) -> bytes:
        """The whole utterance as 16-bit mono PCM at ``target_rate``."""
        return b"".join([chunk async for chunk in self.stream(text)])

    async def _drop(self) -> None:
        if self._socket is not None:
            try:
                await asyncio.wait_for(self._socket.close(), timeout=5)
            except Exception:
                pass
        self._socket = None

    async def close(self) -> None:
        await self._drop()
