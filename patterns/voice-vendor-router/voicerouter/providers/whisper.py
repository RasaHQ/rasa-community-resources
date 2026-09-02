"""faster-whisper — open-source, local, no API key.

    asr:
      name: voicerouter.providers.whisper.FasterWhisperASR
      model_id: tiny.en       # tiny(.en) base(.en) small(.en) medium large-v3
      device: cpu
      compute_type: int8

Whisper is a batch model: it takes a finished utterance and returns a
transcript. `LocalBufferedASR` supplies the streaming shape around it —
buffering, endpointing and off-loop execution — so this class is only the model.

Licence: the faster-whisper runtime is MIT and the Whisper weights are MIT.
Unlike NeuTTS, the model repositories are not gated, so this runs on a fresh
machine with nothing but an install.
"""

from __future__ import annotations

from typing import Any, List, Optional

from rasa.core.channels.voice_stream.asr.asr_engine import ASRLanguageMapEntry
from rasa.core.channels.voice_stream.audio_bytes import AudioFormat

from voicerouter.providers._local_asr import LocalASRConfig, LocalBufferedASR


class FasterWhisperASRConfig(LocalASRConfig):
    #: int8 is the default because it is roughly 4x faster on CPU than float32
    #: at a word-error-rate cost that does not show up in a banking dialogue.
    compute_type: Optional[str] = None
    beam_size: Optional[int] = None
    #: Force a language instead of letting Whisper detect it. Detection costs a
    #: pass over the audio and is unreliable on short turns. Named
    #: `force_language` because `language` is reserved by ASREngineConfig.
    force_language: Optional[str] = None
    vad_filter: Optional[bool] = None


class FasterWhisperASR(LocalBufferedASR):
    target_sample_rate = 16000

    @classmethod
    def name(cls) -> str:
        return "faster-whisper"

    def load_model(self) -> Any:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ModuleNotFoundError(
                "faster-whisper is not installed, so this provider is not "
                "configured here. Install with: uv pip install faster-whisper"
            ) from exc
        return WhisperModel(
            self.config.model_id or "tiny.en",
            device=self.config.device or "cpu",
            compute_type=self.config.compute_type or "int8",
        )

    def transcribe(self, pcm16: bytes, sample_rate: int) -> str:
        import numpy as np

        # faster-whisper wants float32 in [-1, 1] at 16 kHz mono.
        audio = np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0
        segments, _info = self._model.transcribe(
            audio,
            beam_size=self.config.beam_size or 1,
            language=self.config.force_language or "en",
            vad_filter=bool(self.config.vad_filter),
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    @classmethod
    def from_config_dict(
        cls, config: Any, format: AudioFormat, rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "FasterWhisperASR":
        import importlib.util

        if importlib.util.find_spec("faster_whisper") is None:
            raise ModuleNotFoundError(
                "faster-whisper is not installed, so this provider is not "
                "configured here. Install with: uv pip install faster-whisper"
            )
        return cls(
            rasa_language=rasa_language, format=format,
            config=FasterWhisperASRConfig.model_validate(config or {}),
            additional_languages=additional_languages,
        )

    @staticmethod
    def get_default_config(rasa_language: str) -> FasterWhisperASRConfig:
        return FasterWhisperASRConfig(
            model_id="tiny.en", device="cpu", compute_type="int8",
            endpoint_silence_ms=700, min_speech_ms=250, max_segment_ms=20000,
            language_map={rasa_language: ASRLanguageMapEntry(language=rasa_language)},
        )
