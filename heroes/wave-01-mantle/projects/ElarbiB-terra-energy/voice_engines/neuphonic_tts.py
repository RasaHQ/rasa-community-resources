"""Neuphonic TTS Engine for local/remote text-to-speech.

This engine integrates Neuphonic as a TTS engine compatible with
Rasa's voice channel architecture, following the same patterns as
the built-in Azure/Deepgram/Cartesia TTS engines.

For local development, it can also use pyttsx3 as a stand-in.
"""

import os
import json
import asyncio
from typing import AsyncIterator, Dict, List, Optional
from dataclasses import dataclass

import aiohttp
import structlog
from aiohttp import ClientTimeout, ClientWSTimeout, WSMsgType

from rasa.core.channels.voice_stream.audio_bytes import (
    L16_24KHZ,
    L16_48KHZ,
    MULAW_8KHZ,
    AudioFormat,
    RasaAudioBytes,
)
from rasa.core.channels.voice_stream.tts.tts_engine import (
    TTSEngine,
    TTSEngineConfig,
    TTSError,
    TTSLanguageMapEntry,
)
from rasa.tracing import voice as voice_tracing

logger = structlog.get_logger(__name__)


# ======================================================================================
# Configuration
# ======================================================================================


class NeuphonicTTSConfig(TTSEngineConfig):
    """Configuration for Neuphonic TTS.

    Attributes:
        api_key: Neuphonic API key (from NEUPHONIC_API_KEY env var)
        endpoint: WebSocket endpoint URL
        voice_id: Default voice ID to use
        speed: Speech speed (0.5 to 2.0)
        sample_rate: Output sample rate
    """

    api_key: Optional[str] = None
    endpoint: str = "wss://api.neuphonic.com/v1/tts/stream"
    voice_id: str = "en-US-female-1"
    speed: float = 1.0

    @classmethod
    def get_default_config(cls, rasa_language: str) -> "NeuphonicTTSConfig":
        return cls(
            language_map={
                rasa_language: TTSLanguageMapEntry(
                    model="en-US-female-1",
                ),
            },
        )


# ======================================================================================
# Neuphonic TTS Engine
# ======================================================================================


