"""Offline voice configuration and installed engine validation, no voice call."""
from importlib.util import find_spec
from pathlib import Path
import json
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from voice_config import voice_channels, VOICE_OFF_TEXT, VOICE_FAILED_TEXT


class VoiceConfig(unittest.TestCase):
    def test_missing_voice_is_optional_and_contains_no_other_provider_key(self):
        self.assertEqual(voice_channels({}), {})
        self.assertEqual(voice_channels({'DEEPGRAM_API_KEY': '  '}), {})
        self.assertIn('DEEPGRAM_API_KEY', VOICE_OFF_TEXT)
        self.assertIn('text', VOICE_OFF_TEXT)
        self.assertIn('text', VOICE_FAILED_TEXT)

    def test_environment_key_never_enters_runtime_config(self):
        canary = 'c8f31a7b9420ed65d2a9e13b7046f58c'
        channels = voice_channels({'DEEPGRAM_API_KEY': canary})
        text = json.dumps(channels)
        for offset in range(len(canary) - 7):
            self.assertNotIn(canary[offset:offset + 8], text)
        self.assertNotIn('api_key', text)
        self.assertIn('flux-general-en', text)
        self.assertIn('aura-2-andromeda-en', text)
        self.assertEqual(channels['inspector']['asr']['name'], 'deepgram_flux')
        self.assertEqual(channels['inspector']['tts']['name'], 'deepgram')

    @unittest.skipUnless(find_spec('rasa') is not None, 'Mantle project interpreter required')
    def test_actual_engine_accepts_flux_v2_configuration_without_opening_a_connection(self):
        from rasa.core.channels.voice_stream.asr.deepgram.config import DeepgramFluxASRConfig
        asr = voice_channels({'DEEPGRAM_API_KEY': 'synthetic-only'})['inspector']['asr']
        parsed = DeepgramFluxASRConfig.model_validate({k: v for k, v in asr.items() if k != 'name'})
        self.assertEqual(parsed.version, 'v2')
        self.assertEqual(parsed.language_map['en'].model, 'flux-general-en')
