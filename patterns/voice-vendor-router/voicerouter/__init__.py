"""Vendor-agnostic ASR/TTS routing for Rasa Mantle.

Point Rasa at these by dotted path, exactly as it accepts any custom engine:

    asr: { name: voicerouter.RoutedASR, providers: [...] }
    tts: { name: voicerouter.RoutedTTS, providers: [...] }
"""

from voicerouter.health import HealthRegistry, ProviderHealth
from voicerouter.routed_asr import RoutedASR
from voicerouter.routed_tts import RoutedTTS

__all__ = ["RoutedASR", "RoutedTTS", "HealthRegistry", "ProviderHealth"]
