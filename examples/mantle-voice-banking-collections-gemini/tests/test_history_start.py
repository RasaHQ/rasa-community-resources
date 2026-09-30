"""Offline checks for the Gemini history fix. No model, no network, no licence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib.history_start import ENGINE_NOTE, start_on_customer_side  # noqa: E402

CALL = {"role": "assistant", "content": None,
        "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "activate", "arguments": "{}"}}]}
RESULT = {"role": "tool", "tool_call_id": "c1", "content": "activate: done"}


class HistoryStartTests(unittest.TestCase):
    def test_a_history_opening_on_a_tool_call_gets_an_engine_note(self):
        messages = [{"role": "system", "content": "prompt"}, CALL, RESULT,
                    {"role": "assistant", "content": "Ese plan ya venció."}, {"role": "user", "content": "Sí."}]
        out = start_on_customer_side(messages)
        self.assertEqual([m["role"] for m in out], ["system", "user", "assistant", "tool", "assistant", "user"])
        self.assertEqual(out[1]["content"], ENGINE_NOTE)
        self.assertEqual(out[2:], messages[1:])

    def test_a_history_opening_on_the_customer_is_untouched(self):
        messages = [{"role": "system", "content": "prompt"}, {"role": "user", "content": "Hola"}, CALL, RESULT]
        self.assertIs(start_on_customer_side(messages), messages)

    def test_system_only_or_empty(self):
        self.assertEqual(start_on_customer_side([]), [])
        only = [{"role": "system", "content": "prompt"}]
        self.assertIs(start_on_customer_side(only), only)

    def test_the_note_never_claims_to_be_the_customer(self):
        self.assertIn("not from the customer", ENGINE_NOTE)


if __name__ == "__main__":
    unittest.main()
