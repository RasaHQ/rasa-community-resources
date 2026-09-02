"""Vosk — open-source, local, and the only local ASR here that truly streams.

    asr:
      name: voicerouter.providers.vosk.VoskASR
      model_path: /path/to/vosk-model-small-en-us-0.15

Vosk is the odd one out, in a way that matters. Whisper and friends are batch
models that need buffering and endpointing bolted on. Vosk's recogniser is
natively incremental: feed it audio, ask after every chunk, and it answers
either "still going, here is the partial" or "that turn is finished". That maps
directly onto Rasa's `UserIsSpeaking` / `NewTranscript` with no VAD and no
guessing about where a turn ended — the model decides, which is what a cloud ASR
does too.

It is also small: the English model is about 40 MB and there is no torch, no
CUDA and no download gate. That combination — genuinely streaming, tiny, offline,
Apache 2.0 — makes it the most realistic last resort in a failover chain.

Models are not bundled: download one from https://alphacephei.com/vosk/models
and point `model_path` at the unpacked directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncIterator, List, Optional

import structlog
from rasa.core.channels.voice_stream.asr.asr_engine import (
    ASREngine,
    ASREngineConfig,
    ASRLanguageMapEntry,
)
from rasa.core.channels.voice_stream.asr.asr_event import (
    ASREvent,
    NewTranscript,
    UserIsSpeaking,
)
from rasa.core.channels.voice_stream.audio_bytes import AudioFormat, RasaAudioBytes

logger = structlog.get_logger(__name__)

_SENTINEL = object()


class VoskASRConfig(ASREngineConfig):
    #: Path to an unpacked Vosk model directory.
    model_path: Optional[str] = None
    #: Vosk resamples internally, but matching its rate avoids a conversion.
    sample_rate: Optional[int] = None


class VoskASR(ASREngine[VoskASRConfig]):
    required_env_vars = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._recognizer: Any = None
        self._model: Any = None
        self._events: Any = None
        self._rate = 16000

    @classmethod
    def name(cls) -> str:
        return "vosk"

    async def connect(self) -> None:
        import asyncio

        self._events = asyncio.Queue()
        if self._recognizer is None:
            self._recognizer = await asyncio.to_thread(self._build)
            logger.info("vosk.loaded", model_path=self.config.model_path, rate=self._rate)

    def _build(self) -> Any:
        from vosk import KaldiRecognizer, Model, SetLogLevel

        SetLogLevel(-1)  # Vosk is chatty on stderr by default
        path = self.config.model_path
        if not path or not Path(path).is_dir():
            raise ValueError(
                f"VoskASR needs `model_path` pointing at an unpacked Vosk model "
                f"directory; got {path!r}. Models are not bundled — download one "
                f"from https://alphacephei.com/vosk/models. Not configured here."
            )
        self._rate = int(self.config.sample_rate or 16000)
        self._model = Model(path)
        recognizer = KaldiRecognizer(self._model, self._rate)
        recognizer.SetWords(False)
        return recognizer

    async def close_connection(self) -> None:
        return None

    async def open_websocket_connection(self) -> Any:  # pragma: no cover
        raise NotImplementedError("Vosk is a local model, not a websocket service.")

    def rasa_audio_bytes_to_engine_bytes(self, chunk: RasaAudioBytes) -> bytes:
        return chunk.data

    async def send_audio_chunks(self, chunk: RasaAudioBytes) -> None:
        """Feed Vosk and let it decide whether the turn ended."""
        import asyncio
        import audioop

        pcm = chunk.to_pcm16()
        if self.audio_format.sample_rate != self._rate:
            pcm, _ = audioop.ratecv(
                pcm, 2, 1, self.audio_format.sample_rate, self._rate, None
            )
        # AcceptWaveform is the whole endpointing story: True means Vosk has
        # closed a turn on its own, which is why this engine needs no VAD.
        final = await asyncio.to_thread(self._recognizer.AcceptWaveform, pcm)
        if final:
            text = json.loads(self._recognizer.Result()).get("text", "").strip()
            if text:
                await self._events.put(NewTranscript(text))
        else:
            partial = json.loads(self._recognizer.PartialResult()).get("partial", "").strip()
            if partial:
                await self._events.put(UserIsSpeaking(partial))

    async def signal_audio_done(self) -> None:
        import asyncio

        text = json.loads(
            await asyncio.to_thread(self._recognizer.FinalResult)
        ).get("text", "").strip()
        if text:
            await self._events.put(NewTranscript(text))
        await self._events.put(_SENTINEL)

    async def send_keep_alive(self) -> None:
        return None

    async def stream_asr_events(self) -> AsyncIterator[ASREvent]:
        while True:
            item = await self._events.get()
            if item is _SENTINEL:
                return
            yield item

    async def set_language(self, rasa_language: str) -> bool:
        # One Vosk model is one language; switching means a different model.
        self._set_current_language_config(rasa_language)
        return False

    def engine_event_to_asr_event(self, e: Any) -> Optional[ASREvent]:  # pragma: no cover
        return e if isinstance(e, ASREvent) else None

    @classmethod
    def from_config_dict(
        cls, config: Any, format: AudioFormat, rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "VoskASR":
        import importlib.util

        if importlib.util.find_spec("vosk") is None:
            raise ModuleNotFoundError(
                "vosk is not installed, so this provider is not configured here. "
                "Install with: uv pip install vosk"
            )
        parsed = VoskASRConfig.model_validate(config or {})
        if not parsed.model_path or not Path(parsed.model_path).is_dir():
            raise ValueError(
                "VoskASR needs `model_path` pointing at an unpacked model "
                "directory; it is not configured here. Download one from "
                "https://alphacephei.com/vosk/models"
            )
        return cls(
            rasa_language=rasa_language, format=format,
            config=parsed, additional_languages=additional_languages,
        )

    @staticmethod
    def get_default_config(rasa_language: str) -> VoskASRConfig:
        return VoskASRConfig(
            sample_rate=16000,
            language_map={rasa_language: ASRLanguageMapEntry(language=rasa_language)},
        )