class NeuphonicTTS(TTSEngine):
    """Neuphonic TTS Engine for streaming text-to-speech.

    This engine connects to Neuphonic's streaming TTS API via WebSocket
    for real-time audio generation. It follows the same patterns as
    the built-in Deepgram/Cartesia/Azure TTS engines.

    Docs: https://docs.neuphonic.com/
    """

    required_env_vars = ("NEUPHONIC_API_KEY",)
    streaming_input: bool = True

    @classmethod
    def name(cls) -> str:
        return "neuphonic"

    def __init__(
        self,
        rasa_language: str,
        format: AudioFormat,
        config: Optional["NeuphonicTTSConfig"] = None,
        additional_languages: Optional[list[str]] = None,
    ):
        super().__init__(rasa_language, format, config, additional_languages)
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws = None
        self._lock = asyncio.Lock()

    @classmethod
    def get_default_config(cls, rasa_language: str) -> "NeuphonicTTSConfig":
        return cls(
            language_map={
                rasa_language: TTSLanguageMapEntry(
                    model="en-US-female-1",
                ),
            },
        )

    async def connect(self, config: Optional["NeuphonicTTSConfig"] = None) -> None:
        """Establish WebSocket connection to Neuphonic TTS API."""
        if self.ws is not None and not self.ws.closed:
            return

        # Create aiohttp session if needed
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

        # Build WebSocket URL with query parameters
        ws_url = self.get_websocket_url(self.config)
        headers = self.get_request_headers(self.config)

        try:
            ws_timeout = aiohttp.ClientWSTimeout(ws_close=float(self.config.timeout))
            self.ws = await self.session.ws_connect(
                self.get_websocket_url(self.config),
                headers=self.get_request_headers(self.config),
                timeout=aiohttp.ClientWSTimeout(ws_close=float(self.config.timeout)),
            )
            logger.info("neuphonic_tts_connected")
        except Exception as e:
            logger.error("neuphonic_tts_connection_failed", error=str(e))
            raise TTSError(f"Failed to connect to Neuphonic: {e}")

    def get_request_headers(self, config) -> Dict[str, str]:
        """Build request headers with API key."""
        api_key = os.environ.get("NEUPHONIC_API_KEY") or config.api_key
        if not api_key:
            raise TTSError("NEUPHONIC_API_KEY not configured")
        return {
            "Authorization": f"Bearer {api_key}",
        }

    def get_websocket_url(self, config) -> str:
        """Build WebSocket URL with query parameters."""
        base_url = config.endpoint
        query_params = {
            "model": self.current_language_config.model,
            "voice_id": config.voice_id,
            "speed": str(config.speed),
            "sample_rate": self.audio_format.sample_rate,
        }
        from urllib.parse import urlencode
        return f"{config.endpoint}?{urlencode(query_params)}"

    @voice_tracing.traced_tts_connect
    async def connect(self, config: Optional = None) -> None:
        """Connect to Neuphonic WebSocket."""
        if self.ws is not None and not self.ws.closed:
            return

        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

        self.ws = await self.session.ws_connect(
            self.get_websocket_url(self.config),
            headers=self.get_request_headers(self.config),
            timeout=aiohttp.ClientWSTimeout(ws_close=float(self.config.timeout)),
        )
        logger.info("neuphonic_tts_connected")

    @voice_tracing.traced_tts_disconnect
    async def close_connection(self) -> None:
        if self.ws and not self.ws.closed:
            await self.ws.close()
            self.ws = None

    def get_websocket_url(self, config) -> str:
        from urllib.parse import urlencode
        base_url = config.endpoint
        query_params = {
            "model": self.current_language_config.model,
            "voice_id": config.voice_id,
            "speed": str(config.speed),
            "sample_rate": self.audio_format.sample_rate,
        }
        return f"{config.endpoint}?{urlencode(query_params)}"

    async def send_text_chunk(self, text: str) -> None:
        """Send text to Neuphonic for continuous streaming."""
        if not self.ws or self.ws.closed:
            raise TTSError("WebSocket connection not established")
        await self.ws.send_json({"type": "speak", "text": text})

    async def signal_text_done(self) -> None:
        """Signal end of text input to flush buffer."""
        if not self.ws or self.ws.closed:
            raise TTSError("WebSocket connection not established")
        await self.ws.send_json({"type": "flush"})

    async def signal_interrupt(self) -> None:
        """Clear the TTS buffer (interrupt current speech)."""
        if not self.ws or self.ws.closed:
            raise TTSError("WebSocket connection not established")
        await self.ws.send_json({"type": "clear"})

    async def stream_audio(self):
        """Stream audio output from Neuphonic."""
        if not self.ws or self.ws.closed:
            raise TTSError("WebSocket connection not established")

        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.BINARY:
                # Raw audio data
                yield self.engine_bytes_to_rasa_audio_bytes(msg.data)
            elif msg.type == aiohttp.WSMsgType.TEXT:
                data = msg.json()
                if data.get("type") == "audio_end":
                    break
                elif data.get("type") == "error":
                    raise TTSError(f"Neuphonic error: {data.get('message')}")
            elif msg.type == aiohttp.WSMsgType.CLOSED:
                break
            elif msg.type == aiohttp.WSMsgType.ERROR:
                raise TTSError(f"WebSocket error: {self.ws.exception()}")

    async def synthesize(
        self, text: str, config: Optional = None
    ) -> AsyncIterator:
        """Generate speech from text using Neuphonic streaming API."""
        if not self.ws or self.ws.closed:
            raise TTSError("WebSocket connection not established")

        # Send text and flush
        await self.send_text_chunk(text)
        await self.signal_text_done()

        async for audio_chunk in self.stream_audio():
            yield audio_chunk

    def engine_bytes_to_rasa_audio_bytes(self, chunk: bytes):
        from rasa.core.channels.voice_stream.audio_bytes import RasaAudioBytes
        return RasaAudioBytes(chunk, format=self.audio_format)

    @classmethod
    def get_default_config(cls, rasa_language: str):
        return cls(
            language_map={
                rasa_language: TTSLanguageMapEntry(
                    model="en-US-female-1",
                ),
            },
        )

    @classmethod
    def from_config_dict(
        cls,
        config: dict,
        format: "AudioFormat",
        rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ):
        return cls(
            rasa_language=rasa_language,
            format=format,
            config=NeuphonicTTSConfig.model_validate(config),
            additional_languages=additional_languages,
        )

    async def set_language(self, rasa_language: str) -> bool:
        if not await super().set_language(rasa_language):
            return False
        await self._reconnect_with_lock()
        return True

    async def _reconnect_with_lock(self):
        async with self._lock:
            await self.close_connection()
            await self.connect()


