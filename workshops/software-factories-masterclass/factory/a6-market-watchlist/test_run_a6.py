"""The gate says could not run, and does not judge, on a machine without sandbox-exec."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Preflight(unittest.TestCase):
    def test_without_sandbox_exec_the_gate_exits_2_before_any_test_runs(self):
        done = subprocess.run([sys.executable, str(HERE / "run_a6.py"), str(HERE / "tasks/a6-market-watchlist.json"), "baseline"],
                              capture_output=True, text=True, cwd=HERE, env={"PATH": "/nonexistent"})
        self.assertEqual(done.returncode, 2)
        self.assertIn("could not run: this check needs macOS", done.stdout)
        self.assertNotIn("REJECT", done.stdout)


if __name__ == "__main__":
    unittest.main()
