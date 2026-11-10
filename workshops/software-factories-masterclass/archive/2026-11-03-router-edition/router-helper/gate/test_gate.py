"""Tests for the gate: a good change is accepted, each bad change is rejected by name, the gate never runs the
change, and an unreadable file is not judged."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
GATE = HERE / "gate.py"
CAND = HERE / "candidates"


def run(candidate, cwd=None):
    done = subprocess.run([sys.executable, "-I", str(GATE), str(candidate)], capture_output=True, text=True, timeout=60, cwd=cwd)
    return done.returncode, done.stdout


class Gate(unittest.TestCase):
    def test_a_good_change_is_accepted(self):
        code, out = run(CAND / "good.py")
        self.assertEqual(code, 0, out)

    def test_a_change_that_names_a_reset_is_rejected_by_name(self):
        code, out = run(CAND / "bad_sends_reset.py")
        self.assertEqual(code, 1, out)
        self.assertIn("test_no_restart_or_reset_command", out)

    def test_a_change_that_imports_the_network_is_rejected_by_name(self):
        code, out = run(CAND / "bad_opens_network.py")
        self.assertEqual(code, 1, out)
        self.assertIn("test_only_the_one_function_and_nothing_else", out)

    def test_a_change_that_writes_a_file_is_rejected_and_never_run(self):
        folder = Path(tempfile.mkdtemp(prefix="gate-cwd-"))
        self.addCleanup(lambda: [p.unlink() for p in folder.iterdir()] and folder.rmdir())
        code, out = run(CAND / "bad_writes_a_file.py", cwd=folder)
        self.assertEqual(code, 1, out)
        self.assertEqual(list(folder.iterdir()), [], "the change was run")

    def test_a_change_with_a_wrong_answer_is_rejected_by_name(self):
        folder = Path(tempfile.mkdtemp(prefix="gate-wrong-"))
        self.addCleanup(lambda: [p.unlink() for p in folder.iterdir()] and folder.rmdir())
        path = folder / "c.py"
        path.write_text('def check_line_status():\n    return {"operation": "check_line_status", "status": "down", "changes_anything": False}\n')
        code, out = run(path)
        self.assertEqual(code, 1, out)
        self.assertIn("test_returns_the_expected_read_only_answer", out)

    def test_an_expression_that_is_not_a_literal_is_rejected(self):
        folder = Path(tempfile.mkdtemp(prefix="gate-expr-"))
        self.addCleanup(lambda: [p.unlink() for p in folder.iterdir()] and folder.rmdir())
        path = folder / "c.py"
        path.write_text('def check_line_status():\n    return dict(operation="check_line_status", status="ok", changes_anything=False)\n')
        code, out = run(path)
        self.assertEqual(code, 1, out)
        self.assertIn("test_returns_a_plain_literal", out)

    def test_a_missing_file_is_not_judged(self):
        self.assertEqual(run(CAND / "nope.py")[0], 2)


if __name__ == "__main__":
    unittest.main()
