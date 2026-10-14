"""Native validation of prepared source; not licensed training or chat."""
import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prepare import prepare
from rasa.mantle.validation import validate_project


class PreparedProject(unittest.TestCase):
    def test_catalog_project_is_the_default_generated_gated_configuration(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp, patch.dict(
                os.environ, {"OPENAI_API_KEY": "placeholder-not-a-real-key"}):
            target = Path(temp) / "gated"
            receipt = prepare("gated", target, 8937, scripted_model_port=8938)
            for name in receipt["files"]:
                self.assertEqual((root / name).read_bytes(), (target / name).read_bytes(), name)
            validate_project(root)

    def test_scripted_pair_validates_with_identical_local_endpoints(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(
                os.environ, {"OPENAI_API_KEY": "placeholder-not-a-real-key",
                             "RASA_TELEMETRY_ENABLED": "false"}):
            configurations = []
            for variant in ("gated", "ungated"):
                path = Path(temp) / variant
                receipt = prepare(variant, path, 8937, scripted_model_port=8938)
                validate_project(path)
                config = (path / "integrations.yml").read_text()
                self.assertIn("http://127.0.0.1:8938/v1", config)
                self.assertIn("http://127.0.0.1:8937/mcp", config)
                self.assertNotIn("reasoning_effort", config)
                self.assertNotIn("MODEL_PORT", config)
                self.assertEqual(receipt["model_mode"], "scripted-loopback")
                self.assertEqual(json.loads((path / "variant.json").read_text()), receipt)
                self.assertFalse((path / ".env").exists())
                self.assertFalse((path / ".venv").exists())
                configurations.append(config)
            self.assertEqual(configurations[0], configurations[1])

    def test_bad_or_conflicting_fixture_port_leaves_no_partial_project(self):
        with tempfile.TemporaryDirectory() as temp:
            for port in (1023, 65536, 8937):
                path = Path(temp) / str(port)
                with self.assertRaises(ValueError):
                    prepare("gated", path, 8937, scripted_model_port=port)
                self.assertFalse(path.exists())

    def test_both_source_only_variants_validate_without_overwriting_work(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(
                os.environ, {"OPENAI_API_KEY": "placeholder-not-a-real-key",
                             "RASA_TELEMETRY_ENABLED": "false"}):
            sources = []
            for variant in ("gated", "ungated"):
                path = Path(temp) / variant
                prepare(variant, path, 8937)
                self.assertFalse((path / ".env").exists())
                self.assertFalse((path / ".venv").exists())
                validate_project(path)
                sources.append((path / "skills/review_case/skill.md").read_text())
                with self.assertRaises(FileExistsError):
                    prepare(variant, path, 8937)
            self.assertEqual(sources[0].replace("enabled: true", "enabled: false"), sources[1])
