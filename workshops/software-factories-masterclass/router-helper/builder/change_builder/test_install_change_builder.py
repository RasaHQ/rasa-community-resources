"""Tests for install_change_builder.py on fake agent folders. Needs PyYAML."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent


def make(config):
    agent = Path(tempfile.mkdtemp(prefix="agent-"))
    (agent / "skills").mkdir()
    (agent / "agent.yml").write_text(config)
    return agent


def install(agent):
    return subprocess.run([sys.executable, str(HERE / "install_change_builder.py"), str(agent)], capture_output=True, text=True)


class Install(unittest.TestCase):
    def test_copies_the_skill_and_raises_the_default_timeout(self):
        for config in ("agent:\n  id: a\n", "agent:\n  id: a\ntool_timeout: 30\n"):
            agent = make(config)
            done = install(agent)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(sorted(p.name for p in (agent / "skills/change_builder").iterdir()), ["skill.md", "tools.py"])
            self.assertEqual(yaml.safe_load((agent / "agent.yml").read_text())["tool_timeout"], 400.0)

    def test_a_larger_timeout_is_kept_and_a_second_run_is_safe(self):
        agent = make("agent:\n  id: a\ntool_timeout: 900\n")
        self.assertEqual(install(agent).returncode, 0)
        self.assertEqual(install(agent).returncode, 0)
        self.assertEqual(yaml.safe_load((agent / "agent.yml").read_text())["tool_timeout"], 900.0)

    def test_unreadable_config_changes_nothing(self):
        agent = make("agent: [unclosed\n")
        done = install(agent)
        self.assertEqual(done.returncode, 2)
        self.assertFalse((agent / "skills/change_builder").exists())
        self.assertEqual((agent / "agent.yml").read_text(), "agent: [unclosed\n")


if __name__ == "__main__":
    unittest.main()
