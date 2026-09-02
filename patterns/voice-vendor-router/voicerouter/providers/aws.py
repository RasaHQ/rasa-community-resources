"""Amazon Polly (TTS) and Amazon Transcribe (ASR).

    tts:
      name: voicerouter.providers.aws.PollyTTS
      language_map: { en: { voice: Joanna } }
      engine: neural
      region: us-east-1

    asr:
      name: voicerouter.providers.aws.TranscribeASR
      language_map: { en: { language: en-US } }
      region: us-east-1

Credentials come from the normal AWS chain — environment, shared config file,
instance role — because that is what boto3 already does correctly, and
reimplementing SigV4 to avoid a dependency would be a poor trade.

Two vendor details worth knowing before you configure this:

* **Polly's PCM tops out at 16 kHz.** `OutputFormat="pcm"` accepts 8000 or
  16000 only, so 24 kHz callers get upsampled locally rather than natively. It
  is fine for telephony, which is 8 kHz anyway, and audible against a 24 kHz
  vendor on a wideband channel.
* **Transcribe streaming is not JSON over a websocket.** It is an AWS
  event-stream: binary framing with its own headers and CRCs, over a SigV4
  presigned socket. Hand-rolling it is a bad idea, so the ASR here uses the
  `amazon-transcribe` SDK, which is asyncio-native and needs no thread bridge.

STATUS: config- and shape-verified against the installed SDKs, but **not** run
against AWS — no credentials were available. Treat the first real call as the
test.
"""

from __future__ import annotations

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
from rasa.core.channels.voice_stream.audio_bytes import (
    AudioEncoding,
    AudioFormat,
    RasaAudioBytes,
)
from rasa.core.channels.voice_stream.tts.tts_engine import (
    TTSEngineConfig,
    TTSLanguageMapEntry,
)

from voicerouter.providers._sdk_tts import SdkTTS

logger = structlog.get_logger(__name__)

_SENTINEL = object()

#: Polly accepts only these rates for raw PCM.
_POLLY_PCM_RATES = (8000, 16000)


def _aws_credentials_available() -> bool:
    """True when boto3 can resolve credentials from any source it knows.

    `find_spec` only proves the SDK is installed. Without this the router would
    call a configured-looking Polly and discover the missing credentials at the
    moment it needed to speak.
    """
    try:
        import boto3

        return boto3.Session().get_credentials() is not None
    except Exception:  # noqa: BLE001 - any failure means "not usable here"
        return False


# ---------------------------------------------------------------------------
# TTS — Amazon Polly
# ---------------------------------------------------------------------------


class PollyTTSConfig(TTSEngineConfig):
    region: Optional[str] = None
    #: standard | neural | long-form | generative
    engine: Optional[str] = None
    #: 8000 or 16000; Polly refuses anything else for pcm.
    sample_rate: Optional[int] = None
    #: Pass SSML instead of plain text.
    text_type: Optional[str] = None


