"""Provider transport boundary; Rasa is optional for library consumers.

When Rasa is installed, use its public voice types so existing channel plugins
retain their contract. Otherwise providers use the small transport interfaces
below. Routing, vendor requests and audio conversion are shared in both cases.
An installed but broken Rasa installation fails rather than silently changing
runtime. No framework SDK is imported by the standalone transport.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

RASA_AVAILABLE = importlib.util.find_spec("rasa") is not None

if RASA_AVAILABLE:
    from rasa.core.channels.voice_stream.audio_bytes import AudioEncoding, AudioFormat, RasaAudioBytes, L16_16KHZ, L16_24KHZ, L16_48KHZ, MULAW_8KHZ
    from rasa.core.channels.voice_stream.asr.asr_event import ASREvent, NewTranscript, UserIsSpeaking
    from rasa.core.channels.voice_stream.asr.asr_engine import ASREngine, ASREngineConfig, ASRLanguageMapEntry
    from rasa.core.channels.voice_stream.tts.tts_engine import TTSEngine, TTSEngineConfig, TTSError, TTSLanguageMapEntry, StreamState
else:
    class AudioEncoding(str, Enum):
        LINEAR = "linear"
        MULAW = "mulaw"

    @dataclass(frozen=True)
    class AudioFormat:
        encoding: AudioEncoding
        sample_rate: int
        bit_depth: int = 16
        channels: int = 1

        @property
        def bytes_per_second(self):
            return self.sample_rate * (self.bit_depth // 8)

    @dataclass(frozen=True)
    class RasaAudioBytes:
        data: bytes
        format: AudioFormat

    @dataclass(frozen=True)
    class ASREvent:
        text: str

    class NewTranscript(ASREvent):
        pass

    class UserIsSpeaking(ASREvent):
        pass

    class StreamState(str, Enum):
        NO_STREAMING = "no_streaming"
        INTERRUPTED = "interrupted"

    class TTSError(RuntimeError):
        pass

    class ASRLanguageMapEntry(BaseModel):
        model_config = ConfigDict(extra="allow")
        language: str | None = None
        model: str | None = None

    class TTSLanguageMapEntry(ASRLanguageMapEntry):
        voice: str | None = None

    class ASREngineConfig(BaseModel):
        model_config = ConfigDict(extra="forbid")
        language_map: dict[str, ASRLanguageMapEntry] = Field(default_factory=dict)
        keep_alive_interval: float | None = None
        timeout: float = 30

    class TTSEngineConfig(BaseModel):
        timeout: float = 30
        model_config = ConfigDict(extra="forbid")
        language_map: dict[str, TTSLanguageMapEntry] = Field(default_factory=dict)

    C = TypeVar("C", bound=BaseModel)

    class _Engine(Generic[C]):
        required_env_vars: tuple[str, ...] = ()

        def __init__(self, rasa_language: str, format: AudioFormat,
                     config: C | None = None, additional_languages: list[str] | None = None):
            missing = [name for name in self.required_env_vars if not os.environ.get(name)]
            if missing:
                raise ValueError("Missing environment variables: " + ", ".join(missing))
            defaults = self.get_default_config(rasa_language)
            supplied = config.model_dump(exclude_unset=True, exclude_none=True) if config is not None else {}
            self.config = type(defaults).model_validate({**defaults.model_dump(), **supplied})
            self.audio_format = format
            self.additional_languages = additional_languages or []
            self._set_current_language_config(rasa_language)

        def _set_current_language_config(self, language: str):
            entry = self.config.language_map.get(language)
            if entry is None:
                raise ValueError(f"No provider language mapping for {language}")
            self.current_language_config = SimpleNamespace(
                rasa_language_key=language, engine_language_key=entry.language,
                voice=getattr(entry, "voice", None), model=getattr(entry, "model", None))

        async def set_language(self, language: str):
            self._set_current_language_config(language)
            return True

        async def __aenter__(self):
            await self.connect()
            return self

        async def __aexit__(self, *exc):
            await self.close_connection()

    class ASREngine(_Engine[C]):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.asr_socket = None

        async def connect(self):
            self.asr_socket = await self.open_websocket_connection()

        async def send_audio_chunks(self, chunk: RasaAudioBytes):
            if self.asr_socket is None:
                raise RuntimeError("ASR socket is not connected")
            await self.asr_socket.send(self.rasa_audio_bytes_to_engine_bytes(chunk))

        async def set_language(self, language: str):
            active = self.asr_socket is not None
            if self.current_language_config.rasa_language_key == language:
                return True
            self._set_current_language_config(language)
            if active:
                await self.close_connection()
                await self.connect()
            return True

        async def stream_asr_events(self):
            if self.asr_socket is None:
                raise RuntimeError("ASR socket is not connected")
            async for raw in self.asr_socket:
                event = self.engine_event_to_asr_event(raw)
                if event is not None:
                    yield event

        async def send_keep_alive(self):
            # Provider-specific keep-alive messages must be implemented by the
            # provider. Arbitrary bytes would count as caller audio.
            return None

        async def close_connection(self):
            if self.asr_socket is not None:
                await self.asr_socket.close()
            self.asr_socket = None

    class TTSEngine(_Engine[C]):
        streaming_input = False
        stream_state = StreamState.NO_STREAMING
        stop_streaming_output_audio_chunks = False

        async def signal_interrupt(self):
            self.stop_streaming_output_audio_chunks = True
            self.stream_state = StreamState.INTERRUPTED


if not RASA_AVAILABLE:
    L16_16KHZ = AudioFormat(AudioEncoding.LINEAR, 16000)
    L16_24KHZ = AudioFormat(AudioEncoding.LINEAR, 24000)
    L16_48KHZ = AudioFormat(AudioEncoding.LINEAR, 48000)
    MULAW_8KHZ = AudioFormat(AudioEncoding.MULAW, 8000, bit_depth=8)

# Short names here refer only to implementations shipped in this package.
# Rasa-only built-ins remain available through the native Rasa factory.
_PROVIDERS = {
    "asr": {"deepgram-shared": "deepgram.DeepgramASR", "speechmatics": "speechmatics.SpeechmaticsASR",
            "assemblyai": "assemblyai.AssemblyAIASR", "vosk": "vosk.VoskASR",
            "whisper": "whisper.FasterWhisperASR", "aws": "aws.TranscribeASR",
            "google": "google.GoogleSTT"},
    "tts": {"deepgram-shared": "deepgram.DeepgramTTS", "speechmatics": "speechmatics.SpeechmaticsTTS", "openai": "openai.OpenAITTS",
            "elevenlabs": "elevenlabs.ElevenLabsTTS", "aws": "aws.PollyTTS",
            "google": "google.GoogleTTS", "neutts": "neuphonic.NeuTTSLocal",
            "neutts-native": "neutts_native.NeuTTSNative"},
}


def _factory(kind: str, config: dict, format: AudioFormat, language: str, additional_languages=None):
    config = dict(config)
    name = config.pop("name")
    if name in _PROVIDERS[kind]:
        name = "voicerouter.providers." + _PROVIDERS[kind][name]
    elif "." not in name:
        if not RASA_AVAILABLE:
            raise ValueError(f"{name!r} is a Rasa-only built-in; use a shared provider or dotted path")
        module = importlib.import_module("rasa.core.channels.voice_stream.voice_channel")
        return getattr(module, kind + "_engine_from_config")({"name": name, **config}, format, language, additional_languages)
    module, cls = name.rsplit(".", 1)
    return getattr(importlib.import_module(module), cls).from_config_dict(config, format, language, additional_languages)


def asr_engine_from_config(config, format, rasa_language, additional_languages=None):
    return _factory("asr", config, format, rasa_language, additional_languages)


def tts_engine_from_config(config, format, rasa_language, additional_languages=None):
    return _factory("tts", config, format, rasa_language, additional_languages)


S = TypeVar("S", bound=ASREngineConfig)


class SocketASR(ASREngine[S]):
    """Expose transport errors to routing in both native and standalone runtimes."""
    async def stream_asr_events(self):
        if self.asr_socket is None:
            raise RuntimeError("ASR socket is not connected")
        async for raw in self.asr_socket:
            event = self.engine_event_to_asr_event(raw)
            if event is not None:
                yield event
