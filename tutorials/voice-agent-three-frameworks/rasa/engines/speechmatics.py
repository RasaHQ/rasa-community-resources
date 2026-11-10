# concern: voice-adapter
"""Speechmatics clients implementing Rasa ASREngine and TTSEngine.

Configure these custom engines by dotted path in integrations.yml.
The browser_audio channel owns the WebSocket voice loop; these classes
handle the provider messages and audio conversion. The shared speech
package supplies the corresponding clients for the other implementations.
tests/test_speech_parity.py checks their configured provider messages.
"""

from __future__ import annotations

import audioop
import json
import os
import struct
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from urllib.parse import quote

import aiohttp
import structlog
import websockets.exceptions
from rasa.core.channels.voice_stream.asr.asr_engine import ASREngine, ASREngineConfig, ASRLanguageMapEntry
from rasa.core.channels.voice_stream.asr.asr_event import ASREvent, NewTranscript, UserIsSpeaking
from rasa.core.channels.voice_stream.audio_bytes import AudioEncoding, AudioFormat, RasaAudioBytes
from rasa.core.channels.voice_stream.tts.tts_engine import (
    TTSEngine,
    TTSEngineConfig,
    TTSError,
    TTSLanguageMapEntry,
)
from websockets.asyncio.client import ClientConnection, connect

logger = structlog.get_logger(__name__)

SPEECHMATICS_API_KEY_ENV_VAR = "SPEECHMATICS_API_KEY"
DEFAULT_ASR_ENDPOINT = "wss://eu.rt.speechmatics.com/v2"
DEFAULT_TTS_ENDPOINT = "https://preview.tts.speechmatics.com/generate"

_ENCODING_MAP = {AudioEncoding.LINEAR: "pcm_s16le", AudioEncoding.MULAW: "mulaw"}
_PCM16_WIDTH = 2


# ---------------------------------------------------------------------------
# Audio: Speechmatics TTS returns a 16 kHz WAV; the channel runs at 24 kHz.
# ---------------------------------------------------------------------------


