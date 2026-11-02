"""Tests for the first check: it passes, it fails on the wrong command, and it refuses to guess."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
CHECK = HERE / "check_helper.py"
TOOLS = HERE / "mantle/skills/router_restart/tools.py"


def run(path):
    done = subprocess.run([sys.executable, "-I", str(CHECK), str(path)], capture_output=True, text=True)
    return done.returncode, done.stdout


class CheckHelper(unittest.TestCase):
    def write(self, name, text):
        folder = Path(tempfile.mkdtemp(prefix="check-helper-"))
        self.addCleanup(lambda: [p.unlink() for p in folder.iterdir()] and folder.rmdir())
        path = folder / name
        path.write_text(text)
        return path

    def test_the_supplied_tool_passes(self):
        self.assertEqual(run(TOOLS)[0], 0)

    def test_the_wrong_command_fails_even_if_the_reply_would_sound_right(self):
        broken = self.write("tools.py", TOOLS.read_text().replace('"REBOOT"', '"FACTORY_RESET"'))
        code, out = run(broken)
        self.assertEqual(code, 1, out)
        self.assertIn("FACTORY_RESET", out)

    def test_a_studio_export_with_the_right_command_passes(self):
        path = self.write("studio_flows.yml", "flows:\n  restart_router:\n    steps:\n      - set_slots:\n          - command_sent: \"REBOOT\"\n")
        self.assertEqual(run(path)[0], 0)

    def test_a_studio_export_with_the_wrong_command_fails(self):
        path = self.write("studio_flows.yml", "flows:\n  restart_router:\n    steps:\n      - set_slots:\n          - command_sent: FACTORY_RESET\n")
        self.assertEqual(run(path)[0], 1)

    def test_no_command_found_is_not_a_pass(self):
        self.assertEqual(run(self.write("tools.py", "OPERATIONS = {}\n"))[0], 2)
        self.assertEqual(run(self.write("studio_flows.yml", "flows: {}\n"))[0], 2)
        self.assertEqual(run(Path("/nonexistent/file.py"))[0], 2)


if __name__ == "__main__":
    unittest.main()
