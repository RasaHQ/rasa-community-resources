"""Test the install script on fake agent folders. Needs PyYAML, which Rasa's environment has."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

HERE = Path(__file__).resolve().parent
GOOD = "agent:\n  id: x1\n  language: en\n  persona: You are a bank.\nrules:\n  - Help with banking.\ntool_timeout: 30\n"


def make(config=GOOD):
    agent = Path(tempfile.mkdtemp(prefix="agent-"))
    for name in ("view_transactions", "custom"):
        (agent / "skills" / name).mkdir(parents=True)
        (agent / "skills" / name / "skill.md").write_text(name)
    (agent / "agent.yml").write_text(config)
    return agent


def install(agent):
    return subprocess.run([sys.executable, str(HERE / "install_helper.py"), str(agent)], capture_output=True, text=True)


class Install(unittest.TestCase):
    def test_other_skills_are_moved_not_deleted_and_the_router_skill_is_active(self):
        agent = make()
        done = install(agent)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(sorted(p.name for p in (agent / "skills").iterdir()), ["factory_reset_refusal", "router_restart"])
        self.assertEqual((agent / "starter-skills-moved/custom/skill.md").read_text(), "custom")
        data = yaml.safe_load((agent / "agent.yml").read_text())
        self.assertEqual((data["agent"]["id"], data["tool_timeout"]), ("x1", 30))
        self.assertIn("router", data["agent"]["persona"])
        self.assertTrue(any("not even steps" in r for r in data["rules"]))
        self.assertIn("router_restart", data["prompts"]["routing_no_active_skill"])

    def test_malformed_agent_yml_changes_nothing(self):
        agent = make("agent: [unclosed\n  persona: x")
        before = sorted(str(p.relative_to(agent)) for p in agent.rglob("*"))
        done = install(agent)
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertEqual(sorted(str(p.relative_to(agent)) for p in agent.rglob("*")), before)
        self.assertEqual((agent / "skills/custom/skill.md").read_text(), "custom")
        self.assertEqual((agent / "agent.yml").read_text(), "agent: [unclosed\n  persona: x")

    def test_running_twice_is_safe(self):
        agent = make()
        self.assertEqual(install(agent).returncode, 0)
        self.assertEqual(install(agent).returncode, 0)
        self.assertEqual(sorted(p.name for p in (agent / "skills").iterdir()), ["factory_reset_refusal", "router_restart"])
        self.assertEqual((agent / "starter-skills-moved/custom/skill.md").read_text(), "custom")

    def test_a_folder_that_is_not_an_agent_is_refused(self):
        self.assertEqual(install(Path(tempfile.mkdtemp())).returncode, 2)


if __name__ == "__main__":
    unittest.main()
