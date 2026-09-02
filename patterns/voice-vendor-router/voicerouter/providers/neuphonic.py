"""Neuphonic NeuTTS — text-to-speech that runs on this machine.

    tts:
      name: voicerouter.providers.neuphonic.NeuTTSLocal
      backbone_repo: neuphonic/neutts-nano
      ref_audio: /path/to/reference.wav      # ~3s of the voice to clone
      ref_text:  /path/to/reference.txt      # its exact transcript

This is the provider that makes the router's headline claim true. Every other
vendor here is a network call away from failing; a local model is the end of the
failover chain that cannot go down because someone else's region did. Put it
last in `providers:` and the agent stops being able to go silent.

Three things make it different from every other adapter in this package, and all
three shape the code:

**It is CPU-bound, not IO-bound.** `NeuTTS.infer` is a synchronous forward pass.
Awaiting it directly would block the event loop for the whole utterance —
freezing every other call on the process, not just this one. Everything runs in
a worker thread.

**It needs a reference voice.** NeuTTS clones from ~3 seconds of audio plus its
exact transcript. There is no built-in voice, so `ref_audio`/`ref_text` (or a
pre-encoded `ref_codes`) are required configuration rather than optional colour.

**Streaming is GGUF-only.** A `-q4-gguf` or `-q8-gguf` backbone yields audio in
chunks as it generates; the PyTorch backbones return the whole utterance at
once. Both work here — the difference is only how soon the first byte arrives —
and `supports_streaming` reports which one you got.

LICENCE, worth reading before shipping: the models are not uniformly open.
NeuTTS-Air is Apache 2.0; NeuTTS-Nano and NeuTTS-2E are under the *NeuTTS Open
License 1.0*, which is a different document with different terms. This adapter
is Apache 2.0 like the rest of this catalogue, but the weights you point it at
are not necessarily. No model or reference audio is vendored here for that
reason.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from pathlib import Path
from typing import Any, AsyncIterator, List, Optional

import structlog
from rasa.core.channels.voice_stream.audio_bytes import AudioFormat, RasaAudioBytes
from rasa.core.channels.voice_stream.tts.tts_engine import (
    TTSEngine,
    TTSEngineConfig,
    TTSError,
    TTSLanguageMapEntry,
)

from voicerouter.audio import PcmStreamConverter

logger = structlog.get_logger(__name__)

#: NeuTTS emits float32 at this rate; it is a property of the codec, not config.
NEUTTS_SAMPLE_RATE = 24000

_SENTINEL = object()


class NeuTTSLocalConfig(TTSEngineConfig):
    backbone_repo: Optional[str] = None
    codec_repo: Optional[str] = None
    backbone_device: Optional[str] = None
    codec_device: Optional[str] = None
    #: Reference voice: either a wav to encode at load, or pre-encoded codes.
    ref_audio: Optional[str] = None
    ref_codes: Optional[str] = None
    #: Exact transcript of the reference. A path or the text itself.
    ref_text: Optional[str] = None
    temperature: Optional[float] = None
    top_k: Optional[int] = None
    #: NeuTTS-2E only.
    emotion: Optional[str] = None


class NeuTTSLocal(TTSEngine):
    """Local, on-device TTS with no API key and no network at synthesis time."""

    # No credentials: that is the entire point, and it is also why the router
    # never skips this provider for want of a key.
    required_env_vars = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tts: Any = None
        self._ref_codes: Any = None
        self._ref_text: str = ""
        self._load_lock = asyncio.Lock()

    @classmethod
    def name(cls) -> str:
        return "neutts"

    @property
    def supports_streaming(self) -> bool:
        """True for GGUF backbones, which yield audio as they generate."""
        return bool(getattr(self._tts, "_is_quantized_model", False))

    # ---- loading ------------------------------------------------------------

    def _resolve_ref_text(self) -> str:
        value = self.config.ref_text
        if not value:
            raise TTSError(
                "NeuTTSLocal needs `ref_text`: NeuTTS clones a voice from a "
                "short reference, and the transcript must match the audio."
            )
        path = Path(value)
        # A transcript is short; treating an existing path as a file and
        # anything else as the literal text keeps both spellings working.
        return path.read_text(encoding="utf-8").strip() if path.is_file() else value

    def _load_blocking(self) -> None:
        """Import, construct and warm the model. Runs in a worker thread."""
        try:
            from neutts import NeuTTS
        except ImportError as exc:
            raise TTSError(
                "NeuTTSLocal needs the optional `neutts` package, which is not "
                "installed. It is optional because it pulls torch and "
                "transformers — a large install that everyone using the router "
                "should not pay for. Install with: uv pip install 'neutts>=1.4.1'"
            ) from exc

        self._ref_text = self._resolve_ref_text()
        tts = NeuTTS(
            backbone_repo=self.config.backbone_repo or "neuphonic/neutts-nano",
            backbone_device=self.config.backbone_device or "cpu",
            codec_repo=self.config.codec_repo or "neuphonic/neucodec",
            codec_device=self.config.codec_device or "cpu",
        )

        if self.config.ref_codes:
            import torch

            self._ref_codes = torch.load(self.config.ref_codes, weights_only=True)
        elif self.config.ref_audio:
            # Encoding at load costs a second once, rather than per utterance.
            self._ref_codes = tts.encode_reference(self.config.ref_audio)
        else:
            raise TTSError(
                "NeuTTSLocal needs `ref_audio` (a ~3s wav) or `ref_codes` (a "
                "pre-encoded .pt). There is no default voice to fall back on."
            )
        self._tts = tts

    async def connect(self, config: Optional[Any] = None) -> None:
        """Load the model once, off the event loop.

        Model load is seconds, not milliseconds, and the first call pays for a
        HuggingFace download. Doing it here means the cost lands at startup
        instead of inside the first thing the agent tries to say.
        """
        async with self._load_lock:
            if self._tts is not None:
                return
            await asyncio.to_thread(self._load_blocking)
            logger.info(
                "neutts.loaded",
                backbone=self.config.backbone_repo or "neuphonic/neutts-nano",
                streaming=self.supports_streaming,
            )

    async def close_connection(self) -> None:
        # Nothing to disconnect. The model stays resident on purpose: reloading
        # it per call would cost seconds of silence.
        return None

    # ---- speaking -----------------------------------------------------------

    def _to_pcm16(self, wav: Any) -> bytes:
        """float32 in [-1, 1] -> little-endian PCM16."""
        import numpy as np

        array = np.asarray(wav, dtype=np.float32).squeeze()
        # Clip before scaling: a model overshooting 1.0 would otherwise wrap
        # around and turn a loud sample into a loud sample of the wrong sign.
        return (np.clip(array, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()

    async def synthesize(
        self, text: str, config: Optional[Any] = None
    ) -> AsyncIterator[RasaAudioBytes]:
        if self._tts is None:
            await self.connect()

        converter = PcmStreamConverter(NEUTTS_SAMPLE_RATE, self.audio_format)
        kwargs: dict[str, Any] = {}
        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature
        if self.config.top_k is not None:
            kwargs["top_k"] = self.config.top_k
        if self.config.emotion:
            kwargs["emotion"] = self.config.emotion

        if not self.supports_streaming:
            wav = await asyncio.to_thread(
                self._tts.infer, text, self._ref_codes, self._ref_text, **kwargs
            )
            audio = converter.feed(self._to_pcm16(wav))
            if audio:
                yield RasaAudioBytes(audio, format=self.audio_format)
            return

        # Streaming backbone: a *synchronous* generator running on a worker
        # thread, drained through a bounded queue. The bound matters — an
        # unbounded queue would let a fast model race ahead and buffer a whole
        # utterance in memory, which is the opposite of why you stream.
        loop = asyncio.get_running_loop()
        chunks: queue.Queue = queue.Queue(maxsize=8)

        def produce() -> None:
            try:
                for chunk in self._tts.infer_stream(
                    text, self._ref_codes, self._ref_text, **kwargs
                ):
                    chunks.put(chunk)
            except Exception as exc:  # noqa: BLE001 - forwarded to the consumer
                chunks.put(exc)
            finally:
                chunks.put(_SENTINEL)

        threading.Thread(target=produce, name="neutts-synthesis", daemon=True).start()

        while True:
            item = await loop.run_in_executor(None, chunks.get)
            if item is _SENTINEL:
                break
            if isinstance(item, BaseException):
                raise TTSError(f"NeuTTS synthesis failed: {item}") from item
            audio = converter.feed(self._to_pcm16(item))
            if audio:
                yield RasaAudioBytes(audio, format=self.audio_format)

    def engine_bytes_to_rasa_audio_bytes(self, chunk: bytes) -> RasaAudioBytes:
        return RasaAudioBytes(chunk, format=self.audio_format)

    @staticmethod
    def get_default_config(rasa_language: str) -> NeuTTSLocalConfig:
        return NeuTTSLocalConfig(
            backbone_repo="neuphonic/neutts-nano",
            codec_repo="neuphonic/neucodec",
            backbone_device="cpu",
            codec_device="cpu",
            timeout=120,
            language_map={rasa_language: TTSLanguageMapEntry(voice="reference")},
        )

    @classmethod
    def from_config_dict(
        cls, config: Any, format: AudioFormat, rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "NeuTTSLocal":
        parsed = NeuTTSLocalConfig.model_validate(config or {})

        # Checked here rather than at first speech, so an unusable local
        # provider is skipped when the router is built — the same moment a
        # provider without an API key is skipped — instead of failing over
        # mid-sentence the first time the agent tries to talk.
        import importlib.util

        if importlib.util.find_spec("neutts") is None:
            raise ModuleNotFoundError(
                "the optional `neutts` package is not installed, so NeuTTS is "
                "not configured here. Install with: uv pip install 'neutts>=1.4.1' "
                "'torchao==0.14.0'"
            )
        if not (parsed.ref_audio or parsed.ref_codes) or not parsed.ref_text:
            raise ValueError(
                "NeuTTS needs a reference voice (`ref_audio` or `ref_codes`) and "
                "its transcript (`ref_text`); without them it is not configured "
                "here. NeuTTS clones a voice rather than shipping one."
            )
        return cls(
            rasa_language=rasa_language, format=format,
            config=parsed, additional_languages=additional_languages,
        )
