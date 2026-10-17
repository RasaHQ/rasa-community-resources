"""Acceptance for the review-dispute project: an outside reviewer's advice must never stand in for the customer's confirmation.

Run with MANTLE_PROJECT pointing at the project to grade, from a folder where accept_lib.py is importable
(the factory copies accept_lib.py next to its suites; here: PYTHONPATH=../factory). Offline: no model, licence or network.
"""
import unittest

import accept_lib as lib
import yaml

SKILL = "review_dispute"


class ReviewDisputeSkill(unittest.TestCase):
    def test_the_engine_has_no_objection_to_the_project(self):
        self.assertEqual(lib.findings(), [])

    def test_blocking_waits_for_confirmation_after_compilation(self):
        gate = lib.gate(SKILL, "block_card")
        self.assertIsNotNone(gate, "the engine compiled the confirmation gate away")
        self.assertTrue(gate.enabled)

    def test_the_reviewer_tool_is_imported_from_a_configured_mcp_server(self):
        self.assertIn("mcp/reviewer:ask_reviewer", lib.skill(SKILL).import_tool_names)
        config = yaml.safe_load((lib.PROJECT / "integrations.yml").read_text())
        names = [server["name"] for server in config.get("mcp_servers", [])]
        self.assertIn("reviewer", names)

    def test_the_reviewer_server_is_reached_over_http_on_loopback(self):
        config = yaml.safe_load((lib.PROJECT / "integrations.yml").read_text())
        server = next(s for s in config["mcp_servers"] if s["name"] == "reviewer")
        self.assertTrue(server["url"].startswith("http://127.0.0.1:"), server["url"])

    def test_the_reviewers_answer_is_not_a_confirmation(self):
        gate = lib.gate(SKILL, "ask_reviewer")
        self.assertTrue(gate is None or not gate.enabled, "advice must not be what the engine treats as the caller's yes")

    def test_the_instructions_tell_the_agent_the_answer_is_advice(self):
        body = lib.skill_text(SKILL).split("---", 2)[2].lower()
        self.assertIn("advice", body)
        self.assertIn("never block a card until the caller has confirmed", body)


if __name__ == "__main__":
    unittest.main()
