# concern: voice-adapter
"""Speechmatics realtime speech-to-text, one socket per call.

    async with SpeechmaticsASR() as asr:           # opens the socket, sends StartRecognition
        feeder = asyncio.create_task(pump(asr))    # asr.send_audio(pcm) for every 20 ms frame
        async for event in asr.events():           # Transcript objects
            if event.final:
                await agent_turn(event.text)       # one caller turn, joined at EndOfUtterance

Speechmatics decides where the caller stopped: with
``end_of_utterance_silence_trigger`` (0.7 s, ``config.ASR_SETTINGS``) it sends
``EndOfUtterance`` and the held final segments become one ``final`` event.
Partial events (``final=False``) say the caller is speaking, which is what a
barge-in or a "still listening" indicator would use.

Same messages, same settings and the same reply handling as the Rasa
version's engine (see ``protocol.py``). Uses the websockets asyncio client
with ``additional_headers``, as Rasa's own engines do.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from websockets.asyncio.client import ClientConnection, connect

from cedar_speech import config, protocol


@dataclass
class Transcript:
    text: str
    final: bool
    #: time.time() when the reply arrived.
    at: float = field(default_factory=time.time)


class SpeechmaticsError(RuntimeError):
    pass


class SpeechmaticsASR:
    def __init__(self, sample_rate: int = config.SAMPLE_RATE, *, endpoint: str = config.ASR_ENDPOINT,
                 api_key: Optional[str] = None, **settings) -> None:
        self.sample_rate = sample_rate
        self.endpoint = endpoint
        self._api_key = api_key
        self.start_message = protocol.start_recognition(sample_rate, **settings)
        trigger = self.start_message["transcription_config"].get("conversation_config", {}).get(
            "end_of_utterance_silence_trigger")
        self.reader = protocol.ReplyReader(utterance_mode=bool(trigger))
        self.socket: Optional[ClientConnection] = None
        self.seq_no = 0
        #: Seconds of audio sent: Speechmatics bills realtime by the second streamed.
        self.audio_seconds = 0.0
        self.opened_at: Optional[float] = None

    async def open(self) -> "SpeechmaticsASR":
        key = self._api_key or os.environ.get(config.API_KEY_ENV_VAR, "")
        if not key:
            raise SpeechmaticsError(f"{config.API_KEY_ENV_VAR} is not set")
        self.socket = await connect(self.endpoint, additional_headers={"Authorization": f"Bearer {key}"})
        self.seq_no = 0
        self.opened_at = time.time()
        await self.socket.send(json.dumps(self.start_message))
        return self

    async def send_audio(self, pcm16: bytes) -> None:
        """One chunk of 16-bit mono PCM at ``sample_rate`` (the browser sends 20 ms frames)."""
        if self.socket is None:
            raise SpeechmaticsError("socket not open")
        await self.socket.send(pcm16)
        self.seq_no += 1
        self.audio_seconds += len(pcm16) / 2 / self.sample_rate

    async def events(self) -> AsyncIterator[Transcript]:
        """Partial and final transcripts until the socket closes."""
        if self.socket is None:
            raise SpeechmaticsError("socket not open")
        async for raw in self.socket:
            if isinstance(raw, bytes):
                continue
            event = self.reader.read(raw)
            if event is None:
                continue
            kind, text = event
            if kind == "error":
                raise SpeechmaticsError(text)
            yield Transcript(text, final=(kind == "final"))

    async def close(self) -> None:
        """Send EndOfStream with the audio count, then close the socket."""
        if self.socket is None:
            return
        try:
            await self.socket.send(json.dumps(protocol.end_of_stream(self.seq_no)))
            await asyncio.wait_for(self.socket.close(), timeout=5)
        except Exception:
            pass
        self.socket = None

    async def __aenter__(self) -> "SpeechmaticsASR":
        return await self.open()

    async def __aexit__(self, *exc) -> None:
        await self.close()
