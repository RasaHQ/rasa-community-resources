"""Shared Nova /v1/listen and Aura /v1/speak transports.

Uses the existing Cedar tutorial's vendor protocol. Flux /v2/listen is a
separate protocol and is not selected by this adapter. Retries belong to the
router policy; this transport never silently retries a request.
"""
from __future__ import annotations
import asyncio
import json
import os
from typing import Any, Optional
from urllib.parse import urlencode
from websockets.asyncio.client import connect

from voicerouter.engine import (SocketASR, ASREngineConfig, ASRLanguageMapEntry,
                               TTSEngine, TTSEngineConfig, TTSLanguageMapEntry,
                               AudioEncoding, RasaAudioBytes, NewTranscript, UserIsSpeaking, TTSError)


class DeepgramASRConfig(ASREngineConfig):
    endpoint: str = 'wss://api.deepgram.com/v1/listen'
    endpointing: int = 400
    utterance_end_ms: int = 1000
    smart_format: bool = True


class DeepgramASR(SocketASR[DeepgramASRConfig]):
    required_env_vars = ('DEEPGRAM_API_KEY',)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._held = []

    @classmethod
    def name(cls): return 'deepgram-shared'

    @staticmethod
    def get_default_config(rasa_language):
        return DeepgramASRConfig(language_map={rasa_language:ASRLanguageMapEntry(language=rasa_language,model='nova-3')})

    @classmethod
    def from_config_dict(cls,config,format,rasa_language,additional_languages=None):
        return cls(rasa_language,format,DeepgramASRConfig.model_validate(config or {}),additional_languages)

    def query(self):
        if self.audio_format.encoding!=AudioEncoding.LINEAR or self.audio_format.bit_depth!=16 or self.audio_format.channels!=1:
            raise ValueError('Shared Deepgram adapter requires mono PCM16')
        return {'encoding':'linear16','sample_rate':self.audio_format.sample_rate,
                'endpointing':self.config.endpointing,'vad_events':'true',
                'language':self.current_language_config.engine_language_key,
                'interim_results':'true','model':self.current_language_config.model,
                'smart_format':str(self.config.smart_format).lower(),'utterance_end_ms':self.config.utterance_end_ms}

    async def open_websocket_connection(self):
        self._held=[]
        return await connect(self.config.endpoint+'?'+urlencode(self.query()),
                             additional_headers={'Authorization':'Token '+os.environ['DEEPGRAM_API_KEY']})

    def rasa_audio_bytes_to_engine_bytes(self,chunk): return chunk.data

    async def signal_audio_done(self):
        if self.asr_socket is not None:await self.asr_socket.send(json.dumps({'type':'CloseStream'}))

    async def send_keep_alive(self):
        if self.asr_socket is not None:await self.asr_socket.send(json.dumps({'type':'KeepAlive'}))

    def engine_event_to_asr_event(self,raw):
        data=json.loads(raw)
        kind=data.get('type')
        if kind=='Error':raise RuntimeError('Deepgram ASR returned an error event')
        if kind=='Results':
            alternatives=(data.get('channel') or {}).get('alternatives') or [{}]
            text=(alternatives[0].get('transcript') or '').strip()
            if data.get('is_final'):
                if text:self._held.append(text)
                if data.get('speech_final') and self._held:
                    full,self._held=' '.join(self._held),[]
                    return NewTranscript(full)
            elif text:return UserIsSpeaking(text)
        elif kind=='UtteranceEnd' and self._held:
            full,self._held=' '.join(self._held),[]
            return NewTranscript(full)
        return None


class DeepgramTTSConfig(TTSEngineConfig):
    endpoint: str = 'wss://api.deepgram.com/v1/speak'


class DeepgramTTS(TTSEngine[DeepgramTTSConfig]):
    required_env_vars = ('DEEPGRAM_API_KEY',)
    streaming_input = False

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._socket=None
        self._lock=asyncio.Lock()

    @classmethod
    def name(cls): return 'deepgram-shared'

    @staticmethod
    def get_default_config(rasa_language):
        return DeepgramTTSConfig(timeout=30,language_map={rasa_language:TTSLanguageMapEntry(model='aura-2-thalia-en')})

    @classmethod
    def from_config_dict(cls,config,format,rasa_language,additional_languages=None):
        return cls(rasa_language,format,DeepgramTTSConfig.model_validate(config or {}),additional_languages)

    def query(self):
        if self.audio_format.encoding!=AudioEncoding.LINEAR or self.audio_format.bit_depth!=16 or self.audio_format.channels!=1:
            raise ValueError('Shared Deepgram adapter requires mono PCM16')
        return {'model':self.current_language_config.model,'encoding':'linear16','sample_rate':self.audio_format.sample_rate}

    async def connect(self,config:Optional[Any]=None):
        if self._socket is None:
            self._socket=await connect(self.config.endpoint+'?'+urlencode(self.query()),
                                      additional_headers={'Authorization':'Token '+os.environ['DEEPGRAM_API_KEY']})

    async def close_connection(self):
        socket,self._socket=self._socket,None
        if socket is not None:await asyncio.wait_for(socket.close(),timeout=5)

    async def synthesize(self,text,config:Optional[Any]=None):
        async with self._lock:
            await self.connect()
            try:
                await self._socket.send(json.dumps({'type':'Speak','text':text}))
                await self._socket.send(json.dumps({'type':'Flush'}))
                while True:
                    raw=await asyncio.wait_for(self._socket.recv(),timeout=float(self.config.timeout))
                    if isinstance(raw,bytes):
                        yield RasaAudioBytes(raw,format=self.audio_format)
                        continue
                    kind=json.loads(raw).get('type')
                    if kind=='Flushed':return
                    if kind=='Error':raise TTSError('Deepgram TTS returned an error event')
            except BaseException:
                # Cancellation leaves buffered audio on a pooled socket. Drop
                # it so the next utterance cannot consume the old response.
                await self.close_connection()
                raise
