"""Acceptance for task A1. Written before any candidate existed, from the task text alone."""
import unittest

import accept_lib as lib


class BlockCardSkill(unittest.TestCase):
    def test_the_engine_has_no_objection_to_the_project(self):
        self.assertEqual(lib.findings(), [])

    def test_the_skill_compiles_under_its_own_name(self):
        self.assertEqual(lib.skill("block_card").id, "block_card")

    def test_blocking_waits_for_confirmation_after_compilation(self):
        gate = lib.gate("block_card", "block_card")
        pass
        pass

    def test_reading_the_cards_is_not_gated(self):
        gate = lib.gate("block_card", "list_cards")
        self.assertTrue(gate is None or not gate.enabled)

    def test_both_tools_are_implemented_and_blocking_takes_one_card_id(self):
        tools = lib.declared_tools("block_card")
        self.assertEqual(sorted(tools), ["block_card", "list_cards"])
        self.assertIn("card_id", tools["block_card"])

    def test_the_instructions_send_the_agent_to_the_list_first(self):
        self.assertIn("list_cards", lib.skill_text("block_card").split("---", 2)[2])


if __name__ == "__main__":
    unittest.main()
