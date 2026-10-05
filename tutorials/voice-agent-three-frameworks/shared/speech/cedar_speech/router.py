# concern: voice-adapter
"""Translate the shared vendor router to the tutorial PCM/transcript interface."""
from __future__ import annotations

import asyncio
import os
import time
from typing import AsyncIterator

from cedar_speech import config
from cedar_speech.asr import SpeechmaticsASR, Transcript
from cedar_speech.tts import SpeechmaticsTTS

PROFILE_ENV = "CEDAR_VOICE_ROUTER_CONFIG"


def selected_profile():
    path = os.environ.get(PROFILE_ENV)
    if not path:
        return None
    from voicerouter.profile import VoiceProfile
    return VoiceProfile.load(path)


class RouterASR:
    def __init__(self, profile, sample_rate):
        if sample_rate != profile.sample_rate:
            raise ValueError("Caller sample rate differs from the selected speech profile")
        self.profile = profile
        self.engine = profile.build_asr()
        self.sample_rate = sample_rate
        self.audio_seconds = 0.0
        self.opened_at = None
        self._open = False

    async def open(self):
        await self.engine.connect()
        self.opened_at = time.time()
        self._open = True
        return self

    async def send_audio(self, pcm16: bytes):
        from voicerouter.engine import RasaAudioBytes
        if not self._open:
            raise RuntimeError("ASR is not open")
        if len(pcm16) % 2:
            raise ValueError("Caller audio must contain whole PCM16 samples")
        await self.engine.send_audio_chunks(RasaAudioBytes(pcm16, format=self.profile.audio_format))
        self.audio_seconds += len(pcm16) / 2 / self.sample_rate

    async def events(self):
        from voicerouter.engine import NewTranscript
        async for event in self.engine.stream_asr_events():
            yield Transcript(event.text, final=isinstance(event, NewTranscript))

    async def close(self):
        if not self._open:
            return
        try:
            await asyncio.wait_for(self.engine.signal_audio_done(), timeout=5)
        finally:
            await asyncio.wait_for(self.engine.close_connection(), timeout=5)
            self._open = False

    async def __aenter__(self):
        return await self.open()

    async def __aexit__(self, *exc):
        await self.close()


class RouterTTS:
    def __init__(self, profile):
        self.profile = profile
        self.engine = profile.build_tts()
        self.target_rate = profile.sample_rate
        self.characters = 0
        self.last_timings = {}

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        began = time.monotonic()
        first_audio_s = None
        emitted = 0
        # This is requested text, not an invoice. Failed requests and retries
        # must be accounted for by the provider request journal separately.
        self.characters += len(text)
        try:
            async for chunk in self.engine.synthesize(text):
                if chunk.data and first_audio_s is None:
                    first_audio_s = time.monotonic() - began
                emitted += len(chunk.data)
                yield chunk.data
        finally:
            self.last_timings = {"chars": len(text), "first_audio_s": first_audio_s,
                                 "headers_s": None, "total_s": time.monotonic() - began,
                                 "audio_s": emitted / 2 / self.target_rate,
                                 "provider": self.engine.active_provider}

    async def synthesize(self, text: str):
        return b"".join([chunk async for chunk in self.stream(text)])

    async def close(self):
        await self.engine.close_connection()


def create_asr(sample_rate=config.SAMPLE_RATE):
    profile = selected_profile()
    if profile: return RouterASR(profile, sample_rate)
    # Existing vendor launchers replace these exported constructors before the
    # server starts. Resolve at call time so their baseline stays reproducible.
    from cedar_speech import SpeechmaticsASR as client
    return client(sample_rate)


def create_tts():
    profile = selected_profile()
    if profile: return RouterTTS(profile)
    from cedar_speech import SpeechmaticsTTS as client
    return client()
