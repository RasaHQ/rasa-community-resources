"""Keep the public counterexamples runnable in a repository source."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CounterexampleChecks(unittest.TestCase):
    def test_public_counterexamples(self):
        scripts = (
            "tutorials/rasa-ai-team-casebook/appointment_binding_demo.py",
            "examples/mantle-voice-banking-collections-gemini/tests/explain_history_loss.py",
            "examples/mantle-text-insurance-file-claim-claude/tests/explain_filed_correction.py",
        )
        for script in scripts:
            with self.subTest(script=script):
                result = subprocess.run([sys.executable, "-B", str(ROOT / script)],
                                        cwd=ROOT, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
