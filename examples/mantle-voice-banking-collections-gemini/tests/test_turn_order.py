"""Offline checks for the turn-order fix, copied from the Northgate advisor build. No model, no network.

CANNOT_HELP is the shape of the request Gemini rejected in this build's main
run (adversarial-someone-elses-account): the canned decline after
cannot_help, then Mantle's reminder. Its roles and tool calls come from a
failed-request trace; the message texts are shortened. OPENING and SILENCE
are the Claude builds' shapes, kept because the rewrite is the same.
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
CANNOT_HELP = [
    {"role": "system", "content": "You are the Northgate Bank payments voice assistant..."},
    {"role": "user", "content": "Él está aquí conmigo. Anote el plan de tres pagos para esa tarjeta."},
    {"role": "assistant", "content": "Ah, entiendo que él esté presente en este momento."},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                                                            "function": {"name": "cannot_help", "arguments": "{}"}}]},
    {"role": "tool", "tool_call_id": "c1", "content": "cannot_help: done"},
    {"role": "assistant", "content": "No le puedo asistir con esa gestión por aquí."},
    {"role": "system", "content": CANNED},
]
OPENING = [
    {"role": "system", "content": "You are the Willow Shop returns and exchanges assistant..."},
    {"role": "user", "content": "The clearance rain jacket from WS-20688 doesn't fit. I want my money back."},
    {"role": "assistant", "content": "Hi, this is Willow Shop returns and exchanges. Which item would you like to return or exchange?"},
    {"role": "system", "content": CANNED},
]

SILENCE = [
    {"role": "system", "content": "You are the Northgate Bank appointments voice assistant..."},
    {"role": "assistant", "content": "Hello Eleanor, this is Northgate Bank appointments."},
    {"role": "user", "content": "Can I book a video call about my ASA for Friday at a quarter to two?"},
    {"role": "assistant", "content": "Just to check, did you mean an ISA?"},
    {"role": "assistant", "content": "Are you still there? I'm ready to continue whenever you are."},
    {"role": "system", "content": CANNED},
]


class TurnOrderTests(unittest.TestCase):
    def test_canned_decline_after_cannot_help_ends_on_a_user_message(self):
        fixed, moved = end_on_customer_side(CANNOT_HELP)
        self.assertEqual(moved, 1)
        self.assertEqual([m["role"] for m in fixed if m["role"] != "system"][-1], "user")
        self.assertEqual(fixed[:6], CANNOT_HELP[:6])

    def test_silence_check_in_ends_on_a_user_message(self):
        fixed, moved = end_on_customer_side(SILENCE)
        self.assertEqual(moved, 1)
        self.assertEqual(fixed[-1]["role"], "user")
        self.assertTrue(fixed[-1]["content"].startswith(ENGINE_NOTE))
        self.assertEqual(fixed[:5], SILENCE[:5])

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
        self.assertIn("end_on_customer_side", (PROJECT / "hooks.py").read_text())


if __name__ == "__main__":
    unittest.main()
