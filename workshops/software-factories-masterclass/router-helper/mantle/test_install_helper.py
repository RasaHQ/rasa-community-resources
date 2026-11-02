"""Test the install script on a fake agent folder. Needs PyYAML, which Rasa's environment has."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

yaml = __import__("yaml")
HERE = Path(__file__).resolve().parent


class Install(unittest.TestCase):
    def test_starter_skills_go_and_the_router_skill_stays(self):
        agent = Path(tempfile.mkdtemp(prefix="agent-"))
        (agent / "skills/view_transactions").mkdir(parents=True)
        (agent / "skills/view_transactions/skill.md").write_text("banking")
        (agent / "agent.yml").write_text("agent:\n  id: x1\n  language: en\n  persona: You are a bank.\nrules:\n  - Help with banking.\ntool_timeout: 30\n")
        done = subprocess.run([sys.executable, str(HERE / "install_helper.py"), str(agent)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(sorted(p.name for p in (agent / "skills").iterdir()), ["router_restart"])
        data = yaml.safe_load((agent / "agent.yml").read_text())
        self.assertEqual(data["agent"]["id"], "x1")
        self.assertEqual(data["tool_timeout"], 30)
        self.assertIn("router", data["agent"]["persona"])
        self.assertNotIn("bank", " ".join(data["rules"]).replace("Never mention banking", ""))

    def test_a_folder_that_is_not_an_agent_is_refused(self):
        done = subprocess.run([sys.executable, str(HERE / "install_helper.py"), tempfile.mkdtemp()], capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)


if __name__ == "__main__":
    unittest.main()
