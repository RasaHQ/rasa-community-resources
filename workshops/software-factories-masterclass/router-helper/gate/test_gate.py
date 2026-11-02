"""Tests for the gate: a good change is accepted, each bad change is rejected by name, and a missing
or edited isolation helper means no judgment at all."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
GATE = HERE / "gate.py"
CAND = HERE / "candidates"


def run(gate, candidate):
    done = subprocess.run([sys.executable, "-I", str(gate), str(candidate)], capture_output=True, text=True, timeout=120)
    return done.returncode, done.stdout


class Gate(unittest.TestCase):
    def test_a_good_change_is_accepted(self):
        code, out = run(GATE, CAND / "good.py")
        self.assertEqual(code, 0, out)

    def test_a_change_that_names_a_reset_is_rejected_by_name(self):
        code, out = run(GATE, CAND / "bad_sends_reset.py")
        self.assertEqual(code, 1, out)
        self.assertIn("test_no_restart_or_reset_command", out)

    def test_a_change_that_opens_the_network_is_rejected_by_name(self):
        code, out = run(GATE, CAND / "bad_opens_network.py")
        self.assertEqual(code, 1, out)
        self.assertIn("test_no_network_process_or_file_access", out)

    def test_a_missing_file_is_not_judged(self):
        self.assertEqual(run(GATE, CAND / "nope.py")[0], 2)

    def test_an_edited_isolation_helper_means_no_judgment(self):
        root = Path(tempfile.mkdtemp(prefix="gate-pin-"))
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(HERE.parent, root / "router-helper", ignore=shutil.ignore_patterns("__pycache__"))
        iso = root / "book/ready/ch06"
        iso.mkdir(parents=True)
        shutil.copy(HERE.parent.parent / "book/ready/ch06/isolation.py", iso / "isolation.py")
        sentinel = iso / "SENTINEL"
        with (iso / "isolation.py").open("a") as handle:
            handle.write("\nfrom pathlib import Path as _P\n_P(__file__).with_name('SENTINEL').write_text('ran')\n")
        code, out = run(root / "router-helper/gate/gate.py", CAND / "good.py")
        self.assertEqual(code, 2, out)
        self.assertFalse(sentinel.exists(), "the edited helper was run before its pin was checked")


if __name__ == "__main__":
    unittest.main()
