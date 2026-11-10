import tempfile
import unittest
from pathlib import Path
from shop_adviser.native_fixture import observe_handoff_owner_mutation


class HandoffOwnerMutation(unittest.TestCase):
    def test_ready_schema_and_product_tool_do_not_prove_memory_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            result = observe_handoff_owner_mutation(Path(directory) / "memory.sqlite")
        bound, omitted = result["observations"]
        for observation in (bound, omitted):
            self.assertEqual(observation["status"], "ready")
            self.assertEqual(observation["public_product_id"], "WS-HAND-01")
            self.assertEqual(observation["user_messages_in_initial_input"], 1)
            self.assertTrue(observation["native_product_tool_seen"])
        self.assertFalse(bound["preference_in_initial_input"])
        self.assertTrue(omitted["preference_in_initial_input"])


if __name__ == "__main__":
    unittest.main()
