"""The shipped reference agent is exactly what the compiler produces from its specification."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from factory import build  # noqa: E402

FILES = ["agent.yml", "integrations.yml", "skills/travel_briefing/skill.md", "skills/travel_briefing/tools.py"]


class ReferenceSyncTests(unittest.TestCase):
    def test_reference_tools_start_with_the_current_readers(self):
        head = (ROOT / "travel_data.py").read_text().split("if __name__")[0]
        tools = (ROOT / "reference/finished-agent/skills/travel_briefing/tools.py").read_text()
        self.assertTrue(tools.startswith(head), "regenerate the reference agent from the compiler")

    def test_reference_agent_equals_the_compiler_output(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            build.generate((ROOT / "reference/full.json").read_bytes(), project)
            for name in FILES:
                self.assertEqual((project / name).read_bytes(), (ROOT / "reference/finished-agent" / name).read_bytes(), name)

    def test_rules_order_the_date_question_before_any_weather_lookup(self):
        self.assertIn("wait for the answer before calling it again", build.LANDING_RULES)
        self.assertIn("flight number and the arrival date", build.LANDING_RULES)
        self.assertIn("source field", build.RULES)

    def test_the_date_gate_applies_only_where_there_is_a_flight_lookup(self):
        full = build.rules_for(["weather", "fx", "flights", "status"])
        self.assertIn(build.LANDING_RULES, full)
        for tools in (["weather", "fx"], ["fx"], ["weather", "flights"]):
            self.assertNotIn("flight number and the arrival date", build.rules_for(tools), tools)
        self.assertIn(build.AIRPORT_WEATHER_RULES, build.rules_for(["weather", "fx"]))
        self.assertNotIn("weather at an airport", build.rules_for(["fx"]))

    def test_the_starter_agent_keeps_direct_airport_weather(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "starter"
            build.generate((ROOT / "reference/starter.json").read_bytes(), project)
            skill = (project / "skills/travel_briefing/skill.md").read_text()
            self.assertIn("weather at an airport", skill)
            self.assertNotIn("flight number and the arrival date", skill)


if __name__ == "__main__":
    unittest.main()
