"""Keep the real Rasa tool-dispatch controls in catalog compatibility checks."""
import importlib.util
from pathlib import Path
import subprocess
import unittest


@unittest.skipUnless(importlib.util.find_spec("rasa"),
    "Native Rasa is absent from the consent environment; run make test-native.")
class NativeGate(unittest.TestCase):
    def test_native_rasa_and_installed_provider_contracts(self):
        project = Path(__file__).resolve().parent.parent
        result = subprocess.run(["make", "test-native"], cwd=project,
            text=True, capture_output=True, timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
