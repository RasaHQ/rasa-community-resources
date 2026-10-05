"""One versioned speech profile shared by framework transports and Rasa."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from voicerouter.engine import AudioEncoding, AudioFormat
from voicerouter.routed_asr import RoutedASR
from voicerouter.routed_tts import RoutedTTS


class VoiceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    id: str
    revision: str
    language: str = "en"
    sample_rate: int = Field(default=24000, gt=0)
    asr: dict
    tts: dict

    @model_validator(mode="after")
    def validate_profile(self):
        if self.schema_version != 1:
            raise ValueError("Unsupported speech profile schema")
        if not self.id or not self.revision:
            raise ValueError("Profile id and revision must be explicit")
        # Profiles contain rebuild settings, never credential values.
        def inspect(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key.lower() in {"api_key", "token", "password", "authorization", "secret", "credentials"}:
                        raise ValueError("Credentials belong in the authorized environment, not a speech profile")
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)
        for kind in ("asr", "tts"):
            section = getattr(self, kind)
            if not section.get("providers"):
                raise ValueError(f"Profile needs {kind} providers")
            if "name" in section:
                raise ValueError("Section contains router settings only; names belong inside providers")
            inspect(section)
        return self

    @classmethod
    def load(cls, path: str | Path):
        return cls.model_validate(json.loads(Path(path).read_text()))

    @property
    def fingerprint(self):
        canonical = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    @property
    def audio_format(self):
        return AudioFormat(encoding=AudioEncoding.LINEAR, bit_depth=16, sample_rate=self.sample_rate)

    def engines(self):
        return self.build_asr(), self.build_tts()

    def build_asr(self):
        return RoutedASR.from_config_dict(self.asr, self.audio_format, self.language)

    def build_tts(self):
        return RoutedTTS.from_config_dict(self.tts, self.audio_format, self.language)
