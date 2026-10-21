"""Acceptance for the travel-desk project: read-only skill, one MCP tool, honest spoken answers.

Run with MANTLE_PROJECT pointing at the project to grade and the factory folder on PYTHONPATH (for accept_lib.py).
Offline: no model, licence or network. It grades what Mantle will load, not the MCP server behind it.
"""
import unittest

import accept_lib as lib
import yaml

SKILL = "desk"


def body():
    return lib.skill_text(SKILL).split("---", 2)[2].lower()


class DeskSkill(unittest.TestCase):
    def test_the_engine_has_no_objection_to_the_project(self):
        self.assertEqual(lib.findings(), [])

    def test_the_skill_compiles_under_its_own_name(self):
        self.assertEqual(lib.skill(SKILL).id, SKILL)

    def test_the_desk_tool_is_imported_from_a_configured_mcp_server(self):
        self.assertIn("mcp/desk:ask_desk_agent", lib.skill(SKILL).import_tool_names)
        config = yaml.safe_load((lib.PROJECT / "integrations.yml").read_text())
        self.assertIn("desk", [server["name"] for server in config.get("mcp_servers", [])])

    def test_the_desk_server_is_reached_over_http_on_loopback(self):
        config = yaml.safe_load((lib.PROJECT / "integrations.yml").read_text())
        server = next(s for s in config["mcp_servers"] if s["name"] == "desk")
        self.assertTrue(server["url"].startswith("http://127.0.0.1:"), server["url"])

    def test_the_skill_only_reads_so_nothing_waits_for_confirmation(self):
        for tool in lib.skill(SKILL).tools:
            gate = tool.requires_confirmation
            self.assertTrue(gate is None or not gate.enabled, f"{tool.name} is read-only and must not be gated")

    def test_the_skill_declares_no_local_tools(self):
        self.assertFalse((lib.PROJECT / "skills" / SKILL / "tools.py").exists(), "a read-only desk needs no local tool code")

    def test_the_instructions_never_let_the_agent_claim_a_delay(self):
        self.assertIn("never say a flight is delayed or on time", body())

    def test_the_instructions_say_the_numbers_come_from_the_tool_data(self):
        self.assertIn("exactly as they appear in its data", body())

    def test_the_instructions_name_the_rate_date_and_the_empty_result(self):
        self.assertIn("say its date", body())
        self.assertIn("do not repeat an earlier answer", body())


if __name__ == "__main__":
    unittest.main()
