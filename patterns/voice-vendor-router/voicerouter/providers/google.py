"""Google Cloud Text-to-Speech and Speech-to-Text.

    tts:
      name: voicerouter.providers.google.GoogleTTS
      language_map: { en: { voice: en-US-Neural2-F, language: en-US } }

    asr:
      name: voicerouter.providers.google.GoogleSTT
      language_map: { en: { language: en-US } }
      project_id: my-gcp-project

Credentials come from Application Default Credentials — `gcloud auth
application-default login` locally, the attached service account on GCP —
because that is the chain the google-cloud-* libraries already implement.

Two details that shape the code:

* **Google's LINEAR16 comes back with a RIFF header.** It is a WAV file, not
  raw PCM, so the header is stripped rather than played as a burst of noise.
  `voicerouter.audio` does that and trusts the rate declared in the header over
  the rate we asked for.
* **Speech-to-Text v2 streaming is gRPC, not a websocket.** The async client
  takes an *iterator of requests* and returns an iterator of responses, so the
  config has to be the first request on the stream and audio follows. That is
  the same shape as Speechmatics' StartRecognition, arrived at differently.

STATUS: config- and shape-verified against the installed SDKs, but **not** run
against Google — no credentials were available. Treat the first real call as
the test.
"""

from __future__ import annotations

import asyncio
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
from rasa.core.channels.voice_stream.tts.tts_engine import (
    TTSEngineConfig,
    TTSLanguageMapEntry,
)

from voicerouter.providers._sdk_tts import SdkTTS

logger = structlog.get_logger(__name__)

_SENTINEL = object()


def _google_credentials_available() -> bool:
    """True when Application Default Credentials resolve.

    Same reasoning as the AWS probe: an installed SDK is not a usable provider,
    and finding that out mid-call is the failure this avoids.
    """
    try:
        import google.auth

        google.auth.default()
        return True
    except Exception:  # noqa: BLE001 - any failure means "not usable here"
        return False


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------


class GoogleTTSConfig(TTSEngineConfig):
    #: Google returns LINEAR16 as a WAV; any rate it supports is fine here.
    sample_rate: Optional[int] = None
    speaking_rate: Optional[float] = None
    pitch: Optional[float] = None
    #: MALE | FEMALE | NEUTRAL, used only when no explicit voice name is given.
    ssml_gender: Optional[str] = None


