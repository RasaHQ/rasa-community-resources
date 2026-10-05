"""Rime HTTP streaming TTS, usable with or without Rasa.

Implements the documented /v1/rime-tts protocol. Select an explicit model,
voice and language; live availability depends on the account. HTTP PCM is
little-endian according to Rime's API documentation (despite the L16 MIME name).
Reference: https://docs.rime.ai/api-reference/coda/http
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from voicerouter.engine import AudioFormat, TTSEngineConfig, TTSLanguageMapEntry
from voicerouter.providers._http_tts import HttpStreamingTTS

DEFAULT_ENDPOINT = "https://users.rime.ai/v1/rime-tts"


class RimeTTSConfig(TTSEngineConfig):
    endpoint: Optional[str] = None
    model_id: Optional[str] = None
    sampling_rate: int = 24000


class RimeTTS(HttpStreamingTTS):
    required_env_vars = ("RIME_API_KEY",)
    returns_wav = False

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        if self.config.sampling_rate not in {8000, 16000, 22050, 24000, 44100, 48000}:
            raise ValueError("Unsupported Rime PCM sampling rate")
        self.source_sample_rate = self.config.sampling_rate
        if not self.current_language_config.voice or not self.current_language_config.engine_language_key:
            raise ValueError("Rime needs an explicit voice and provider language")

    @classmethod
    def name(cls) -> str:
        return "rime-shared"

    def request(self, text: str) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
        return (
            self.config.endpoint or DEFAULT_ENDPOINT,
            {"Authorization": "Bearer " + os.environ["RIME_API_KEY"], "Accept": "audio/L16"},
            {"text": text, "modelId": self.config.model_id or "coda",
             "speaker": self.current_language_config.voice,
             "lang": self.current_language_config.engine_language_key,
             "samplingRate": self.source_sample_rate},
        )

    @staticmethod
    def get_default_config(rasa_language: str) -> RimeTTSConfig:
        return RimeTTSConfig(endpoint=DEFAULT_ENDPOINT, model_id="coda", sampling_rate=24000,
                             timeout=30, language_map={rasa_language: TTSLanguageMapEntry(
                                 voice="astra", language=rasa_language)})

    @classmethod
    def from_config_dict(cls, config: Any, format: AudioFormat, rasa_language: str,
                         additional_languages: Optional[List[str]] = None):
        return cls(rasa_language=rasa_language, format=format,
                   config=RimeTTSConfig.model_validate(config or {}),
                   additional_languages=additional_languages)