class PollyTTS(SdkTTS):
    required_env_vars = ()  # boto3 resolves credentials its own way
    returns_wav = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        rate = int(self.config.sample_rate or 16000)
        if rate not in _POLLY_PCM_RATES:
            raise ValueError(
                f"Polly PCM supports {_POLLY_PCM_RATES}, got {rate}. Anything "
                f"else must be resampled locally, which this adapter does from "
                f"16000 by default."
            )
        self.source_sample_rate = rate

    @classmethod
    def name(cls) -> str:
        return "polly"

    def build_client(self) -> Any:
        try:
            import boto3
        except ImportError as exc:
            raise ModuleNotFoundError(
                "boto3 is not installed, so Amazon Polly is not configured "
                "here. Install with: uv pip install boto3"
            ) from exc
        return boto3.client("polly", region_name=self.config.region or None)

    def synthesize_blocking(self, text: str) -> bytes:
        response = self._client.synthesize_speech(
            Text=text,
            TextType=self.config.text_type or "text",
            OutputFormat="pcm",
            SampleRate=str(self.source_sample_rate),
            VoiceId=self.current_language_config.voice or "Joanna",
            Engine=self.config.engine or "neural",
        )
        # Polly returns a StreamingBody; the whole utterance is one response.
        return response["AudioStream"].read()

    @staticmethod
    def get_default_config(rasa_language: str) -> PollyTTSConfig:
        return PollyTTSConfig(
            engine="neural", sample_rate=16000, text_type="text", timeout=30,
            language_map={rasa_language: TTSLanguageMapEntry(voice="Joanna")},
        )

    @classmethod
    def from_config_dict(
        cls, config: Any, format: AudioFormat, rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "PollyTTS":
        import importlib.util

        if importlib.util.find_spec("boto3") is None:
            raise ModuleNotFoundError(
                "boto3 is not installed, so Amazon Polly is not configured here. "
                "Install with: uv pip install boto3"
            )
        if not _aws_credentials_available():
            raise ValueError(
                "no AWS credentials could be resolved, so Amazon Polly is not "
                "configured here. boto3 looks at the environment, the shared "
                "config file and the instance role."
            )
        return cls(
            rasa_language=rasa_language, format=format,
            config=PollyTTSConfig.model_validate(config or {}),
            additional_languages=additional_languages,
        )


# ---------------------------------------------------------------------------
# ASR — Amazon Transcribe streaming
# ---------------------------------------------------------------------------


class TranscribeASRConfig(ASREngineConfig):
    region: Optional[str] = None
    #: Transcribe's own vocabulary/customisation hooks.
    vocabulary_name: Optional[str] = None
    vocabulary_filter_name: Optional[str] = None
    show_speaker_label: Optional[bool] = None


class TranscribeASR(ASREngine[TranscribeASRConfig]):
    """Streaming transcription over AWS's event-stream protocol.

    Unlike every other ASR here this needs no thread bridge: the
    `amazon-transcribe` SDK is asyncio-native, so its stream is awaited
    directly. What it does need is a background task pumping results into a
    queue, because the SDK's handler pattern pushes events at you rather than
    letting you pull them.
    """

    required_env_vars = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stream: Any = None
        self._events: Any = None
        self._pump: Any = None

    @classmethod
    def name(cls) -> str:
        return "transcribe"

    def _media_encoding(self) -> str:
        if self.audio_format.encoding == AudioEncoding.MULAW:
            return "pcm"  # Transcribe has no mu-law; audio is converted below.
        return "pcm"

    async def connect(self) -> None:
        import asyncio

        try:
            from amazon_transcribe.client import TranscribeStreamingClient
        except ImportError as exc:
            raise ModuleNotFoundError(
                "amazon-transcribe is not installed, so Amazon Transcribe is "
                "not configured here. Install with: uv pip install amazon-transcribe"
            ) from exc

        self._events = asyncio.Queue()
        client = TranscribeStreamingClient(region=self.config.region or "us-east-1")
        language = (
            self.current_language_config.engine_language_key
            or self.current_language_config.rasa_language_key
            or "en-US"
        )
        kwargs: dict[str, Any] = {
            "language_code": language,
            "media_sample_rate_hz": self.audio_format.sample_rate,
            "media_encoding": self._media_encoding(),
        }
        if self.config.vocabulary_name:
            kwargs["vocabulary_name"] = self.config.vocabulary_name
        if self.config.vocabulary_filter_name:
            kwargs["vocab_filter_name"] = self.config.vocabulary_filter_name
        self._stream = await client.start_stream_transcription(**kwargs)
        self._pump = asyncio.create_task(self._drain())
        logger.info("transcribe.connected", language=language,
                    rate=self.audio_format.sample_rate)

    async def _drain(self) -> None:
        """Forward SDK events into the queue this engine yields from."""
        try:
            async for event in self._stream.output_stream:
                results = getattr(event, "transcript", None)
                if results is None:
                    continue
                for result in results.results:
                    if not result.alternatives:
                        continue
                    text = (result.alternatives[0].transcript or "").strip()
                    if not text:
                        continue
                    # is_partial is Transcribe's own turn boundary, which is
                    # exactly the partial/final split Rasa's turn-taking wants.
                    await self._events.put(
                        UserIsSpeaking(text) if result.is_partial else NewTranscript(text)
                    )
        except Exception as exc:  # noqa: BLE001 - surfaced to the router
            await self._events.put(exc)
        finally:
            await self._events.put(_SENTINEL)

    async def close_connection(self) -> None:
        if self._pump is not None:
            self._pump.cancel()
            self._pump = None
        self._stream = None

    async def open_websocket_connection(self) -> Any:  # pragma: no cover
        raise NotImplementedError(
            "Amazon Transcribe uses an AWS event-stream, not a plain websocket; "
            "the SDK owns the connection."
        )

    def rasa_audio_bytes_to_engine_bytes(self, chunk: RasaAudioBytes) -> bytes:
        return chunk.to_pcm16()

    async def send_audio_chunks(self, chunk: RasaAudioBytes) -> None:
        if self._stream is None:
            return
        # to_pcm16 converts mu-law telephony audio, which Transcribe cannot
        # accept directly.
        await self._stream.input_stream.send_audio_event(
            audio_chunk=self.rasa_audio_bytes_to_engine_bytes(chunk)
        )

    async def signal_audio_done(self) -> None:
        if self._stream is not None:
            await self._stream.input_stream.end_stream()

    async def send_keep_alive(self) -> None:
        return None

    async def stream_asr_events(self) -> AsyncIterator[ASREvent]:
        while True:
            item = await self._events.get()
            if item is _SENTINEL:
                return
            if isinstance(item, BaseException):
                raise item
            yield item

    async def set_language(self, rasa_language: str) -> bool:
        # Transcribe fixes the language when the stream opens, so switching
        # means a new stream rather than a live change.
        self._set_current_language_config(rasa_language)
        return False

    def engine_event_to_asr_event(self, e: Any) -> Optional[ASREvent]:  # pragma: no cover
        return e if isinstance(e, ASREvent) else None

    @classmethod
    def from_config_dict(
        cls, config: Any, format: AudioFormat, rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "TranscribeASR":
        import importlib.util

        if importlib.util.find_spec("amazon_transcribe") is None:
            raise ModuleNotFoundError(
                "amazon-transcribe is not installed, so Amazon Transcribe is "
                "not configured here. Install with: uv pip install amazon-transcribe"
            )
        if not _aws_credentials_available():
            raise ValueError(
                "no AWS credentials could be resolved, so Amazon Transcribe is "
                "not configured here."
            )
        return cls(
            rasa_language=rasa_language, format=format,
            config=TranscribeASRConfig.model_validate(config or {}),
            additional_languages=additional_languages,
        )

    @staticmethod
    def get_default_config(rasa_language: str) -> TranscribeASRConfig:
        return TranscribeASRConfig(
            region="us-east-1",
            language_map={rasa_language: ASRLanguageMapEntry(language="en-US")},
        )
