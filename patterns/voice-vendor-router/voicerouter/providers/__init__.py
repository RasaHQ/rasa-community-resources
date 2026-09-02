"""Engine adapters for vendors Rasa does not ship.

Rasa ships ASR for azure and deepgram, and TTS for azure, cartesia, deepgram and
rime. Those work through the router already — it delegates to Rasa's own
factories. This package is for everything else.

    TTS   voicerouter.providers.openai.OpenAITTS
          voicerouter.providers.elevenlabs.ElevenLabsTTS
          voicerouter.providers.speechmatics.SpeechmaticsTTS
          voicerouter.providers.neuphonic.NeuTTSLocal      (local, no API key)

    ASR   voicerouter.providers.speechmatics.SpeechmaticsASR
          voicerouter.providers.assemblyai.AssemblyAIASR

Each is a normal Rasa engine: usable on its own, with or without the router.
`CATALOGUE` exists so `make probe` and the docs can enumerate them without
importing every vendor (and its credential check) up front.
"""

from __future__ import annotations

from typing import NamedTuple


class VendorEntry(NamedTuple):
    kind: str
    dotted_path: str
    env_var: str
    verified_live: bool
    note: str


CATALOGUE: tuple[VendorEntry, ...] = (
    VendorEntry("tts", "voicerouter.providers.openai.OpenAITTS",
                "OPENAI_API_KEY", True, "24 kHz PCM, no resampling on the common path"),
    VendorEntry("tts", "voicerouter.providers.speechmatics.SpeechmaticsTTS",
                "SPEECHMATICS_API_KEY", True, "returns 16 kHz WAV; header stripped locally"),
    VendorEntry("tts", "voicerouter.providers.elevenlabs.ElevenLabsTTS",
                "ELEVENLABS_API_KEY", False, "voice is an ElevenLabs voice id, not a name"),
    VendorEntry("asr", "voicerouter.providers.speechmatics.SpeechmaticsASR",
                "SPEECHMATICS_API_KEY", True, "config is a StartRecognition message, not a query string"),
    VendorEntry("asr", "voicerouter.providers.assemblyai.AssemblyAIASR",
                "ASSEMBLYAI_API_KEY", False, "bare Authorization header; turns carry end_of_turn"),
    VendorEntry("tts", "voicerouter.providers.neuphonic.NeuTTSLocal",
                "(none — local)", False,
                "on-device; needs the optional neutts package and a reference voice"),
)

__all__ = ["CATALOGUE", "VendorEntry"]
