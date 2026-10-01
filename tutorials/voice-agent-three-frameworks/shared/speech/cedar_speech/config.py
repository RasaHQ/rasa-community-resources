# concern: voice-adapter
"""Speechmatics settings shared with the Rasa version's integrations.yml.

The Rasa version sets the same values in YAML (``rasa/integrations.yml``,
``channels.browser_audio``); ``rasa/tests/test_speech_parity.py`` fails if
they drift, so all three versions make identical vendor calls.
"""

from __future__ import annotations

API_KEY_ENV_VAR = "SPEECHMATICS_API_KEY"

#: The browser_audio wire rate. The shared caller fixtures are 24 kHz, and
#: Speechmatics realtime takes raw pcm_s16le at the stream's own rate.
SAMPLE_RATE = 24000

#: Realtime speech-to-text (EU endpoint, as in the companion's adapter).
ASR_ENDPOINT = "wss://eu.rt.speechmatics.com/v2"
ASR_SETTINGS = {
    "language": "en",
    # The higher-accuracy operating point: names, dates, medicine names.
    "operating_point": "enhanced",
    # Seconds Speechmatics may wait before finalising a segment.
    "max_delay": 1.0,
    "enable_partials": True,
    # Speechmatics finalises a word or two at a time. With this set it sends
    # EndOfUtterance after 0.7 s of silence and the segments are joined into
    # one transcript per caller turn (the Northgate dispute build saw one
    # 14-second turn become 19 user turns without it).
    "end_of_utterance_silence_trigger": 0.7,
}
#: Custom vocabulary: the clinic's medicine names, known before any call
#: (the same list the earlier on-device build gave Whisper as hotwords).
#: No patient names: a caller's name is not known until they say it.
ADDITIONAL_VOCAB = [
    "Cedar Clinic", "lisinopril", "atorvastatin", "albuterol", "budesonide", "lorazepam", "simvastatin",
    "metformin", "sertraline", "amoxicillin",
]

#: Text-to-speech (preview API; one POST per utterance, a WAV file back).
TTS_ENDPOINT = "https://preview.tts.speechmatics.com/generate"
TTS_VOICE = "megan"
#: The API accepts wav_16000 or pcm_16000 only (checked 2026-09-30: other
#: values return HTTP 422). The audio is resampled to SAMPLE_RATE locally.
TTS_OUTPUT_FORMAT = "wav_16000"
TTS_SOURCE_RATE = 16000
