"""Acceptance for task A2. Written before any candidate existed, from the task text alone."""
import unittest

import accept_lib as lib

RULE = "Never say more than the last four digits of a card number."


class DigitsRule(unittest.TestCase):
    def test_the_engine_has_no_objection_to_the_project(self):
        self.assertEqual(lib.findings(), [])

    def test_the_rule_is_one_mantle_will_put_in_the_prompt(self):
        self.assertIn(RULE, lib.agent_rules())

    def test_the_persona_is_unchanged(self):
        self.assertEqual(lib.persona(), "A calm, careful bank assistant that helps customers with their cards.")


if __name__ == "__main__":
    unittest.main()
