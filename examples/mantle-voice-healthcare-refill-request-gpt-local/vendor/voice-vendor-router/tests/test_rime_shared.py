"""Offline Rime request and shared-factory contracts; no vendor calls."""
import os
import unittest
from unittest.mock import patch

from voicerouter.engine import L16_24KHZ, tts_engine_from_config
from voicerouter.providers.rime import RimeTTS


class RimeSharedTests(unittest.TestCase):
    def test_coda_pcm_request_uses_exact_provider_language(self):
        with patch.dict(os.environ, {"RIME_API_KEY": "offline-test"}):
            engine = tts_engine_from_config({"name": "rime-shared", "model_id": "coda",
                "sampling_rate": 24000, "language_map": {"en": {"voice": "astra", "language": "en"}}},
                L16_24KHZ, "en")
            url, headers, body = engine.request("Reference 0615.")
            self.assertIsInstance(engine, RimeTTS)
            self.assertEqual(url, "https://users.rime.ai/v1/rime-tts")
            self.assertEqual(headers, {"Authorization": "Bearer offline-test", "Accept": "audio/L16"})
            self.assertEqual(body, {"text": "Reference 0615.", "modelId": "coda", "speaker": "astra",
                                   "lang": "en", "samplingRate": 24000})
            self.assertEqual(engine.source_sample_rate, 24000)
            self.assertFalse(engine.returns_wav)

    def test_mist_configuration_is_not_normalised_to_coda(self):
        with patch.dict(os.environ, {"RIME_API_KEY": "offline-test"}):
            engine = tts_engine_from_config({"name": "voicerouter.providers.rime.RimeTTS",
                "model_id": "mistv2", "sampling_rate": 22050,
                "language_map": {"en": {"voice": "cove", "language": "eng"}}}, L16_24KHZ, "en")
            body = engine.request("hello")[2]
            self.assertEqual((body["modelId"], body["lang"], engine.source_sample_rate), ("mistv2", "eng", 22050))

    def test_invalid_configuration_rejected_before_connection(self):
        with patch.dict(os.environ, {"RIME_API_KEY": "offline-test"}):
            for rate in [0, 123]:
                with self.assertRaises(ValueError):
                    tts_engine_from_config({"name": "rime-shared", "sampling_rate": rate}, L16_24KHZ, "en")
            with self.assertRaises(ValueError):
                tts_engine_from_config({"name": "rime-shared", "language_map": {"en": {"voice": "astra"}}},
                                      L16_24KHZ, "en")
