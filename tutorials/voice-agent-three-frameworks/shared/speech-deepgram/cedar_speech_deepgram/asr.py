# concern: voice-adapter
"""Deepgram streaming speech-to-text (Nova-3, /v1/listen), one socket per call.

The same interface as ``cedar_speech.SpeechmaticsASR``, so the LangGraph and
Strands voice loops run unchanged:

    async with DeepgramASR() as asr:
        await asr.send_audio(pcm_20ms)
        async for event in asr.events():     # cedar_speech.Transcript(text, final, at)
            ...

Turn ends are Deepgram's: ``is_final`` results are held until one carries
``speech_final`` (400 ms of silence, ``config.ASR_ENDPOINTING_MS``), or an
``UtteranceEnd`` arrives, and then sent as one final transcript. That is the
logic of Rasa's built-in engine (``_DeepgramV1.parse_event``), so the three
versions split caller turns the same way.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import AsyncIterator, Optional
from urllib.parse import urlencode

from cedar_speech import Transcript
from websockets.asyncio.client import ClientConnection, connect

from cedar_speech_deepgram import config


class DeepgramError(RuntimeError):
    pass


class ResultsReader:
    """Deepgram /v1/listen frames to ("partial" | "final", text), as Rasa's built-in engine reads them."""

    def __init__(self) -> None:
        self.held = ""

    def read(self, raw: str | bytes) -> Optional[tuple[str, str]]:
        data = json.loads(raw)
        kind = data.get("type")
        if kind == "Results":
            alternatives = (data.get("channel") or {}).get("alternatives") or [{}]
            text = (alternatives[0].get("transcript") or "").strip()
            if data.get("is_final"):
                self.held = (self.held + " " + text).strip()
                if data.get("speech_final"):
                    full, self.held = self.held, ""
                    return ("final", full) if full else None
            elif text:
                return ("partial", text)
        elif kind == "UtteranceEnd" and self.held:
            full, self.held = self.held, ""
            return ("final", full)
        elif kind == "Error":
            return ("error", str(data.get("description") or data.get("message") or data))
        return None


class DeepgramASR:
    def __init__(self, sample_rate: int = config.SAMPLE_RATE, *, endpoint: str = config.ASR_ENDPOINT,
                 api_key: Optional[str] = None) -> None:
        self.sample_rate = sample_rate
        self.url = f"{endpoint}?{urlencode(config.asr_query(sample_rate))}"
        self._api_key = api_key
        self.reader = ResultsReader()
        self.socket: Optional[ClientConnection] = None
        #: Seconds of audio sent: Deepgram bills streaming by the minute of audio.
        self.audio_seconds = 0.0
        self.opened_at: Optional[float] = None

    async def open(self) -> "DeepgramASR":
        key = self._api_key or os.environ.get(config.API_KEY_ENV_VAR, "")
        if not key:
            raise DeepgramError(f"{config.API_KEY_ENV_VAR} is not set")
        self.socket = await connect(self.url, additional_headers={"Authorization": f"Token {key}"})
        self.opened_at = time.time()
        return self

    async def send_audio(self, pcm16: bytes) -> None:
        """One chunk of 16-bit mono PCM at ``sample_rate`` (the browser sends 20 ms frames)."""
        if self.socket is None:
            raise DeepgramError("socket not open")
        await self.socket.send(pcm16)
        self.audio_seconds += len(pcm16) / 2 / self.sample_rate

    async def events(self) -> AsyncIterator[Transcript]:
        """Partial and final transcripts until the socket closes."""
        if self.socket is None:
            raise DeepgramError("socket not open")
        async for raw in self.socket:
            if isinstance(raw, bytes):
                continue
            event = self.reader.read(raw)
            if event is None:
                continue
            kind, text = event
            if kind == "error":
                raise DeepgramError(text)
            yield Transcript(text, final=(kind == "final"))

    async def close(self) -> None:
        """Send CloseStream, as Rasa's engine does, then close the socket."""
        if self.socket is None:
            return
        try:
            await self.socket.send(json.dumps({"type": "CloseStream"}))
            await asyncio.wait_for(self.socket.close(), timeout=5)
        except Exception:
            pass
        self.socket = None

    async def __aenter__(self) -> "DeepgramASR":
        return await self.open()

    async def __aexit__(self, *exc) -> None:
        await self.close()
