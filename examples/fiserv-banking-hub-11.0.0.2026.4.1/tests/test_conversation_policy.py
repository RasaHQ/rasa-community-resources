"""Alias context and no repeated text. Both fail on the old behaviour."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib import conversation_policy as policy
from rasa.mantle.hooks.payloads import ModelRequestPayload, ModelResponsePayload

HOOKS = Path(__file__).resolve().parents[1] / "hooks.py"


class AliasContext(unittest.TestCase):
    def request(self):
        return ModelRequestPayload(sender_id="caller", messages=[
            {"role": "system", "content": "persona"}, {"role": "user", "content": "What is my checking balance?"}])

    def test_the_caller_aliases_are_in_every_request_once(self):
        messages = policy.add_alias_note(policy.add_alias_note(self.request())).messages
        notes = [m for m in messages if policy.ALIAS_NOTE_MARK in m["content"]]
        self.assertEqual(len(notes), 1)
        self.assertEqual(messages[1]["role"], "system")
        for alias in ("DDA-A", "SDA-A", "LOAN-A"):
            self.assertIn(alias, notes[0]["content"])
        self.assertNotIn("DDA-B", notes[0]["content"])

    def test_the_hook_is_registered_so_no_discovery_call_is_needed(self):
        source = HOOKS.read_text()
        self.assertIn("@modify_model_request()", source)
        self.assertIn("add_alias_note", source)

    def test_the_skill_reserves_banking_accounts_for_an_explicit_request(self):
        skill = (HOOKS.parent / "skills" / "banking" / "skill.md").read_text()
        self.assertNotIn("Use @tool.banking_accounts to list permitted aliases.", skill)
        self.assertIn("only when the caller asks which accounts they have", skill)


class NoRepeatedText(unittest.TestCase):
    def setUp(self):
        policy._said.clear()
        self.native = SimpleNamespace(sender_id="caller", turn=object(), is_cancelled=False)
        p = patch.object(policy, "current_turn_context", return_value=self.native)
        p.start(); self.addCleanup(p.stop); self.addCleanup(policy._said.clear)

    def say(self, text):
        return policy.drop_repeated_text(ModelResponsePayload(sender_id="caller", text=text, tool_calls=[])).text

    def test_the_same_follow_up_is_not_said_twice_in_one_turn(self):
        self.assertEqual(self.say("Your balance is USD 1,250.00. What would you like to do next?"),
                         "Your balance is USD 1,250.00. What would you like to do next?")
        self.assertIsNone(self.say("What would you like to do next?"))

    def test_a_repeated_trailing_question_is_cut_and_new_content_kept(self):
        self.say("You have DDA-A and savings-A. What would you like to do next?")
        self.assertEqual(self.say("Your balance is USD 1,250.00. What would you like to do next?"),
                         "Your balance is USD 1,250.00.")

    def test_no_greeting_is_spoken_alongside_skill_activation(self):
        reply = policy.drop_repeated_text(ModelResponsePayload(sender_id="caller",
            text="How can I assist you with your banking accounts today?",
            tool_calls=[{"id": "a", "tool_name": "activate", "tool_args": {"target_id": "banking"}, "type": "function"}]))
        self.assertIsNone(reply.text)
        self.assertEqual(reply.tool_calls[0]["tool_name"], "activate")

    def test_a_new_turn_starts_clean(self):
        self.say("What would you like to do next?")
        self.native.turn = object()
        self.assertEqual(self.say("What would you like to do next?"), "What would you like to do next?")



class RegisteredReplyHook(unittest.IsolatedAsyncioTestCase):
    """Drives the hook as hooks.py registers it, so it fails if dedupe is not wired in."""

    async def test_the_registered_reply_hook_drops_a_repeated_follow_up(self):
        import importlib.util
        from lib import reply_policy
        spec = importlib.util.spec_from_file_location("bank_hooks_under_test", HOOKS)
        hooks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hooks)
        native = SimpleNamespace(sender_id="caller", turn=object(), is_cancelled=False)
        policy._said.clear(); reply_policy._delivered.clear()
        self.addCleanup(policy._said.clear)
        with patch.object(policy, "current_turn_context", return_value=native), \
                patch.object(reply_policy, "current_turn_context", return_value=native):
            first = await hooks.banking_host_reply(ModelResponsePayload(
                sender_id="caller", text="What would you like to do next?", tool_calls=[]))
            second = await hooks.banking_host_reply(ModelResponsePayload(
                sender_id="caller", text="What would you like to do next?", tool_calls=[]))
        self.assertEqual(first.text, "What would you like to do next?")
        self.assertIsNone(second.text)

if __name__ == "__main__":
    unittest.main()
