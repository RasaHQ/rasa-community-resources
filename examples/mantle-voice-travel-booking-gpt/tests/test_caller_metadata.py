"""Metadata controls only: no renderer, credential loader or provider call."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("caller_metadata", ROOT / "case-build/caller_metadata.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CallerMetadata(unittest.TestCase):
    def test_fallback_rows_do_not_inherit_default_model_or_tariff(self):
        rows = {"a.wav": {"vendor": "rime", "model": "mistv2"}}
        summary = MODULE.declared_summary({"vendor": "gemini", "model": "configured-default"}, rows)
        self.assertEqual(summary["model"], "mistv2")
        self.assertEqual(summary["vendor"], "rime")
        self.assertEqual(summary["renderer_configuration"]["default_model"], "configured-default")
        self.assertFalse(summary["attribution"]["original_provider_use_verified"])

    def test_mixed_or_missing_declarations_do_not_get_a_single_model(self):
        rows = {"a": {"vendor": "rime", "model": "mistv2"},
                "b": {"vendor": "gemini", "model": "configured-default"}}
        summary = MODULE.declared_summary({}, rows)
        self.assertIsNone(summary["model"])
        self.assertIsNone(summary["vendor"])
        self.assertEqual(sum(row["files"] for row in summary["declared_file_models"]), 2)
        self.assertIsNone(MODULE.declared_summary({}, {})["model"])

    def test_current_manifest_matches_declarations_not_request_attestation(self):
        manifest = json.loads((ROOT / "case-build/caller-audio/manifest.json").read_text())
        caller = json.loads((ROOT / "case-build/conversations.json").read_text())["voice"]["caller"]
        expected = MODULE.declared_summary(caller, manifest["files"])
        for field, value in expected.items():
            self.assertEqual(manifest[field], value)
        self.assertNotIn("price", manifest)


if __name__ == "__main__":
    unittest.main()
