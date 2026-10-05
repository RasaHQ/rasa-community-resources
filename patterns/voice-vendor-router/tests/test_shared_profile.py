"""Shared speech contracts, exercised without a model or paid vendor request."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
TUTORIAL = ROOT / 'tutorials/voice-agent-three-frameworks'
sys.path.insert(0, str(TUTORIAL / 'shared/speech'))
from cedar_speech import config, protocol
from cedar_speech.router import create_asr, create_tts, RouterASR, RouterTTS
from voicerouter.engine import NewTranscript, UserIsSpeaking, RasaAudioBytes
from voicerouter.profile import VoiceProfile

PROFILE = TUTORIAL / 'shared/speech/profiles/speechmatics-fixed.json'
FRAMEWORKS = ['rasa','langgraph','strands','langchain','agno','crewai','pipecat','livekit']


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'SPEECHMATICS_API_KEY': 'offline-test',
                                         'CEDAR_VOICE_ROUTER_CONFIG': str(PROFILE)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_same_speechmatics_requests_as_original_clients(self):
        p = VoiceProfile.load(PROFILE)
        asr, tts = p.engines()
        self.assertEqual(asr._active.engine._start_recognition_message(), protocol.start_recognition())
        self.assertEqual(tts._active.engine.request('hello'), protocol.tts_request('hello', 'offline-test'))
        self.assertEqual(asr.active_provider, 'voicerouter.providers.speechmatics.SpeechmaticsASR')
        self.assertEqual(p.sample_rate, config.SAMPLE_RATE)

    def test_socket_error_is_visible_and_failed_transport_is_closed(self):
        async def check():
            router = VoiceProfile.load(PROFILE).build_asr()
            class Socket:
                closed = False
                def __aiter__(self): return self.messages()
                async def messages(self):
                    yield json.dumps({'message':'Error','reason':'offline-failure'})
                async def close(self): self.closed = True
            socket = Socket()
            router._active.engine.asr_socket = socket
            router._connected.add(0)
            with self.assertRaises(RuntimeError):
                _ = [e async for e in router.stream_asr_events()]
            self.assertTrue(socket.closed)
        asyncio.run(check())

    def test_truncated_tts_is_not_replayed_or_reported_as_success(self):
        from voicerouter.base import BuiltProvider, ProviderSpec, RouterPolicy
        from voicerouter import RoutedTTS
        from voicerouter.engine import TTSError
        async def check():
            class Broken:
                closed = False
                async def connect(self): pass
                async def close_connection(self): self.closed = True
                async def synthesize(self, text):
                    yield RasaAudioBytes(b'\0\0', format=VoiceProfile.load(PROFILE).audio_format)
                    raise RuntimeError('offline-failure')
            provider = Broken()
            router = RoutedTTS([BuiltProvider(ProviderSpec('broken','broken',{}),provider)],
                               RouterPolicy(health_scope='call',same_provider_retries=0,raise_on_failure=True))
            emitted = []
            with self.assertRaises(TTSError):
                async for chunk in router.synthesize('hello'): emitted.append(chunk.data)
            self.assertEqual(emitted,[b'\0\0'])
            self.assertTrue(provider.closed)
        asyncio.run(check())

    def test_identity_changes_with_vendor_settings_not_json_order(self):
        p = VoiceProfile.load(PROFILE)
        d = p.model_dump()
        self.assertEqual(p.fingerprint, VoiceProfile.model_validate(dict(reversed(list(d.items())))).fingerprint)
        d['tts']['providers'][0]['language_map']['en']['voice'] = 'theo'
        self.assertNotEqual(p.fingerprint, VoiceProfile.model_validate(d).fingerprint)

    def test_credentials_and_schema_rejected_before_requests(self):
        d = VoiceProfile.load(PROFILE).model_dump()
        d['tts']['providers'][0]['api_key'] = 'must-not-be-saved'
        with self.assertRaises(ValueError): VoiceProfile.model_validate(d)
        d.pop('tts')
        with self.assertRaises(ValueError): VoiceProfile.model_validate(d)

    def test_all_seven_frameworks_select_shared_factories(self):
        for fw in FRAMEWORKS[1:]:
            with self.subTest(framework=fw):
                sources = '\n'.join(p.read_text() for p in (TUTORIAL/fw).glob('*.py'))
                self.assertIn('create_asr(', sources)
                self.assertIn('create_tts(', sources)
                self.assertNotIn('SpeechmaticsASR(', sources)
                self.assertNotIn('SpeechmaticsTTS(', sources)
                self.assertIsInstance(create_asr(), RouterASR)
                self.assertIsInstance(create_tts(), RouterTTS)

    def test_default_is_original_client(self):
        from cedar_speech import SpeechmaticsASR, SpeechmaticsTTS
        with patch.dict(os.environ):
            os.environ.pop('CEDAR_VOICE_ROUTER_CONFIG', None)
            self.assertIsInstance(create_asr(), SpeechmaticsASR)
            self.assertIsInstance(create_tts(), SpeechmaticsTTS)

    def test_existing_vendor_launchers_still_select_their_clients(self):
        import cedar_speech
        with patch.dict(os.environ):
            os.environ.pop("CEDAR_VOICE_ROUTER_CONFIG",None)
            with patch.object(cedar_speech,"SpeechmaticsASR") as asr, patch.object(cedar_speech,"SpeechmaticsTTS") as tts:
                self.assertIs(create_asr(),asr.return_value)
                self.assertIs(create_tts(),tts.return_value)

    def test_shared_deepgram_matches_existing_tutorial_protocol(self):
        sys.path.insert(0,str(TUTORIAL/'shared/speech-deepgram'))
        from cedar_speech_deepgram import config as dg
        from cedar_speech_deepgram.asr import ResultsReader
        with patch.dict(os.environ,{'DEEPGRAM_API_KEY':'offline-test'}):
            profile=VoiceProfile.load(PROFILE.with_name('deepgram-nova-aura-fixed.json'))
            asr,tts=profile.engines()
            self.assertEqual(asr._active.engine.query(),dg.asr_query())
            self.assertEqual(tts._active.engine.query(),dg.tts_query())
            frames=[{'type':'Results','is_final':False,'channel':{'alternatives':[{'transcript':'he'}]}},
                    {'type':'Results','is_final':True,'channel':{'alternatives':[{'transcript':'hello'}]}},
                    {'type':'Results','is_final':True,'speech_final':True,'channel':{'alternatives':[{'transcript':'world'}]}}]
            reader=ResultsReader()
            for frame in frames:
                raw=json.dumps(frame)
                old=reader.read(raw)
                new=asr._active.engine.engine_event_to_asr_event(raw)
                if old is None:self.assertIsNone(new)
                else:self.assertEqual((new.text,isinstance(new,NewTranscript)),(old[1],old[0]=='final'))
            with self.assertRaises(RuntimeError):asr._active.engine.engine_event_to_asr_event(json.dumps({'type':'Error'}))

    def test_pcm_rate_mismatch_fails(self):
        with self.assertRaises(ValueError): create_asr(16000)

    def test_bridge_audio_events_lifecycle_and_timings(self):
        async def check():
            asr, tts = create_asr(), create_tts()
            sent = []
            class FakeASR:
                async def connect(self): sent.append('open')
                async def send_audio_chunks(self, chunk): sent.append(chunk.data)
                async def stream_asr_events(self):
                    yield UserIsSpeaking('he')
                    yield NewTranscript('hello')
                async def signal_audio_done(self): sent.append('done')
                async def close_connection(self): sent.append('close')
            class FakeTTS:
                active_provider = 'fake'
                async def synthesize(self, text):
                    yield RasaAudioBytes(b'\0\0' * 480, format=tts.profile.audio_format)
                async def close_connection(self): sent.append('tts-close')
            asr.engine, tts.engine = FakeASR(), FakeTTS()
            async with asr:
                await asr.send_audio(b'\0\0' * 480)
                events = [event async for event in asr.events()]
                with self.assertRaises(ValueError): await asr.send_audio(b'\0')
            self.assertEqual([(e.text,e.final) for e in events], [('he',False),('hello',True)])
            self.assertAlmostEqual(asr.audio_seconds,.02)
            self.assertEqual(sent[0], 'open')
            self.assertEqual(sent[-2:], ['done','close'])
            self.assertEqual(len(await tts.synthesize('hello')), 960)
            self.assertEqual(tts.characters,5)
            self.assertIsNone(tts.last_timings['headers_s'])
            self.assertEqual(tts.last_timings['provider'],'fake')
            await tts.close()
        asyncio.run(check())

    @unittest.skipUnless(importlib.util.find_spec('rasa'), 'Native Rasa contract needs the pinned Rasa environment')
    def test_rasa_plugins_select_same_router(self):
        spec = importlib.util.spec_from_file_location('cedar_rasa_speech', TUTORIAL/'rasa/engines/speechmatics.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        profile = VoiceProfile.load(PROFILE)
        from voicerouter import RoutedASR, RoutedTTS
        self.assertIsInstance(module.SpeechmaticsASR.from_config_dict({},profile.audio_format,'en'),RoutedASR)
        self.assertIsInstance(module.SpeechmaticsTTS.from_config_dict({},profile.audio_format,'en'),RoutedTTS)

if __name__ == '__main__': unittest.main()
