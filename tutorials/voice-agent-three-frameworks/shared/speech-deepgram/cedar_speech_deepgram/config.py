# concern: voice-adapter
"""Deepgram settings: the defaults of Rasa 3.21.0.dev5's built-in Deepgram engines.

The Rasa variant (``variants/rasa-deepgram.integrations.yml``) names the
built-in ``deepgram`` ASR and TTS engines and leaves their settings at the
defaults; this file states the same values so the LangGraph and Strands
variants send Deepgram the same query parameters and messages.
``rasa/tests/test_speech_parity.py`` builds Rasa's engines from the variant
file and fails if the two drift.

Rasa's built-in Deepgram ASR has no field for keyterms, so no version gets
the medicine-name vocabulary the Speechmatics condition has.
"""

from __future__ import annotations

API_KEY_ENV_VAR = "DEEPGRAM_API_KEY"

#: The browser_audio wire rate; both Deepgram directions run at it (linear16).
SAMPLE_RATE = 24000

#: Streaming speech-to-text, /v1/listen (Nova). Rasa's DeepgramASR defaults.
ASR_ENDPOINT = "wss://api.deepgram.com/v1/listen"
ASR_MODEL = "nova-3"
ASR_LANGUAGE = "en"
#: Milliseconds of silence before Deepgram marks speech_final.
ASR_ENDPOINTING_MS = 400
ASR_SMART_FORMAT = True
#: Fallback: an UtteranceEnd after this long flushes what was held.
ASR_UTTERANCE_END_MS = 1000

#: Streaming text-to-speech, /v1/speak over a WebSocket. Rasa's DeepgramTTS default voice.
TTS_ENDPOINT = "wss://api.deepgram.com/v1/speak"
TTS_MODEL = "aura-2-thalia-en"


def asr_query(sample_rate: int = SAMPLE_RATE) -> dict:
    """The /v1/listen query, key for key as Rasa's ``_DeepgramV1.build_query_params``."""
    return {
        "encoding": "linear16",
        "sample_rate": sample_rate,
        "endpointing": ASR_ENDPOINTING_MS,
        "vad_events": "true",
        "language": ASR_LANGUAGE,
        "interim_results": "true",
        "model": ASR_MODEL,
        "smart_format": str(ASR_SMART_FORMAT).lower(),
        "utterance_end_ms": ASR_UTTERANCE_END_MS,
    }


def tts_query(sample_rate: int = SAMPLE_RATE) -> dict:
    """The /v1/speak query, as Rasa's ``DeepgramTTS.get_websocket_url``."""
    return {"model": TTS_MODEL, "encoding": "linear16", "sample_rate": sample_rate}
