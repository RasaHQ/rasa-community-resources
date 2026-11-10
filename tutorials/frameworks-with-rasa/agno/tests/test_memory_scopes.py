import tempfile
import unittest
from pathlib import Path

from shop_adviser.native_fixture import observe_memory_strategy


class MemoryScopes(unittest.TestCase):
    def observe(self, strategy, *, reuse_agent=True):
        with tempfile.TemporaryDirectory() as tmp:
            result = observe_memory_strategy(
                Path(tmp) / "memory.sqlite", strategy, reuse_agent=reuse_agent
            )
        for item in result["observations"]:
            self.assertFalse(item["previous_question_in_initial_input"])
            self.assertEqual(item["user_messages_in_initial_input"], 1)
            self.assertTrue(item["native_product_tool_seen"])
            self.assertTrue(item["final_output_present"])
        return result["observations"]

    def test_stable_user_retains_preference_across_new_thread_and_excludes_other_user(
        self,
    ):
        a, b = self.observe("correct")
        self.assertTrue(a["preference_in_initial_input"])
        self.assertFalse(b["preference_in_initial_input"])

    def test_thread_as_memory_key_loses_same_customers_preference(self):
        a, b = self.observe("session-as-user")
        self.assertFalse(a["preference_in_initial_input"])
        self.assertFalse(b["preference_in_initial_input"])

    def test_omitting_owner_shares_seeded_default_preference_despite_new_history(self):
        a, b = self.observe("omitted")
        self.assertTrue(a["preference_in_initial_input"])
        self.assertTrue(b["preference_in_initial_input"])

    def test_fresh_agent_preserves_correct_user_memory_across_conversations(self):
        a, b = self.observe("correct", reuse_agent=False)
        self.assertTrue(a["preference_in_initial_input"])
        self.assertFalse(b["preference_in_initial_input"])

    def test_fresh_agent_cannot_restore_memory_stored_under_previous_thread(self):
        a, b = self.observe("session-as-user", reuse_agent=False)
        self.assertFalse(a["preference_in_initial_input"])
        self.assertFalse(b["preference_in_initial_input"])

    def test_fresh_agent_still_loads_seeded_default_preference_for_both_customers(self):
        a, b = self.observe("omitted", reuse_agent=False)
        self.assertTrue(a["preference_in_initial_input"])
        self.assertTrue(b["preference_in_initial_input"])


if __name__ == "__main__":
    unittest.main()
