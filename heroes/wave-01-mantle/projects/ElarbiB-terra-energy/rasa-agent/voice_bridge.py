#!/usr/bin/env python3
"""
WebSocket bridge service for Rasa voice integration with Whisper (ASR) and pyttsx3 (TTS stand-in for Neuphonic).

This service acts as a bridge between Rasa's voice channel and local Whisper/TTS services.
Rasa connects to this WebSocket server, sending/receiving audio frames.
The server uses Whisper for speech-to-text and pyttsx3 for text-to-speech.

To use with Neuphonic instead of pyttsx3:
1. Replace the synthesize_speech() function with a call to Neuphonic's API
2. Install the Neuphonic SDK or make HTTP requests to their service
3. Update the configuration accordingly
"""

import asyncio
import base64
import concurrent.futures
import json
import logging
import os
import tempfile
import wave
import numpy as np
from typing import Optional
from faster_whisper import WhisperModel
import pyttsx3
import websockets
from websockets.server import WebSocketServerProtocol

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Audio constants (matching the frontend's WebAudio capture)
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit audio
CHANNELS = 1

# NOTE: no initial_prompt is used. Earlier versions primed Whisper with a
# domain vocabulary string (e.g. "solar wind photovoltaic irradiance ..."),
# which Whisper reliably leaked INTO the transcript (prompt in:out copying) —
# the assistant then "answered" the injected words instead of the question.
# Keeping the prompt empty makes the transcription faithful to what is spoken.


class VoiceBridge:
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.whisper_model = None
        self.tts_engine = None
        self.clients = set()
        
    async def initialize(self):
        """Initialize the ASR (faster-whisper) and TTS engines."""
        # faster-whisper (CTranslate2): CPU int8 is both fast and accurate on
        # Apple Silicon (several times faster than openai-whisper fp16 on MPS,
        # which took ~50s per utterance on an 8GB M1). Override the size with
        # the WHISPER_MODEL env var (tiny/base/small/medium/large-v3).
        model_size = os.environ.get("WHISPER_MODEL", "medium")
        logger.info(f"Loading faster-whisper model (size='{model_size}', device='cpu', int8)...")
        self.whisper_model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            cpu_threads=max(4, os.cpu_count() or 4),
        )
        logger.info(f"faster-whisper model loaded (size='{model_size}').")
        
        logger.info("Initializing TTS engine...")
        self.tts_engine = pyttsx3.init()
        # Optional: configure TTS properties
        # self.tts_engine.setProperty('rate', 150)    # Speed of speech
        # self.tts_engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
        voices = self.tts_engine.getProperty('voices')
        # Use a female voice if available (index 1 often female on many systems)
        if len(voices) > 1:
            self.tts_engine.setProperty('voice', voices[1].id)
        logger.info("TTS engine initialized.")
        
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle a connected WebSocket client (Rasa voice channel)."""
        client_addr = websocket.remote_address
        logger.info(f"New client connected: {client_addr}")
        self.clients.add(websocket)
        
        try:
            async for message in websocket:
                await self.process_message(websocket, message)
        except websockets.exceptions.ConnectionClosedOK:
            logger.info(f"Client {client_addr} disconnected normally")
        except websockets.exceptions.ConnectionClosedError as e:
            logger.error(f"Client {client_addr} disconnected with error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error with client {client_addr}: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info(f"Client {client_addr} removed from active clients")
    
    async def process_message(self, websocket: WebSocketServerProtocol, message):
        """Process incoming message from a client (voice channel or web app)."""
        try:
            # Accept both text frames (str) and binary frames (bytes)
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            # Only JSON frames are handled; raw binary frames are ignored quietly
            data = json.loads(message)
            msg_type = data.get("type")

            logger.debug(f"Received message type: {msg_type}")

            if msg_type == "audio":
                # Handle incoming audio from client (user speaking)
                await self.handle_audio_input(websocket, data)
            elif msg_type == "text":
                # Handle incoming text (bot response to speak)
                await self.handle_text_input(websocket, data)
            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except json.JSONDecodeError:
            logger.debug("Ignoring non-JSON (raw binary) frame")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def handle_audio_input(self, websocket: WebSocketServerProtocol, data: dict):
        """Process audio input from client (user speech) -> Whisper -> text to Rasa."""
        try:
            # Extract audio data (base64-encoded 16-bit PCM)
            audio_b64 = data.get("audio")
            if not audio_b64:
                logger.warning("Received audio message with no audio data")
                return

            try:
                audio_bytes = base64.b64decode(audio_b64)
            except Exception as e:
                logger.error(f"Failed to decode audio base64: {e}")
                return

            # Convert audio data to numpy array
            # 16-bit PCM in little-endian format (int16 == int16 little-endian)
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            logger.info(f"Received audio chunk: {len(audio_np)} samples")

            # Language of the request (fr/en/de/es). Whisper auto-detects when
            # this is "auto" or missing, so speech is decoded in the language
            # actually spoken — not the one forced by the UI. The multilingual
            # domain prompt keeps domain vocabulary while staying language-neutral.
            language = str(data.get("language", "auto") or "auto")
            # Sample rate of the incoming PCM (defaults to the bridge's rate)
            sample_rate = int(data.get("sampleRate", SAMPLE_RATE))

            # Save audio to temporary file for Whisper processing
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                # Write WAV file
                with wave.open(temp_file.name, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(SAMPLE_WIDTH)
                    wf.setframerate(sample_rate)
                    wf.writeframes((audio_np * 32767).astype(np.int16).tobytes())

                # Transcribe with Whisper. No initial_prompt: it corrupts the
                # transcript with prompt-leaked domain words (see top of file).
                # Run in a thread pool: whisper.transcribe() blocks the event
                # loop (medium model can take 10s+), which would break the
                # WebSocket keepalive pings and kill the connection before the
                # reply is sent.
                if language == "auto":
                    # Let Whisper detect the spoken language itself.
                    whisper_language = None
                else:
                    whisper_language = language

                def _transcribe():
                    segments, info = self.whisper_model.transcribe(
                        temp_file.name,
                        language=whisper_language,
                        task="transcribe",
                        beam_size=5,
                        condition_on_previous_text=False,
                        no_speech_threshold=0.6,
                        log_prob_threshold=-1.0,
                        compression_ratio_threshold=2.4,
                    )
                    text = "".join(seg.text.strip() for seg in segments).strip()
                    return text, info.language

                loop = asyncio.get_running_loop()
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    transcription, detected_lang = await loop.run_in_executor(pool, _transcribe)
                
                logger.info(f"Whisper transcription ({detected_lang}): '{transcription}'")
                
                # Send transcription back to Rasa as text
                response = {
                    "type": "text",
                    "text": transcription
                }
                await websocket.send(json.dumps(response).encode('utf-8'))
                logger.debug(f"Sent text to Rasa: '{transcription}'")
                
                # Clean up temp file
                os.unlink(temp_file.name)
                
        except Exception as e:
            logger.error(f"Error handling audio input: {e}")
            # Send error message to Rasa
            error_response = {
                "type": "error",
                "message": f"ASR error: {str(e)}"
            }
            try:
                await websocket.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass  # Connection might be closed
    
    async def handle_text_input(self, websocket: WebSocketServerProtocol, data: dict):
        """Process text input from Rasa (bot response) -> TTS -> audio to client."""
        try:
            text = data.get("text", "").strip()
            if not text:
                logger.warning("Received empty text for TTS")
                return
            
            logger.info(f"Converting text to speech: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            
            # Convert text to speech using pyttsx3 (stand-in for Neuphonic)
            # For actual Neuphonic integration, replace this section with:
            # - Call to Neuphonic API
            # - Or use their SDK
            # - Receive audio data back
            
            # Save speech to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                self.tts_engine.save_to_file(text, temp_file.name)
                self.tts_engine.runAndWait()  # This blocks until speech is synthesized
                
                # Read the generated audio file
                with wave.open(temp_file.name, 'rb') as wf:
                    frames = wf.getnframes()
                    audio_data = wf.readframes(frames)
                    
                    # Send audio back to client
                    response = {
                        "type": "audio",
                        "audio": audio_data.hex()  # Send as hex string for JSON compatibility
                    }
                    await websocket.send(json.dumps(response).encode('utf-8'))
                    logger.debug(f"Sent audio to client: {len(audio_data)} bytes")
                
                # Clean up temp file
                os.unlink(temp_file.name)
                
        except Exception as e:
            logger.error(f"Error handling text input: {e}")
            # Send error message to Rasa
            error_response = {
                "type": "error",
                "message": f"TTS error: {str(e)}"
            }
            try:
                await websocket.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass  # Connection might be closed
    
    async def start(self):
        """Start the WebSocket server."""
        await self.initialize()
        
        logger.info(f"Starting WebSocket bridge on ws://{self.host}:{self.port}")
        async with websockets.serve(self.handle_client, self.host, self.port):
            logger.info(f"Voice bridge running on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever

async def main():
    """Main entry point."""
    bridge = VoiceBridge(host="localhost", port=8765)
    await bridge.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Voice bridge stopped by user")
    except Exception as e:
        logger.error(f"Voice bridge failed to start: {e}")
        raise