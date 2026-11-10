# concern: voice-adapter
"""Deepgram speech for the LangGraph and Strands versions, behind cedar_speech's interface.

- ``DeepgramASR``: Nova-3 streaming speech-to-text, one WebSocket per call.
- ``DeepgramTTS``: Aura-2 text-to-speech over one WebSocket per process.
- ``config``: the settings, which are the defaults of Rasa's built-in Deepgram engines.

``launch.py`` (one folder up) starts a version's unchanged ``server.py`` with
these classes in place of ``cedar_speech``'s Speechmatics ones.
"""

from cedar_speech_deepgram.asr import DeepgramASR, DeepgramError
from cedar_speech_deepgram.tts import DeepgramTTS, TTSError

__all__ = ["DeepgramASR", "DeepgramError", "DeepgramTTS", "TTSError"]
