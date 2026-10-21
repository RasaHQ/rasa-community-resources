"""Acceptance for the travel-briefing project: three MCP tools, honest spoken answers, nothing gated.

Run with MANTLE_PROJECT pointing at the project to grade and the factory folder on PYTHONPATH (for accept_lib.py).
Offline: no model, licence or network. It grades what Mantle will load, not the briefing service behind it.
"""
import unittest

import accept_lib as lib
import yaml

SKILL = "briefing"
TOOLS = ["mcp/briefing:start_briefing", "mcp/briefing:get_briefing", "mcp/briefing:revise_briefing"]


def body():
    return " ".join(lib.skill_text(SKILL).split("---", 2)[2].lower().split())


def server():
    config = yaml.safe_load((lib.PROJECT / "integrations.yml").read_text())
    return next((s for s in config.get("mcp_servers", []) if s["name"] == "briefing"), None)


class BriefingSkill(unittest.TestCase):
    def test_the_engine_has_no_objection_to_the_project(self):
        self.assertEqual(lib.findings(), [])

    def test_the_skill_compiles_under_its_own_name(self):
        self.assertEqual(lib.skill(SKILL).id, SKILL)

    def test_all_three_briefing_tools_are_imported(self):
        names = lib.skill(SKILL).import_tool_names
        for tool in TOOLS:
            self.assertIn(tool, names)

    def test_the_server_is_configured_and_reached_over_http_on_loopback(self):
        found = server()
        self.assertIsNotNone(found, "no mcp_servers entry named briefing")
        self.assertTrue(found["url"].startswith("http://127.0.0.1:"), found["url"])

    def test_nothing_waits_for_confirmation_because_nothing_writes(self):
        for tool in lib.skill(SKILL).tools:
            gate = tool.requires_confirmation
            self.assertTrue(gate is None or not gate.enabled, f"{tool.name} must not be gated")

    def test_the_skill_declares_no_local_tools(self):
        self.assertFalse((lib.PROJECT / "skills" / SKILL / "tools.py").exists())

    def test_a_flight_is_delayed_only_when_the_provider_says_so(self):
        self.assertIn("delayed only when the provider's reported status says so", body())

    def test_numbers_are_said_as_they_appear_in_the_data(self):
        self.assertIn("exactly as they appear in the briefing data", body())

    def test_a_transfer_time_is_an_assumption_never_traffic(self):
        text = body()
        self.assertIn("is an assumption", text)
        self.assertIn("never call it traffic or live", text)

    def test_replayed_and_delayed_data_is_said_to_be_so(self):
        text = body()
        self.assertIn("replayed or delayed", text)
        self.assertIn("never call market data real time", text)

    def test_missing_input_is_asked_for_then_the_briefing_is_revised(self):
        text = body()
        self.assertIn("if it returns `needs_input`, ask the caller that one question, then call `revise_briefing` with the answer", text)

    def test_an_unavailable_source_is_named_and_no_old_value_is_repeated(self):
        self.assertIn("do not repeat an earlier value as current", body())

    def test_the_cards_are_said_to_be_zeocores_and_ours_not_mantles(self):
        text = body()
        self.assertIn("defined by zeocore and drawn by our renderer", text)
        self.assertIn("mantle does not provide them", text)

    def test_a_field_the_data_calls_not_provided_is_never_filled_in(self):
        self.assertIn("never fill it in", body())


if __name__ == "__main__":
    unittest.main()
