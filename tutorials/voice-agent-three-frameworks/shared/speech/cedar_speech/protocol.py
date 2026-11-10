# concern: voice-adapter
"""The Speechmatics wire messages, as pure functions: no I/O.

These build exactly what the Rasa version's engine
(``rasa/engines/speechmatics.py``, a copy of the companion's
``voicerouter.providers.speechmatics``) sends, and read replies the same way,
so the three versions make identical vendor calls. The parity test in
``rasa/tests/test_speech_parity.py`` compares them message for message.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import quote

from cedar_speech import config


def start_recognition(sample_rate: int = config.SAMPLE_RATE, *, encoding: str = "pcm_s16le",
                      language: str = config.ASR_SETTINGS["language"],
                      operating_point: Optional[str] = config.ASR_SETTINGS["operating_point"],
                      max_delay: float = config.ASR_SETTINGS["max_delay"],
                      enable_partials: bool = config.ASR_SETTINGS["enable_partials"],
                      end_of_utterance_silence_trigger: Optional[float] =
                      config.ASR_SETTINGS["end_of_utterance_silence_trigger"],
                      additional_vocab: Optional[list] = None) -> dict:
    """The first message on the realtime socket. Audio sent before it is never transcribed."""
    vocab = config.ADDITIONAL_VOCAB if additional_vocab is None else additional_vocab
    transcription_config: dict[str, Any] = {
        "language": language,
        "enable_partials": bool(enable_partials),
        "max_delay": float(max_delay),
        "operating_point": operating_point,
    }
    if vocab:
        transcription_config["additional_vocab"] = [
            {"content": entry} if isinstance(entry, str) else dict(entry) for entry in vocab
        ]
    if end_of_utterance_silence_trigger is not None and end_of_utterance_silence_trigger > 0:
        transcription_config["conversation_config"] = {
            "end_of_utterance_silence_trigger": float(end_of_utterance_silence_trigger),
        }
    return {
        "message": "StartRecognition",
        "audio_format": {"type": "raw", "encoding": encoding, "sample_rate": sample_rate},
        "transcription_config": transcription_config,
    }


def end_of_stream(last_seq_no: int) -> dict:
    """The last message: last_seq_no is the number of audio messages sent."""
    return {"message": "EndOfStream", "last_seq_no": last_seq_no}


class ReplyReader:
    """Turns realtime replies into ('partial', text) and ('final', text) events.

    With an end-of-utterance trigger, final segments are held and joined, and
    one ('final', utterance) comes on EndOfUtterance; without it each final
    segment is its own ('final', text). Empty partials (sent during silence)
    are dropped. Errors come back as ('error', "type: reason").
    """

    def __init__(self, utterance_mode: bool = True) -> None:
        self.utterance_mode = utterance_mode
        self.segments: list[str] = []

    def read(self, raw: Any) -> Optional[tuple[str, str]]:
        try:
            message = json.loads(raw)
        except (TypeError, ValueError):
            return None
        kind = message.get("message")
        if kind == "AddPartialTranscript":
            text = message.get("metadata", {}).get("transcript", "").strip()
            return ("partial", text) if text else None
        if kind == "AddTranscript":
            text = message.get("metadata", {}).get("transcript", "").strip()
            if not text:
                return None
            if not self.utterance_mode:
                return ("final", text)
            self.segments.append(text)
            return ("partial", " ".join(self.segments))
        if kind == "EndOfUtterance":
            if not self.segments:
                return None
            text, self.segments = " ".join(self.segments), []
            return ("final", text)
        if kind == "Error":
            return ("error", f"{message.get('type')}: {message.get('reason')}")
        return None


def tts_request(text: str, api_key: str, *, voice: str = config.TTS_VOICE, endpoint: str = config.TTS_ENDPOINT,
                output_format: str = config.TTS_OUTPUT_FORMAT) -> tuple[str, dict, dict]:
    """(url, headers, json_body) for one utterance."""
    return (
        f"{endpoint}/{quote(voice)}?output_format={output_format}",
        {"Authorization": f"Bearer {api_key}"},
        {"text": text},
    )
