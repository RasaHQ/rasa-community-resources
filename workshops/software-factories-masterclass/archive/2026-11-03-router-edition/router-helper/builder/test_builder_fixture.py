"""The fixture writes the public sample and passes the gate without an API client."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
openai = types.ModuleType("openai")
openai.OpenAI = object
sys.modules.setdefault("openai", openai)
import builder


class Fixture(unittest.TestCase):
    def test_fixture_never_constructs_a_provider_client(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(builder, "SCRATCH", Path(directory)), \
                patch.object(builder, "OpenAI", side_effect=AssertionError("provider must not be used")) as client:
            result = builder.build_fixture()
            self.assertEqual(result["mode"], "fixture")
            self.assertNotIn("session_id", result)
            self.assertIn("No Agents session", result["builder_said"])
            self.assertTrue(Path(result["file"]).is_absolute())
            self.assertEqual(hashlib.sha256(Path(result["file"]).read_bytes()).hexdigest(), result["sha256"])
            client.assert_not_called()

    def test_each_fixture_has_a_new_file_without_overwriting_previous_work(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(builder, "SCRATCH", Path(directory)):
            first, second = builder.build_fixture(), builder.build_fixture()
            self.assertNotEqual(first["build_id"], second["build_id"])
            self.assertNotEqual(first["file"], second["file"])
            self.assertEqual(Path(first["file"]).read_bytes(), Path(second["file"]).read_bytes())

    def test_printed_path_works_with_the_unchanged_gate_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(builder, "SCRATCH", Path(directory) / "producer"):
            result = builder.build_fixture()
            gate = Path(__file__).resolve().parent.parent / "gate" / "gate.py"
            done = subprocess.run([sys.executable, str(gate), result["file"]], cwd=directory, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn("ACCEPT", done.stdout)


if __name__ == "__main__":
    unittest.main()