class GoogleTTS(SdkTTS):
    required_env_vars = ()  # Application Default Credentials
    returns_wav = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.source_sample_rate = int(self.config.sample_rate or 24000)

    @classmethod
    def name(cls) -> str:
        return "google-tts"

    def build_client(self) -> Any:
        try:
            from google.cloud import texttospeech
        except ImportError as exc:
            raise ModuleNotFoundError(
                "google-cloud-texttospeech is not installed, so Google TTS is "
                "not configured here. Install with: "
                "uv pip install google-cloud-texttospeech"
            ) from exc
        return texttospeech.TextToSpeechClient()

    def _language_code(self) -> str:
        return (
            self.current_language_config.engine_language_key
            or self.current_language_config.rasa_language_key
            or "en-US"
        )

    def synthesize_blocking(self, text: str) -> bytes:
        from google.cloud import texttospeech

        voice_kwargs: dict[str, Any] = {"language_code": self._language_code()}
        if self.current_language_config.voice:
            voice_kwargs["name"] = self.current_language_config.voice
        elif self.config.ssml_gender:
            voice_kwargs["ssml_gender"] = getattr(
                texttospeech.SsmlVoiceGender, self.config.ssml_gender.upper()
            )

        audio_kwargs: dict[str, Any] = {
            "audio_encoding": texttospeech.AudioEncoding.LINEAR16,
            "sample_rate_hertz": self.source_sample_rate,
        }
        if self.config.speaking_rate is not None:
            audio_kwargs["speaking_rate"] = self.config.speaking_rate
        if self.config.pitch is not None:
            audio_kwargs["pitch"] = self.config.pitch

        response = self._client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=texttospeech.VoiceSelectionParams(**voice_kwargs),
            audio_config=texttospeech.AudioConfig(**audio_kwargs),
        )
        return response.audio_content

    @staticmethod
    def get_default_config(rasa_language: str) -> GoogleTTSConfig:
        return GoogleTTSConfig(
            sample_rate=24000, timeout=30,
            language_map={
                rasa_language: TTSLanguageMapEntry(
                    voice="en-US-Neural2-F", language="en-US"
                )
            },
        )

    @classmethod
    def from_config_dict(
        cls, config: Any, format: AudioFormat, rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "GoogleTTS":
        import importlib.util

        if importlib.util.find_spec("google.cloud.texttospeech") is None:
            raise ModuleNotFoundError(
                "google-cloud-texttospeech is not installed, so Google TTS is "
                "not configured here. Install with: "
                "uv pip install google-cloud-texttospeech"
            )
        if not _google_credentials_available():
            raise ValueError(
                "Application Default Credentials could not be resolved, so "
                "Google TTS is not configured here. Try: gcloud auth "
                "application-default login"
            )
        return cls(
            rasa_language=rasa_language, format=format,
            config=GoogleTTSConfig.model_validate(config or {}),
            additional_languages=additional_languages,
        )


# ---------------------------------------------------------------------------
# ASR
# ---------------------------------------------------------------------------


class GoogleSTTConfig(ASREngineConfig):
    project_id: Optional[str] = None
    location: Optional[str] = None
    #: v2 recognizer resource, or "_" for an inline ad-hoc one.
    recognizer: Optional[str] = None
    model_name: Optional[str] = None
    enable_interim_results: Optional[bool] = None


class GoogleSTT(ASREngine[GoogleSTTConfig]):
    """Streaming recognition over Speech-to-Text v2.

    gRPC streaming is request-iterator shaped: the first message carries the
    config and audio follows. Audio arriving from Rasa is pushed onto a queue
    that feeds that iterator, so the two directions stay decoupled and a slow
    network cannot block `send_audio_chunks`.
    """

    required_env_vars = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._audio: Any = None
        self._events: Any = None
        self._pump: Any = None
        self._client: Any = None

    @classmethod
    def name(cls) -> str:
        return "google-stt"

    def _language_code(self) -> str:
        return (
            self.current_language_config.engine_language_key
            or self.current_language_config.rasa_language_key
            or "en-US"
        )

    def _recognizer_path(self) -> str:
        project = self.config.project_id
        if not project:
            raise ValueError(
                "GoogleSTT needs `project_id`; Speech-to-Text v2 addresses a "
                "recognizer by project and location. Not configured here."
            )
        location = self.config.location or "global"
        recognizer = self.config.recognizer or "_"
        return f"projects/{project}/locations/{location}/recognizers/{recognizer}"

    async def connect(self) -> None:
        try:
            from google.cloud.speech_v2 import SpeechAsyncClient
        except ImportError as exc:
            raise ModuleNotFoundError(
                "google-cloud-speech is not installed, so Google STT is not "
                "configured here. Install with: uv pip install google-cloud-speech"
            ) from exc

        self._audio = asyncio.Queue()
        self._events = asyncio.Queue()
        self._client = SpeechAsyncClient()
        self._pump = asyncio.create_task(self._run_stream())
        logger.info("google-stt.connected", language=self._language_code())

    async def _requests(self) -> AsyncIterator[Any]:
        from google.cloud.speech_v2 import types as t

        # The config must be the first message on the stream; audio after it.
        yield t.StreamingRecognizeRequest(
            recognizer=self._recognizer_path(),
            streaming_config=t.StreamingRecognitionConfig(
                config=t.RecognitionConfig(
                    explicit_decoding_config=t.ExplicitDecodingConfig(
                        encoding=t.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                        sample_rate_hertz=self.audio_format.sample_rate,
                        audio_channel_count=1,
                    ),
                    language_codes=[self._language_code()],
                    model=self.config.model_name or "long",
                ),
                streaming_features=t.StreamingRecognitionFeatures(
                    interim_results=(
                        True if self.config.enable_interim_results is None
                        else bool(self.config.enable_interim_results)
                    )
                ),
            ),
        )
        while True:
            chunk = await self._audio.get()
            if chunk is _SENTINEL:
                return
            yield t.StreamingRecognizeRequest(audio=chunk)

    async def _run_stream(self) -> None:
        try:
            responses = await self._client.streaming_recognize(requests=self._requests())
            async for response in responses:
                for result in response.results:
                    if not result.alternatives:
                        continue
                    text = (result.alternatives[0].transcript or "").strip()
                    if not text:
                        continue
                    await self._events.put(
                        NewTranscript(text) if result.is_final else UserIsSpeaking(text)
                    )
        except Exception as exc:  # noqa: BLE001 - surfaced to the router
            await self._events.put(exc)
        finally:
            await self._events.put(_SENTINEL)

    async def close_connection(self) -> None:
        if self._pump is not None:
            self._pump.cancel()
            self._pump = None
        self._client = None

    async def open_websocket_connection(self) -> Any:  # pragma: no cover
        raise NotImplementedError(
            "Google Speech-to-Text v2 streams over gRPC, not a websocket."
        )

    def rasa_audio_bytes_to_engine_bytes(self, chunk: RasaAudioBytes) -> bytes:
        return chunk.to_pcm16()

    async def send_audio_chunks(self, chunk: RasaAudioBytes) -> None:
        if self._audio is not None:
            await self._audio.put(self.rasa_audio_bytes_to_engine_bytes(chunk))

    async def signal_audio_done(self) -> None:
        if self._audio is not None:
            await self._audio.put(_SENTINEL)

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
        self._set_current_language_config(rasa_language)
        return False

    def engine_event_to_asr_event(self, e: Any) -> Optional[ASREvent]:  # pragma: no cover
        return e if isinstance(e, ASREvent) else None

    @classmethod
    def from_config_dict(
        cls, config: Any, format: AudioFormat, rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "GoogleSTT":
        import importlib.util

        if importlib.util.find_spec("google.cloud.speech_v2") is None:
            raise ModuleNotFoundError(
                "google-cloud-speech is not installed, so Google STT is not "
                "configured here. Install with: uv pip install google-cloud-speech"
            )
        parsed = GoogleSTTConfig.model_validate(config or {})
        if not parsed.project_id:
            raise ValueError(
                "GoogleSTT needs `project_id`; it is not configured here."
            )
        if not _google_credentials_available():
            raise ValueError(
                "Application Default Credentials could not be resolved, so "
                "Google STT is not configured here."
            )
        return cls(
            rasa_language=rasa_language, format=format,
            config=parsed, additional_languages=additional_languages,
        )

    @staticmethod
    def get_default_config(rasa_language: str) -> GoogleSTTConfig:
        return GoogleSTTConfig(
            location="global", recognizer="_", model_name="long",
            enable_interim_results=True,
            language_map={rasa_language: ASRLanguageMapEntry(language="en-US")},
        )
