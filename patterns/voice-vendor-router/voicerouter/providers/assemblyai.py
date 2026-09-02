"""AssemblyAI realtime speech-to-text — a vendor Rasa does not ship.

    asr:
      name: voicerouter.providers.assemblyai.AssemblyAIASR
      language_map: { en: { language: en } }

STATUS: written against the documented v3 streaming API and exercised for config
and URL shape, but **not** run against the live service — no AssemblyAI key was
available. Treat the first real call as the test.

Protocol shape, for whoever runs it first: configuration goes in the query
string (unlike Speechmatics), the socket is authenticated with a bare
`Authorization` header (no `Bearer`), audio is sent as raw binary frames, and
turns arrive as `Turn` messages carrying `transcript` plus an `end_of_turn`
flag — which is the natural boundary between `UserIsSpeaking` and
`NewTranscript`.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

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
from websockets.legacy.client import WebSocketClientProtocol

logger = structlog.get_logger(__name__)

ASSEMBLYAI_API_KEY_ENV_VAR = "ASSEMBLYAI_API_KEY"
DEFAULT_ENDPOINT = "wss://streaming.assemblyai.com/v3/ws"

_ENCODING_MAP = {
    AudioEncoding.LINEAR: "pcm_s16le",
    AudioEncoding.MULAW: "pcm_mulaw",
}


class AssemblyAIASRConfig(ASREngineConfig):
    endpoint: Optional[str] = None
    #: Silence, in ms, after which AssemblyAI closes a turn.
    end_of_turn_confidence_threshold: Optional[float] = None
    min_end_of_turn_silence_when_confident: Optional[int] = None
    format_turns: Optional[bool] = None


class AssemblyAIASR(ASREngine[AssemblyAIASRConfig]):
    required_env_vars = (ASSEMBLYAI_API_KEY_ENV_VAR,)

    @classmethod
    def name(cls) -> str:
        return "assemblyai"

    def _url(self) -> str:
        encoding = _ENCODING_MAP.get(self.audio_format.encoding)
        if encoding is None:
            raise ValueError(
                f"AssemblyAI cannot accept Rasa audio encoding "
                f"{self.audio_format.encoding!r}."
            )
        params: Dict[str, Any] = {
            "sample_rate": self.audio_format.sample_rate,
            "encoding": encoding,
        }
        if self.config.format_turns is not None:
            params["format_turns"] = str(bool(self.config.format_turns)).lower()
        if self.config.end_of_turn_confidence_threshold is not None:
            params["end_of_turn_confidence_threshold"] = (
                self.config.end_of_turn_confidence_threshold
            )
        if self.config.min_end_of_turn_silence_when_confident is not None:
            params["min_end_of_turn_silence_when_confident"] = (
                self.config.min_end_of_turn_silence_when_confident
            )
        return f"{self.config.endpoint or DEFAULT_ENDPOINT}?{urlencode(params)}"

    async def open_websocket_connection(self) -> WebSocketClientProtocol:
        api_key = os.environ[ASSEMBLYAI_API_KEY_ENV_VAR]
        try:
            # Bare key, not "Bearer <key>" — the v3 endpoint rejects the latter.
            return await websockets.connect(
                self._url(), extra_headers={"Authorization": api_key}
            )
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(
                "assemblyai.connection.failed", status_code=e.status_code,
                error=("check your AssemblyAI API key" if e.status_code == 401
                       else "connection to AssemblyAI failed"),
            )
            raise

    async def signal_audio_done(self) -> None:
        if self.asr_socket is None:
            raise AttributeError("Websocket not connected.")
        await self.asr_socket.send(json.dumps({"type": "Terminate"}))

    def rasa_audio_bytes_to_engine_bytes(self, chunk: RasaAudioBytes) -> bytes:
        return chunk.data

    def engine_event_to_asr_event(self, e: Any) -> Optional[ASREvent]:
        try:
            message = json.loads(e)
        except (TypeError, ValueError):
            return None
        if message.get("type") != "Turn":
            if message.get("type") == "Error":
                logger.error("assemblyai.error", error=message.get("error"))
            return None
        text = (message.get("transcript") or "").strip()
        if not text:
            return None
        # `end_of_turn` is AssemblyAI's own turn boundary, which is exactly the
        # partial/final distinction Rasa's turn-taking needs.
        return NewTranscript(text) if message.get("end_of_turn") else UserIsSpeaking(text)

    @classmethod
    def from_config_dict(
        cls, config: Any, format: AudioFormat, rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "AssemblyAIASR":
        return cls(
            rasa_language=rasa_language, format=format,
            config=AssemblyAIASRConfig.model_validate(config or {}),
            additional_languages=additional_languages,
        )

    @staticmethod
    def get_default_config(rasa_language: str) -> AssemblyAIASRConfig:
        from rasa.core.channels.voice_stream.asr.asr_engine import ASRLanguageMapEntry

        return AssemblyAIASRConfig(
            endpoint=DEFAULT_ENDPOINT, format_turns=True,
            language_map={rasa_language: ASRLanguageMapEntry(language=rasa_language)},
        )
