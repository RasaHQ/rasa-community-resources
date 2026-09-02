"""A Speechmatics real-time ASR engine for Rasa's voice channel.

Rasa ships ASR engines for Deepgram and Azure. Speechmatics is not one of them,
so this file exists to show the supported way to add one: implement
``ASREngine`` and give Rasa the dotted path instead of a built-in name.

    # integrations.yml
    asr:
      name: engines.speechmatics.SpeechmaticsASR

Rasa resolves an unrecognised ``name`` with ``class_from_module_path`` and calls
``from_config_dict`` on it. The class is marked as a beta feature on load, which
is a log line rather than a restriction.

Protocol notes, confirmed against the live API rather than the docs alone:

* One websocket, ``wss://eu.rt.speechmatics.com/v2``, authenticated with an
  ``Authorization: Bearer`` header. Unlike Deepgram, configuration is **not**
  in the query string — the first message on the socket is ``StartRecognition``
  and nothing is transcribed until it is sent. ``open_websocket_connection``
  therefore connects *and* handshakes before returning.
* ``EndOfStream`` must carry ``last_seq_no``: the number of audio messages sent.
  Speechmatics uses it to know it has received everything, so the count is kept
  here rather than inferred.
* Transcripts arrive as ``AddPartialTranscript`` (interim, may be revised) and
  ``AddTranscript`` (final). They map onto Rasa's ``UserIsSpeaking`` and
  ``NewTranscript`` respectively, which is what drives turn-taking.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import structlog
import websockets
from pydantic import BaseModel
from websockets.legacy.client import WebSocketClientProtocol

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

logger = structlog.get_logger(__name__)

SPEECHMATICS_API_KEY_ENV_VAR = "SPEECHMATICS_API_KEY"
DEFAULT_ENDPOINT = "wss://eu.rt.speechmatics.com/v2"

# Rasa's audio encodings, in the vocabulary Speechmatics expects.
_ENCODING_MAP = {
    AudioEncoding.LINEAR: "pcm_s16le",
    AudioEncoding.MULAW: "mulaw",
}


class SpeechmaticsASRConfig(ASREngineConfig):
    """Configuration for :class:`SpeechmaticsASR`."""

    endpoint: Optional[str] = None
    # "standard" is faster and cheaper; "enhanced" is more accurate. Enhanced is
    # the default here because a misheard account number costs more than a few
    # tens of milliseconds.
    operating_point: Optional[str] = None
    # Seconds Speechmatics may buffer before emitting a final transcript. Lower
    # is snappier and slightly less accurate.
    max_delay: Optional[float] = None
    enable_partials: Optional[bool] = None


class SpeechmaticsASR(ASREngine[SpeechmaticsASRConfig]):
    """Speechmatics real-time transcription over a single websocket."""

    required_env_vars = (SPEECHMATICS_API_KEY_ENV_VAR,)

    def __init__(
        self,
        rasa_language: str,
        format: AudioFormat,
        config: Optional[SpeechmaticsASRConfig] = None,
        additional_languages: Optional[List[str]] = None,
    ) -> None:
        super().__init__(rasa_language, format, config, additional_languages)
        # Counts audio messages so EndOfStream can report last_seq_no.
        self._seq_no = 0

    @classmethod
    def name(cls) -> str:
        return "speechmatics"

    # ---- connection ---------------------------------------------------------

    def _start_recognition_message(self) -> Dict[str, Any]:
        encoding = _ENCODING_MAP.get(self.audio_format.encoding)
        if encoding is None:
            raise ValueError(
                f"Speechmatics cannot accept Rasa audio encoding "
                f"{self.audio_format.encoding!r}."
            )
        # `current_language_config` is a CurrentLanguageConfig, not the map entry
        # you wrote: the engine-side code lives on `engine_language_key`, with
        # the Rasa-side key as the fallback. Reading `.language` here raises
        # AttributeError at the first connection, not at config load.
        language = (
            self.current_language_config.engine_language_key
            or self.current_language_config.rasa_language_key
            or "en"
        )
        return {
            "message": "StartRecognition",
            "audio_format": {
                "type": "raw",
                "encoding": encoding,
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
        """Connect, then send StartRecognition before any audio flows."""
        api_key = os.environ[SPEECHMATICS_API_KEY_ENV_VAR]
        endpoint = self.config.endpoint or DEFAULT_ENDPOINT
        try:
            socket = await websockets.connect(
                endpoint, extra_headers={"Authorization": f"Bearer {api_key}"}
            )
        except websockets.exceptions.InvalidStatusCode as e:
            reason = (
                "Please make sure your Speechmatics API key is correct."
                if e.status_code == 401
                else "Connection to Speechmatics failed."
            )
            logger.error(
                "speechmatics.connection.failed",
                status_code=e.status_code,
                error=reason,
                endpoint=endpoint,
            )
            raise

        self._seq_no = 0
        await socket.send(json.dumps(self._start_recognition_message()))
        return socket

    async def signal_audio_done(self) -> None:
        """Tell Speechmatics how many audio messages it should have received."""
        if self.asr_socket is None:
            raise AttributeError("Websocket not connected.")
        await self.asr_socket.send(
            json.dumps({"message": "EndOfStream", "last_seq_no": self._seq_no})
        )

    # ---- audio in, events out -----------------------------------------------

    def rasa_audio_bytes_to_engine_bytes(self, chunk: RasaAudioBytes) -> bytes:
        """Pass raw audio straight through, counting it on the way.

        The counter lives here because this is the one hook the base class calls
        exactly once per chunk actually sent.
        """
        self._seq_no += 1
        return chunk.data

    def engine_event_to_asr_event(self, e: Any) -> Optional[ASREvent]:
        """Translate one Speechmatics websocket message into a Rasa ASR event."""
        try:
            message = json.loads(e)
        except (TypeError, ValueError):
            return None

        kind = message.get("message")

        if kind == "AddPartialTranscript":
            text = message.get("metadata", {}).get("transcript", "").strip()
            # Partials with no words arrive during silence; forwarding them
            # would read as the user speaking.
            return UserIsSpeaking(text) if text else None

        if kind == "AddTranscript":
            text = message.get("metadata", {}).get("transcript", "").strip()
            return NewTranscript(text) if text else None

        if kind == "Error":
            logger.error(
                "speechmatics.error",
                type=message.get("type"),
                reason=message.get("reason"),
            )
            return None

        # RecognitionStarted / AudioAdded / Info / EndOfTranscript carry no
        # transcript and need no Rasa-side event.
        return None

    # ---- config plumbing ----------------------------------------------------

    @classmethod
    def from_config_dict(
        cls,
        config: Any,
        format: AudioFormat,
        rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "SpeechmaticsASR":
        return cls(
            rasa_language=rasa_language,
            format=format,
            config=SpeechmaticsASRConfig.model_validate(config or {}),
            additional_languages=additional_languages,
        )

    @staticmethod
    def get_default_config(rasa_language: str) -> SpeechmaticsASRConfig:
        from rasa.core.channels.voice_stream.asr.asr_engine import ASRLanguageMapEntry

        return SpeechmaticsASRConfig(
            endpoint=DEFAULT_ENDPOINT,
            operating_point="enhanced",
            max_delay=1.0,
            enable_partials=True,
            language_map={rasa_language: ASRLanguageMapEntry(language=rasa_language)},
        )