# ======================================================================================
# Local pyttsx3 TTS Stand-in (for development without Neuphonic API)
# ======================================================================================


class LocalTTSEngine(TTSEngine):
    """Local TTS engine using pyttsx3 as a Neuphonic stand-in.

    Use this for development/testing when Neuphonic API is not available.
    Follows the same Rasa TTS engine interface.
    """

    required_env_vars = ()
    streaming_input: bool = True

    @classmethod
    def name(cls) -> str:
        return "local_tts"

    def __init__(
        self,
        rasa_language: str,
        format: AudioFormat,
        config: Optional["NeuphonicTTSConfig"] = None,
        additional_languages: Optional[List[str]] = None,
    ):
        super().__init__(rasa_language, format, config, additional_languages)
        self.tts_engine = None
        self._init_tts()

    def _init_tts(self):
        import pyttsx3
        self.tts_engine = pyttsx3.init()
        voices = self.tts_engine.getProperty('voices')
        if len(voices) > 1:
            self.tts_engine.setProperty('voice', voices[1].id)  # Female voice
        self.tts_engine.setProperty('rate', 150)
        self.tts_engine.setProperty('volume', 0.9)

    @classmethod
    def name(cls) -> str:
        return "local_tts"

    @classmethod
    def get_default_config(cls, rasa_language: str):
        return NeuphonicTTSConfig(
            language_map={
                rasa_language: TTSLanguageMapEntry(
                    model="local",
                ),
            },
        )

    async def connect(self, config=None):
        pass  # Local engine doesn't need connection

    async def close_connection(self):
        pass

    async def send_text_chunk(self, text: str):
        pass

    async def signal_text_done(self):
        pass

    async def signal_interrupt(self):
        pass

    async def synthesize(self, text: str, config=None):
        import tempfile
        import wave

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            self.tts_engine.save_to_file(text, f.name)
            self.tts_engine.runAndWait()

            with wave.open(f.name, 'rb') as wf:
                frames = wf.readframes(wf.getnframes())
                yield RasaAudioBytes(frames, format=self.audio_format)
            os.unlink(f.name)

    def engine_bytes_to_rasa_audio_bytes(self, chunk: bytes):
        from rasa.core.channels.voice_stream.audio_bytes import RasaAudioBytes
        return RasaAudioBytes(chunk, format=self.audio_format)

    @classmethod
    def get_default_config(cls, rasa_language: str):
        return NeuphonicTTSConfig(
            language_map={
                rasa_language: TTSLanguageMapEntry(
                    model="local",
                ),
            },
        )

    @classmethod
    def from_config_dict(cls, config, format, rasa_language, additional_languages=None):
        return cls(
            rasa_language=rasa_language,
            format=format,
            config=NeuphonicTTSConfig.model_validate(config),
            additional_languages=additional_languages,
        )

    async def set_language(self, rasa_language: str) -> bool:
        return await super().set_language(rasa_language)