"""Whisper ASR Engine for local speech-to-text.

This engine integrates OpenAI Whisper as a local ASR engine compatible with
Rasa's voice channel architecture. It follows the same patterns as the
built-in Azure/Deepgram ASR engines.

The engine connects to a local Whisper service via WebSocket or uses
the whisper library directly for transcription.
"""

import json
import os
import tempfile
import asyncio
from typing import Any, List, Optional, AsyncIterator
from dataclasses import dataclass

import whisper
import structlog
import websockets
import websockets.exceptions
from websockets.legacy.client import WebSocketClientProtocol

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
    AudioFormat,
    RasaAudioBytes,
    CurrentLanguageConfig,
)
from rasa.shared.constants import VOICE_LICENSE_SCOPE
from rasa.shared.utils.common import validate_environment

logger = structlog.get_logger(__name__)


# ======================================================================================
# Configuration
# ======================================================================================


class WhisperASRConfig(ASREngineConfig):
    """Configuration for Whisper ASR.

    Attributes:
        model_size: Whisper model size (tiny, base, small, medium, large, large-v2, large-v3)
        device: Device to run on (cpu, cuda, mps)
        compute_type: Compute type for faster inference (float16, int8, etc.)
        language: Default language code
        word_timestamps: Whether to return word-level timestamps
        temperature: Temperature for sampling
        beam_size: Beam size for beam search
        best_of: Number of candidates to consider
        patience: Patience for beam search
    """

    model_size: str = "base"
    device: str = "cpu"
    compute_type: str = "float16"
    word_timestamps: bool = False
    temperature: float = 0.0
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1.0

    @classmethod
    def get_default_config(cls, rasa_language: str) -> "WhisperASRConfig":
        return cls(
            language_map={
                rasa_language: ASRLanguageMapEntry(
                    language="en",
                ),
            },
        )


# ======================================================================================
# Whisper ASR Engine
# ======================================================================================


