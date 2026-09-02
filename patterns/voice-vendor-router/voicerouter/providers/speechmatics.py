"""Speechmatics — both halves, and neither is shipped by Rasa.

    asr:
      name: voicerouter.providers.speechmatics.SpeechmaticsASR
      language_map: { en: { language: en } }

    tts:
      name: voicerouter.providers.speechmatics.SpeechmaticsTTS
      language_map: { en: { voice: theo } }

The two halves use completely different transports — the ASR is a realtime
websocket, the TTS is a single HTTP POST returning a WAV file. That asymmetry
inside one vendor is the normal case, not an oddity, and it is why the router
treats "provider" as a per-role choice rather than a per-vendor one.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import structlog
import websockets
from rasa.core.channels.voice_stream.asr.asr_engine import ASREngine, ASREngineConfig
from rasa.core.channels.voice_stream.asr.asr_event import (
    ASREvent,
    NewTranscript,
    UserIsSpeaking,
)
from rasa.core.channels.voice_stream.audio_bytes import (
    AudioEncoding,
    AudioFormat,
    RasaAudioBytes,
)
from rasa.core.channels.voice_stream.tts.tts_engine import (
    TTSEngineConfig,
    TTSLanguageMapEntry,
)
from websockets.legacy.client import WebSocketClientProtocol

from voicerouter.providers._http_tts import HttpStreamingTTS

logger = structlog.get_logger(__name__)

SPEECHMATICS_API_KEY_ENV_VAR = "SPEECHMATICS_API_KEY"
DEFAULT_ASR_ENDPOINT = "wss://eu.rt.speechmatics.com/v2"
DEFAULT_TTS_ENDPOINT = "https://preview.tts.speechmatics.com/generate"

_ENCODING_MAP = {
    AudioEncoding.LINEAR: "pcm_s16le",
    AudioEncoding.MULAW: "mulaw",
}


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------


class SpeechmaticsTTSConfig(TTSEngineConfig):
    endpoint: Optional[str] = None
    #: Speechmatics returns 16 kHz WAV; anything else is transcoded locally.
    output_format: Optional[str] = None


class SpeechmaticsTTS(HttpStreamingTTS):
    required_env_vars = (SPEECHMATICS_API_KEY_ENV_VAR,)
    source_sample_rate = 16000
    returns_wav = True

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

    @staticmethod
    def get_default_config(rasa_language: str) -> SpeechmaticsTTSConfig:
        return SpeechmaticsTTSConfig(
            endpoint=DEFAULT_TTS_ENDPOINT,
            output_format="wav_16000",
            timeout=30,
            language_map={rasa_language: TTSLanguageMapEntry(voice="theo")},
        )

    @classmethod
    def from_config_dict(
        cls, config: Any, format: AudioFormat, rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "SpeechmaticsTTS":
        return cls(
            rasa_language=rasa_language, format=format,
            config=SpeechmaticsTTSConfig.model_validate(config or {}),
            additional_languages=additional_languages,
        )


# ---------------------------------------------------------------------------
# ASR
# ---------------------------------------------------------------------------


class SpeechmaticsASRConfig(ASREngineConfig):
    endpoint: Optional[str] = None
    operating_point: Optional[str] = None
    max_delay: Optional[float] = None
    enable_partials: Optional[bool] = None


class SpeechmaticsASR(ASREngine[SpeechmaticsASRConfig]):
    """Realtime transcription over one websocket.

    Two protocol details that cost real time to discover:

    * Configuration is **not** in the query string, unlike Deepgram. The socket
      opens unconfigured and the first message must be `StartRecognition`;
      sending audio first gets a connection that transcribes nothing, silently.
    * `EndOfStream` must carry `last_seq_no`, the count of audio messages sent,
      so the count is tracked here rather than inferred.
    """

    required_env_vars = (SPEECHMATICS_API_KEY_ENV_VAR,)

    def __init__(self, rasa_language: str, format: AudioFormat,
                 config: Optional[SpeechmaticsASRConfig] = None,
                 additional_languages: Optional[List[str]] = None) -> None:
        super().__init__(rasa_language, format, config, additional_languages)
        self._seq_no = 0

    @classmethod
    def name(cls) -> str:
        return "speechmatics"

    def _start_recognition_message(self) -> Dict[str, Any]:
        encoding = _ENCODING_MAP.get(self.audio_format.encoding)
        if encoding is None:
            raise ValueError(
                f"Speechmatics cannot accept Rasa audio encoding "
                f"{self.audio_format.encoding!r}."
            )
        # `current_language_config` is a CurrentLanguageConfig, not the map entry
        # written in yaml: the engine-side code lives on `engine_language_key`.
        # Reading `.language` raises AttributeError on the first connection.
        language = (
            self.current_language_config.engine_language_key
            or self.current_language_config.rasa_language_key
            or "en"
        )
        return {
            "message": "StartRecognition",
            "audio_format": {
                "type": "raw", "encoding": encoding,
                "sample_rate": self.audio_format.sample_rate,
            },
            "transcription_config": {
                "language": language,
                "enable_partials": bool(self.config.enable_partials),
                "max_delay": float(self.config.max_delay),
                "operating_point": self.config.operating_point,
            },
        }

    async def open_websocket_connection(self) -> WebSocketClientProtocol:
        api_key = os.environ[SPEECHMATICS_API_KEY_ENV_VAR]
        endpoint = self.config.endpoint or DEFAULT_ASR_ENDPOINT
        try:
            socket = await websockets.connect(
                endpoint, extra_headers={"Authorization": f"Bearer {api_key}"}
            )
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(
                "speechmatics.connection.failed", status_code=e.status_code,
                error=("check your Speechmatics API key" if e.status_code == 401
                       else "connection to Speechmatics failed"),
                endpoint=endpoint,
            )
            raise
        self._seq_no = 0
        await socket.send(json.dumps(self._start_recognition_message()))
        return socket

    async def signal_audio_done(self) -> None:
        if self.asr_socket is None:
            raise AttributeError("Websocket not connected.")
        await self.asr_socket.send(
            json.dumps({"message": "EndOfStream", "last_seq_no": self._seq_no})
        )

    def rasa_audio_bytes_to_engine_bytes(self, chunk: RasaAudioBytes) -> bytes:
        # The one hook called exactly once per chunk actually sent, which makes
        # it the only correct place to count for last_seq_no.
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
            # Empty partials arrive during silence; forwarding them reads as
            # the user speaking.
            return UserIsSpeaking(text) if text else None
        if kind == "AddTranscript":
            text = message.get("metadata", {}).get("transcript", "").strip()
            return NewTranscript(text) if text else None
        if kind == "Error":
            logger.error("speechmatics.error", type=message.get("type"),
                         reason=message.get("reason"))
        return None

    @classmethod
    def from_config_dict(
        cls, config: Any, format: AudioFormat, rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "SpeechmaticsASR":
        return cls(
            rasa_language=rasa_language, format=format,
            config=SpeechmaticsASRConfig.model_validate(config or {}),
            additional_languages=additional_languages,
        )

    @staticmethod
    def get_default_config(rasa_language: str) -> SpeechmaticsASRConfig:
        from rasa.core.channels.voice_stream.asr.asr_engine import ASRLanguageMapEntry

        return SpeechmaticsASRConfig(
            endpoint=DEFAULT_ASR_ENDPOINT, operating_point="enhanced",
            max_delay=1.0, enable_partials=True,
            language_map={rasa_language: ASRLanguageMapEntry(language=rasa_language)},
        )
