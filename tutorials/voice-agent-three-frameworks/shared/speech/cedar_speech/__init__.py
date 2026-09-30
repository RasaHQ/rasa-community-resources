# concern: voice-adapter
"""Speechmatics speech for the voice agents that have no speech engines of their own.

- ``SpeechmaticsASR``: realtime speech-to-text over one WebSocket per call,
  with Speechmatics' end-of-utterance detection.
- ``SpeechmaticsTTS``: text-to-speech, one HTTP POST per utterance, resampled
  to the 24 kHz wire rate.
- ``protocol``: the vendor messages as pure functions (identical to the Rasa
  version's engine), ``config``: the shared settings, ``audio``: PCM helpers.

No framework imports. This is the vendor-adapter layer for the LangGraph and
Strands versions; the Rasa version has its own copy as Rasa engine classes
(``rasa/engines/speechmatics.py``).
"""

from cedar_speech.asr import SpeechmaticsASR, SpeechmaticsError, Transcript
from cedar_speech.tts import SpeechmaticsTTS, TTSError

__all__ = ["SpeechmaticsASR", "SpeechmaticsError", "SpeechmaticsTTS", "TTSError", "Transcript"]
