"""Native validation of prepared source; not licensed training or chat."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prepare import prepare
from rasa.mantle.validation import validate_project


class PreparedProject(unittest.TestCase):
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
