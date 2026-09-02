"""OpenAI text-to-speech — a vendor Rasa does not ship.

    tts:
      name: voicerouter.providers.openai.OpenAITTS
      language_map: { en: { voice: alloy } }
      model_id: gpt-4o-mini-tts

Asks for `response_format: pcm`, which OpenAI returns as 24 kHz 16-bit mono —
the same shape as Rasa's `L16_24KHZ`, so the common case needs no resampling.
Telephony (8 kHz mu-law) is converted in `voicerouter.audio`.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from rasa.core.channels.voice_stream.audio_bytes import AudioFormat
from rasa.core.channels.voice_stream.tts.tts_engine import (
    TTSEngineConfig,
    TTSLanguageMapEntry,
)

from voicerouter.providers._http_tts import HttpStreamingTTS

OPENAI_API_KEY_ENV_VAR = "OPENAI_API_KEY"
DEFAULT_ENDPOINT = "https://api.openai.com/v1/audio/speech"


class OpenAITTSConfig(TTSEngineConfig):
    endpoint: Optional[str] = None
    # `model_id`, not `model`: TTSEngineConfig keeps a deprecated top-level
    # `model` field and rejects a config that sets both it and `language_map`.
    # Rime's built-in engine uses `model_id` for the same reason.
    model_id: Optional[str] = None
    #: Free-text style prompt; the gpt-4o-mini-tts family accepts one.
    instructions: Optional[str] = None
    speed: Optional[float] = None


class OpenAITTS(HttpStreamingTTS):
    required_env_vars = (OPENAI_API_KEY_ENV_VAR,)
    source_sample_rate = 24000
    returns_wav = False

    @classmethod
    def name(cls) -> str:
        return "openai"

    def request(self, text: str) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
        body: Dict[str, Any] = {
            "model": self.config.model_id or "gpt-4o-mini-tts",
            "voice": self.current_language_config.voice or "alloy",
            "input": text,
            "response_format": "pcm",
        }
        if self.config.instructions:
            body["instructions"] = self.config.instructions
        if self.config.speed is not None:
            body["speed"] = self.config.speed
        return (
            self.config.endpoint or DEFAULT_ENDPOINT,
            {"Authorization": f"Bearer {os.environ[OPENAI_API_KEY_ENV_VAR]}"},
            body,
        )

    @staticmethod
    def get_default_config(rasa_language: str) -> OpenAITTSConfig:
        return OpenAITTSConfig(
            endpoint=DEFAULT_ENDPOINT,
            model_id="gpt-4o-mini-tts",
            timeout=30,
            language_map={rasa_language: TTSLanguageMapEntry(voice="alloy")},
        )

    @classmethod
    def from_config_dict(
        cls,
        config: Any,
        format: AudioFormat,
        rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "OpenAITTS":
        return cls(
            rasa_language=rasa_language,
            format=format,
            config=OpenAITTSConfig.model_validate(config or {}),
            additional_languages=additional_languages,
        )
