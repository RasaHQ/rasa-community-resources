"""ElevenLabs text-to-speech — a vendor Rasa does not ship.

    tts:
      name: voicerouter.providers.elevenlabs.ElevenLabsTTS
      language_map: { en: { voice: 21m00Tcm4TlvDq8ikWAM } }
      model_id: eleven_turbo_v2_5

`voice` is an ElevenLabs **voice id**, not a display name — the API takes the id
in the path, and a friendly name there is a 404.

STATUS: written against the documented streaming API and exercised for config
and request shape, but **not** run against the live service — no ElevenLabs key
was available. Treat the first real call as the test.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from rasa.core.channels.voice_stream.audio_bytes import AudioFormat
from rasa.core.channels.voice_stream.tts.tts_engine import (
    TTSEngineConfig,
    TTSLanguageMapEntry,
)

from voicerouter.providers._http_tts import HttpStreamingTTS

ELEVENLABS_API_KEY_ENV_VAR = "ELEVENLABS_API_KEY"
DEFAULT_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # "Rachel", the documented sample voice


class ElevenLabsTTSConfig(TTSEngineConfig):
    endpoint: Optional[str] = None
    model_id: Optional[str] = None
    #: pcm_16000 / pcm_22050 / pcm_24000 / pcm_44100 — raw PCM16, no header.
    output_format: Optional[str] = None
    stability: Optional[float] = None
    similarity_boost: Optional[float] = None
    optimize_streaming_latency: Optional[int] = None


class ElevenLabsTTS(HttpStreamingTTS):
    required_env_vars = (ELEVENLABS_API_KEY_ENV_VAR,)
    returns_wav = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # The vendor's sample rate is encoded in the format name, so the
        # transcoder is told the truth rather than a hardcoded guess.
        fmt = (self.config.output_format or "pcm_24000").rsplit("_", 1)[-1]
        self.source_sample_rate = int(fmt) if fmt.isdigit() else 24000

    @classmethod
    def name(cls) -> str:
        return "elevenlabs"

    def request(self, text: str) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
        voice_id = self.current_language_config.voice or DEFAULT_VOICE
        base = self.config.endpoint or DEFAULT_ENDPOINT
        output_format = self.config.output_format or "pcm_24000"
        url = f"{base}/{quote(voice_id)}/stream?output_format={output_format}"
        if self.config.optimize_streaming_latency is not None:
            url += f"&optimize_streaming_latency={self.config.optimize_streaming_latency}"

        body: Dict[str, Any] = {
            "text": text,
            "model_id": self.config.model_id or "eleven_turbo_v2_5",
        }
        settings = {
            k: v
            for k, v in (
                ("stability", self.config.stability),
                ("similarity_boost", self.config.similarity_boost),
            )
            if v is not None
        }
        if settings:
            body["voice_settings"] = settings
        return url, {"xi-api-key": os.environ[ELEVENLABS_API_KEY_ENV_VAR]}, body

    @staticmethod
    def get_default_config(rasa_language: str) -> ElevenLabsTTSConfig:
        return ElevenLabsTTSConfig(
            endpoint=DEFAULT_ENDPOINT,
            model_id="eleven_turbo_v2_5",
            output_format="pcm_24000",
            timeout=30,
            language_map={rasa_language: TTSLanguageMapEntry(voice=DEFAULT_VOICE)},
        )

    @classmethod
    def from_config_dict(
        cls, config: Any, format: AudioFormat, rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "ElevenLabsTTS":
        return cls(
            rasa_language=rasa_language, format=format,
            config=ElevenLabsTTSConfig.model_validate(config or {}),
            additional_languages=additional_languages,
        )
