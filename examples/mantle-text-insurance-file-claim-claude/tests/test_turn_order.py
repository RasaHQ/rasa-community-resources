"""Offline checks for the Claude turn-order fix. No model, no network, no licence.

The first request below has the shape of the one Mantle sent on the opening
REST turn in the Willow Shop returns build
(examples/mantle-text-retail-return-claude, probe-opening-turn-debug/), with
this agent's greeting and a customer message from this build's scripts.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib.turn_order import ENGINE_NOTE, end_on_customer_side  # noqa: E402

CANNED = ("A canned reply was already sent this turn. Do not repeat, summarize, or\n"
          "paraphrase it. Continue from there with whatever naturally comes next.")
OPENING = [
    {"role": "system", "content": "You are the HarborCover claims intake assistant..."},
    {"role": "user", "content": "A pipe leaked on 26 September and brought down my kitchen ceiling."},
    {"role": "assistant", "content": "Hi, this is HarborCover claims. I can take a first report of a new loss or tell you where an existing claim stands. What happened?"},
    {"role": "system", "content": CANNED},
]


class TurnOrderTests(unittest.TestCase):
    def test_opening_turn_ends_on_a_user_message(self):
        fixed, moved = end_on_customer_side(OPENING)
        self.assertEqual(moved, 1)
        self.assertEqual([m["role"] for m in fixed], ["system", "user", "assistant", "user"])
        self.assertTrue(fixed[-1]["content"].startswith(ENGINE_NOTE))
        self.assertIn("A canned reply was already sent", fixed[-1]["content"])
        self.assertEqual(fixed[:3], OPENING[:3])

    def test_what_anthropic_receives_after_system_hoisting(self):
        """LiteLLM moves system messages to the top-level prompt; the last one left must be the user's."""
        before = [m for m in OPENING if m["role"] != "system"]
        after = [m for m in end_on_customer_side(OPENING)[0] if m["role"] != "system"]
        self.assertEqual(before[-1]["role"], "assistant")
        self.assertEqual(after[-1]["role"], "user")

    def test_requests_already_ending_on_the_customer_are_untouched(self):
        for messages in (
            OPENING[:2],
            [*OPENING[:3], {"role": "user", "content": "Yes."}],
            [*OPENING[:3], {"role": "assistant", "content": None, "tool_calls": [{"id": "t1"}]},
             {"role": "tool", "tool_call_id": "t1", "content": "{}"}, {"role": "system", "content": "note"}],
        ):
            with self.subTest(last=messages[-1]["role"]):
                fixed, moved = end_on_customer_side(messages)
                self.assertIs(fixed, messages)
                self.assertEqual(moved, 0)

    def test_no_customer_words_are_invented(self):
        only_system = [{"role": "system", "content": "prompt"}]
        self.assertIs(end_on_customer_side(only_system)[0], only_system)
        fixed, moved = end_on_customer_side(OPENING[:3])
        self.assertEqual(moved, 0)
        self.assertEqual(fixed[-1]["content"], f"{ENGINE_NOTE}\nContinue the conversation.")

    def test_hook_is_enabled_and_registered(self):
        tree = ast.parse((PROJECT / "hooks.py").read_text())
        names = {n.targets[0].id: n.value.value for n in tree.body
                 if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)}
        self.assertIs(names["ENABLED"], True)
        decorated = [d.func.id for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                     for d in n.decorator_list if isinstance(d, ast.Call)]
        self.assertEqual(decorated, ["modify_model_request"])


if __name__ == "__main__":
    unittest.main()
