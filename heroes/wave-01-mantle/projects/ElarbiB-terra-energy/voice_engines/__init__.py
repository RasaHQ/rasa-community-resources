"""Entry points for custom voice engines.

This module registers custom ASR/TTS engines so Rasa can discover them
by name in the integrations.yml configuration.
"""

# Import to register engines
from .whisper_asr import WhisperASR, WhisperASRConfig
from .neuphonic_tts import NeuphonicTTS, NeuphonicTTSConfig, LocalTTSEngine

__all__ = [
    "WhisperASR",
    "WhisperASRConfig",
    "NeuphonicTTS",
    "NeuphonicTTSConfig",
    "LocalTTSEngine",
]

# Engine name mappings for Rasa to discover
ENGINE_REGISTRY = {
    "asr": {
        "whisper": WhisperASR,
    },
    "tts": {
        "neuphonic": NeuphonicTTS,
        "local_tts": LocalTTSEngine,
    },
}