class WhisperASR(ASREngine[WhisperASRConfig]):
    """Local Whisper ASR Engine.

    This engine runs Whisper locally for speech-to-text transcription.
    It can operate in two modes:
    1. Direct mode: Uses the whisper library directly (no WebSocket)
    2. Server mode: Connects to a local Whisper WebSocket server

    For Rasa voice channel integration, we use direct mode where the
    engine receives audio chunks and returns transcripts via callbacks.
    """

    @classmethod
    def name(cls) -> str:
        return "whisper"

    def __init__(
        self,
        rasa_language: str,
        format: AudioFormat,
        config: Optional[WhisperASRConfig] = None,
        additional_languages: Optional[List[str]] = None,
    ):
        # Initialize Whisper model
        self._whisper_model = None
        self._model_lock = asyncio.Lock()
        super().__init__(rasa_language, format, config, additional_languages)

    def _load_model(self) -> None:
        """Load the Whisper model if not already loaded."""
        if self._whisper_model is None:
            logger.info("loading_whisper_model", model_size=self.config.model_size)
            self._whisper_model = whisper.load_model(
                self.config.model_size,
                device=self.config.device,
            )
            logger.info("whisper_model_loaded")

    def _resolve_config(
        self,
        config: Optional[WhisperASRConfig],
        rasa_language: str,
    ) -> WhisperASRConfig:
        """Build final config merging defaults with provided config."""
        if config is None:
            return self.get_default_config(rasa_language)
        return config

    @classmethod
    def get_default_config(cls, rasa_language: str) -> WhisperASRConfig:
        return WhisperASRConfig(
            language_map={
                rasa_language: ASRLanguageMapEntry(
                    language="en",
                ),
            },
        )

    async def open_websocket_connection(self) -> WebSocketClientProtocol:
        """Not used in direct mode - we use the whisper library directly."""
        raise NotImplementedError("WhisperASR uses direct mode, not WebSocket")

    async def signal_audio_done(self) -> None:
        """Signal that no more audio will be sent."""
        pass

    def rasa_audio_bytes_to_engine_bytes(self, chunk: RasaAudioBytes) -> bytes:
        """Convert RasaAudioBytes to raw audio bytes for Whisper."""
        return chunk.data

    async def synthesize(self, audio_data: bytes) -> Optional[ASREvent]:
        """Transcribe audio data using Whisper.

        This is the main entry point for transcription. It saves the audio
        to a temporary file and runs Whisper transcription.
        """
        await self._ensure_model_loaded()

        try:
            # Save audio to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                # Whisper expects 16kHz mono audio
                self._save_as_wav(audio_data, temp_file.name)

                # Transcribe with Whisper
                logger.debug("transcribing_with_whisper")
                result = self._whisper_model.transcribe(
                    temp_file.name,
                    language=self.current_language_config.engine_language_key,
                    word_timestamps=self.config.word_timestamps,
                    temperature=self.config.temperature,
                    beam_size=self.config.beam_size,
                    best_of=self.config.best_of,
                    patience=self.config.patience,
                )

                # Clean up temp file
                os.unlink(temp_file.name)

                transcript = result.get("text", "").strip()
                if not transcript:
                    logger.debug("whisper_empty_transcript")
                    return None

                logger.info("whisper_transcription", text=transcript[:100])
                return NewTranscript(text=transcript)

        except Exception as e:
            logger.error("whisper_transcription_error", error=str(e))
            return None

    async def _ensure_model_loaded(self) -> None:
        """Ensure Whisper model is loaded (thread-safe)."""
        async with self._model_lock:
            if self._whisper_model is None:
                self._load_model()

    def _save_as_wav(self, audio_data: bytes, filepath: str) -> None:
        """Save raw audio bytes as WAV file for Whisper."""
        import wave
        import numpy as np

        # Convert to numpy array (assuming 16-bit PCM)
        audio_np = np.frombuffer(audio_data, dtype=np.int16)

        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(1)  # mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(16000)  # 16kHz
            wf.writeframes(audio_np.tobytes())

    def engine_event_to_asr_event(self, event: Any) -> Optional[ASREvent]:
        """Not used in direct mode."""
        return None

    async def send_keep_alive(self) -> None:
        """No keep-alive needed in direct mode."""
        pass

    @classmethod
    def from_config_dict(
        cls,
        config: dict,
        format: AudioFormat,
        rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "WhisperASR":
        """Create WhisperASR from config dictionary."""
        parsed = WhisperASRConfig.model_validate(config or {})
        return cls(
            rasa_language=rasa_language,
            format=format,
            config=parsed,
            additional_languages=additional_languages,
        )

    # Override the streaming interface for direct mode
    async def stream_asr_events(self) -> AsyncIterator[ASREvent]:
        """Override to use direct transcription instead of WebSocket streaming."""
        # In direct mode, we don't stream events via WebSocket.
        # The actual transcription happens in the synthesize() method
        # which is called by the voice channel when it has enough audio.
        yield  # Placeholder for async generator


# ======================================================================================
# Whisper ASR Server Mode (WebSocket server for local Whisper)
# ======================================================================================


async def run_whisper_server(host: str = "localhost", port: int = 8765):
    """Run a WebSocket server that exposes local Whisper for ASR.

    This allows multiple clients to connect and use local Whisper
    as an ASR service, similar to how Deepgram/Azure work.
    """
    import whisper
    from whisper.audio import SAMPLE_RATE

    model = whisper.load_model("base")
    logger.info("whisper_server_started", host=host, port=port)

    async def handle_client(websocket: WebSocketClientProtocol, path: str):
        client_addr = websocket.remote_address
        logger.info("whisper_client_connected", addr=client_addr)

        # Load model once per server (not per connection)
        model = whisper.load_model("base")

        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    # Binary audio data
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        # Save as WAV
                        import wave
                        import numpy as np

                        audio_np = np.frombuffer(message, dtype=np.int16)
                        with wave.open(f.name, 'wb') as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)
                            wf.setframerate(16000)
                            wf.writeframes(audio_np.tobytes())

                        # Transcribe
                        result = model.transcribe(f.name, language="en")
                        os.unlink(f.name)

                        transcript = result.get("text", "").strip()
                        if transcript:
                            response = {"type": "transcript", "text": transcript}
                            await websocket.send(json.dumps(response))

                elif isinstance(message, str):
                    # Control messages
                    data = json.loads(message)
                    if data.get("type") == "config":
                        # Update config
                        pass

        except websockets.exceptions.ConnectionClosedOK:
            logger.info("client_disconnected")
        except Exception as e:
            logger.error("server_error", error=str(e))

    async with websockets.serve(handle_client, host, port):
        logger.info("whisper_server_running", host=host, port=port)
        await asyncio.Future()  # Run forever