def strip_wav_header(data: bytes) -> Tuple[bytes, Optional[int]]:
    """(pcm_payload, sample_rate) for a RIFF/WAVE blob; other input passes through."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data, None
    sample_rate: Optional[int] = None
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset: offset + 4]
        (chunk_size,) = struct.unpack("<I", data[offset + 4: offset + 8])
        body = offset + 8
        if chunk_id == b"fmt " and body + 16 <= len(data):
            sample_rate = struct.unpack("<I", data[body + 4: body + 8])[0]
        elif chunk_id == b"data":
            return data[body: body + chunk_size], sample_rate
        offset = body + chunk_size + (chunk_size % 2)
    return data, sample_rate


def to_rasa_audio(raw: bytes, source_rate: int, target: AudioFormat) -> RasaAudioBytes:
    raw, declared = strip_wav_header(raw)
    source_rate = declared or source_rate
    pcm = raw[: len(raw) - len(raw) % _PCM16_WIDTH]
    if pcm and source_rate != target.sample_rate:
        pcm, _ = audioop.ratecv(pcm, _PCM16_WIDTH, 1, source_rate, target.sample_rate, None)
    if pcm and target.encoding == AudioEncoding.MULAW:
        pcm = audioop.lin2ulaw(pcm, _PCM16_WIDTH)
    return RasaAudioBytes(pcm, format=target)


# ---------------------------------------------------------------------------
# TTS: one HTTP POST per utterance, a WAV file back.
# ---------------------------------------------------------------------------


class SpeechmaticsTTSConfig(TTSEngineConfig):
    endpoint: Optional[str] = None
    #: Speechmatics accepts wav_16000 or pcm_16000 only.
    output_format: Optional[str] = None


class SpeechmaticsTTS(TTSEngine[SpeechmaticsTTSConfig]):
    required_env_vars = (SPEECHMATICS_API_KEY_ENV_VAR,)
    source_sample_rate = 16000

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._session: Optional[aiohttp.ClientSession] = None

    @classmethod
    def name(cls) -> str:
        return "speechmatics"

    def request(self, text: str) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
        voice = self.current_language_config.voice or "theo"
        base = self.config.endpoint or DEFAULT_TTS_ENDPOINT
        fmt = self.config.output_format or "wav_16000"
        return (
            f"{base}/{quote(voice)}?output_format={fmt}",
            {"Authorization": f"Bearer {os.environ[SPEECHMATICS_API_KEY_ENV_VAR]}"},
            {"text": text},
        )

    async def connect(self, config: Optional[Any] = None) -> None:
        # A pooled session, so TCP and TLS are reused across utterances.
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close_connection(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def synthesize(self, text: str, config: Optional[Any] = None) -> AsyncIterator[RasaAudioBytes]:
        if self._session is None or self._session.closed:
            await self.connect()
        assert self._session is not None
        url, headers, body = self.request(text)
        try:
            async with self._session.post(url, json=body, headers=headers) as response:
                if response.status != 200:
                    detail = (await response.text())[:300]
                    raise TTSError(f"{self.name()} returned HTTP {response.status}: {detail}")
                # A RIFF header only makes sense on the whole blob.
                raw = await response.read()
                yield to_rasa_audio(raw, self.source_sample_rate, self.audio_format)
        except aiohttp.ClientError as exc:
            raise TTSError(f"{self.name()} request failed: {exc}") from exc

    async def send_text_chunk(self, text: str) -> None:
        raise NotImplementedError(f"{self.name()} synthesises a whole utterance per request; use synthesize().")

    async def signal_text_done(self) -> None:
        return None

    def engine_bytes_to_rasa_audio_bytes(self, chunk: bytes) -> RasaAudioBytes:
        return to_rasa_audio(chunk, self.source_sample_rate, self.audio_format)

    @staticmethod
    def get_default_config(rasa_language: str) -> SpeechmaticsTTSConfig:
        return SpeechmaticsTTSConfig(endpoint=DEFAULT_TTS_ENDPOINT, output_format="wav_16000", timeout=30,
                                     language_map={rasa_language: TTSLanguageMapEntry(voice="theo")})

    @classmethod
    def from_config_dict(cls, config: Any, format: AudioFormat, rasa_language: str,
                         additional_languages: Optional[List[str]] = None) -> "SpeechmaticsTTS":
        from cedar_speech.router import selected_profile
        profile = selected_profile()
        if profile is not None:
            if format.sample_rate != profile.sample_rate or rasa_language != profile.language:
                raise ValueError("Rasa channel format/language differs from the speech profile")
            return profile.build_tts()
        return cls(rasa_language=rasa_language, format=format,
                   config=SpeechmaticsTTSConfig.model_validate(config or {}),
                   additional_languages=additional_languages)


# ---------------------------------------------------------------------------
# ASR: realtime over one WebSocket.
# ---------------------------------------------------------------------------


class SpeechmaticsASRConfig(ASREngineConfig):
    endpoint: Optional[str] = None
    operating_point: Optional[str] = None
    max_delay: Optional[float] = None
    enable_partials: Optional[bool] = None
    #: Seconds of silence (0 to 2) after which Speechmatics sends
    #: EndOfUtterance. When set, final segments are held and joined into one
    #: transcript per utterance; unset, every final segment is its own
    #: transcript, which Rasa treats as a whole user turn.
    end_of_utterance_silence_trigger: Optional[float] = None
    #: Speechmatics custom dictionary (`additional_vocab`): strings or
    #: {"content": ..., "sounds_like": [...]} entries.
    additional_vocab: Optional[List[Any]] = None


class SpeechmaticsASR(ASREngine[SpeechmaticsASRConfig]):
    """Realtime transcription over one WebSocket.

    The socket opens unconfigured: the first message must be StartRecognition
    (audio sent first is silently never transcribed). EndOfStream carries
    last_seq_no, the count of audio messages sent. Speechmatics finalises a
    word or two at a time, and Rasa takes every NewTranscript as a whole user
    turn, so with end_of_utterance_silence_trigger set the segments are held
    until EndOfUtterance and sent as one transcript.
    """

    required_env_vars = (SPEECHMATICS_API_KEY_ENV_VAR,)

    def __init__(self, rasa_language: str, format: AudioFormat, config: Optional[SpeechmaticsASRConfig] = None,
                 additional_languages: Optional[List[str]] = None) -> None:
        super().__init__(rasa_language, format, config, additional_languages)
        self._seq_no = 0
        self._segments: List[str] = []

    @classmethod
    def name(cls) -> str:
        return "speechmatics"

    @property
    def _utterance_mode(self) -> bool:
        trigger = self.config.end_of_utterance_silence_trigger
        return trigger is not None and trigger > 0

    def _start_recognition_message(self) -> Dict[str, Any]:
        encoding = _ENCODING_MAP.get(self.audio_format.encoding)
        if encoding is None:
            raise ValueError(f"Speechmatics cannot accept Rasa audio encoding {self.audio_format.encoding!r}.")
        # current_language_config is a CurrentLanguageConfig: the engine-side
        # code is engine_language_key, not `.language`.
        language = (self.current_language_config.engine_language_key
                    or self.current_language_config.rasa_language_key or "en")
        transcription_config: Dict[str, Any] = {
            "language": language,
            "enable_partials": bool(self.config.enable_partials),
            "max_delay": float(self.config.max_delay),
            "operating_point": self.config.operating_point,
        }
        if self.config.additional_vocab:
            transcription_config["additional_vocab"] = [
                {"content": entry} if isinstance(entry, str) else dict(entry)
                for entry in self.config.additional_vocab
            ]
        if self._utterance_mode:
            transcription_config["conversation_config"] = {
                "end_of_utterance_silence_trigger": float(self.config.end_of_utterance_silence_trigger),
            }
        return {
            "message": "StartRecognition",
            "audio_format": {"type": "raw", "encoding": encoding, "sample_rate": self.audio_format.sample_rate},
            "transcription_config": transcription_config,
        }

    async def open_websocket_connection(self) -> ClientConnection:
        api_key = os.environ[SPEECHMATICS_API_KEY_ENV_VAR]
        endpoint = self.config.endpoint or DEFAULT_ASR_ENDPOINT
        try:
            socket = await connect(endpoint, additional_headers={"Authorization": f"Bearer {api_key}"})
        except websockets.exceptions.InvalidStatus as e:
            status_code = e.response.status_code
            logger.error("speechmatics.connection.failed", status_code=status_code,
                         error=("check your Speechmatics API key" if status_code == 401
                                else "connection to Speechmatics failed"), endpoint=endpoint)
            raise
        self._seq_no = 0
        self._segments = []
        await socket.send(json.dumps(self._start_recognition_message()))
        return socket

    async def signal_audio_done(self) -> None:
        if self.asr_socket is None:
            raise AttributeError("Websocket not connected.")
        await self.asr_socket.send(json.dumps({"message": "EndOfStream", "last_seq_no": self._seq_no}))

    def rasa_audio_bytes_to_engine_bytes(self, chunk: RasaAudioBytes) -> bytes:
        # Called exactly once per chunk sent: the place to count for last_seq_no.
        self._seq_no += 1
        return chunk.data

    def engine_event_to_asr_event(self, e: Any) -> Optional[ASREvent]:
        try:
            message = json.loads(e)
        except (TypeError, ValueError):
            return None
        kind = message.get("message")
        if kind == "AddPartialTranscript":
            text = message.get("metadata", {}).get("transcript", "").strip()
            # Empty partials arrive during silence; forwarding them reads as speech.
            return UserIsSpeaking(text) if text else None
        if kind == "AddTranscript":
            text = message.get("metadata", {}).get("transcript", "").strip()
            if not text:
                return None
            if not self._utterance_mode:
                return NewTranscript(text)
            self._segments.append(text)
            return UserIsSpeaking(" ".join(self._segments))
        if kind == "EndOfUtterance":
            if not self._segments:
                return None
            text, self._segments = " ".join(self._segments), []
            return NewTranscript(text)
        if kind == "Error":
            logger.error("speechmatics.error", type=message.get("type"), reason=message.get("reason"))
        return None

    @classmethod
    def from_config_dict(cls, config: Any, format: AudioFormat, rasa_language: str,
                         additional_languages: Optional[List[str]] = None) -> "SpeechmaticsASR":
        from cedar_speech.router import selected_profile
        profile = selected_profile()
        if profile is not None:
            if format.sample_rate != profile.sample_rate or rasa_language != profile.language:
                raise ValueError("Rasa channel format/language differs from the speech profile")
            return profile.build_asr()
        return cls(rasa_language=rasa_language, format=format,
                   config=SpeechmaticsASRConfig.model_validate(config or {}),
                   additional_languages=additional_languages)

    @staticmethod
    def get_default_config(rasa_language: str) -> SpeechmaticsASRConfig:
        return SpeechmaticsASRConfig(endpoint=DEFAULT_ASR_ENDPOINT, operating_point="enhanced", max_delay=1.0,
                                     enable_partials=True,
                                     language_map={rasa_language: ASRLanguageMapEntry(language=rasa_language)})
