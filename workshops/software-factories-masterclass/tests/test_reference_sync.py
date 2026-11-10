"""The shipped reference agent is exactly what the compiler produces from its specification."""
import ast
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


def weather_parameters(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "destination_weather":
            return [a.arg for a in node.args.args if a.arg != "context"]
    raise AssertionError("no destination_weather tool")


class WeatherInterfaceTests(unittest.TestCase):
    """A flight-briefing agent forecasts a landing from the flight and date only; the starter keeps airport mode."""

    def compiled(self, spec):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / spec
            build.generate((ROOT / "reference" / (spec + ".json")).read_bytes(), project)
            return (project / "skills/travel_briefing/tools.py").read_text()

    def test_agents_with_a_flight_lookup_get_the_flight_first_weather_tool(self):
        arrival = ["flight_number", "flight_date", "airport_code", "arrival_time"]
        self.assertEqual(weather_parameters(self.compiled("full")), arrival)
        reference = (ROOT / "reference/finished-agent/skills/travel_briefing/tools.py").read_text()
        self.assertEqual(weather_parameters(reference), arrival)

    def test_the_starter_keeps_airport_mode(self):
        self.assertEqual(weather_parameters(self.compiled("starter")), ["airport_code", "arrival_time"])

    def test_the_old_call_shape_cannot_reach_the_full_agents_weather_tool(self):
        _, parameters, _, _ = build.tool_spec("weather", ["weather", "fx", "flights", "status"])
        namespace = {}
        exec(f"def destination_weather({parameters}):\n    return 'called'", namespace)
        with self.assertRaises(TypeError):
            namespace["destination_weather"](airport_code="BGO", arrival_time="2026-11-03T20:10:00+01:00")
        self.assertEqual(namespace["destination_weather"]("ZZ201", ""), "called")

    def test_an_airport_and_time_without_a_flight_cannot_start_the_weather_call(self):
        _, parameters, _, _ = build.tool_spec("weather", ["weather", "fx", "flights", "status"])
        self.assertIn("flight_number: str", parameters)
        self.assertNotIn("flight_number: str =", parameters)
        self.assertNotIn("flight_date: str =", parameters)

    def test_an_empty_flight_returns_no_forecast_and_asks_for_flight_and_date(self):
        import travel_data

        result = travel_data.read("weather", "", "", "", "")
        self.assertEqual(result["state"], "needs_flight")
        self.assertIsNone(result["forecast"])
        self.assertIn("flight number and the arrival date", result["reason"])


if __name__ == "__main__":
    unittest.main()
