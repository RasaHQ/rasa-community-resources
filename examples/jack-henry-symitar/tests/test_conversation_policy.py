"""Alias context and no repeated text. Both fail on the old behaviour."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib import conversation_policy as policy
from lib import native_adapter
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
        for alias in ("checking (deposit)", "savings (deposit)", "car (loan)"):
            self.assertIn(alias, notes[0]["content"])
        self.assertNotIn("checking-B", notes[0]["content"])
        self.assertNotIn("0001", notes[0]["content"])  # never a share or loan id

    def test_the_listed_aliases_are_exactly_the_host_fixture_aliases(self):
        import json
        fixture = json.loads((HOOKS.parent / "fixtures" / "fictional.json").read_text())
        self.assertEqual(policy.DEPOSIT_ALIASES, tuple(item["alias"] for item in fixture["shares"]))
        self.assertEqual(policy.LOAN_ALIASES, tuple(item["alias"] for item in fixture["loans"]))

    def test_the_hook_is_registered_so_no_discovery_call_is_needed(self):
        source = HOOKS.read_text()
        self.assertIn("@modify_model_request()", source)
        self.assertIn("add_alias_note", source)

    def test_the_skill_reserves_banking_accounts_for_an_explicit_request(self):
        skill = (HOOKS.parent / "skills" / "banking" / "skill.md").read_text()
        self.assertNotIn("Use banking_accounts to learn the permitted aliases.", skill)
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
        self.say("You have checking-A and savings-A. What would you like to do next?")
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

class VerifyTrigger(unittest.IsolatedAsyncioTestCase):
    """"Verify me" is answered only when the host reports a refresh from this caller turn."""

    def setUp(self):
        from lib import reply_policy
        reply_policy._delivered.clear(); self.addCleanup(reply_policy._delivered.clear)
        self.sent = []
        async def send(text): self.sent.append(text)
        self.context = SimpleNamespace(is_cancelled=False, send=send)
        self.conversation = SimpleNamespace(lock=__import__("asyncio").Lock(), outcome={})
        self.native = SimpleNamespace(sender_id="caller", turn=SimpleNamespace(text="Verify me."), is_cancelled=False)
        for target in (native_adapter, reply_policy):
            p = patch.object(target, "current_turn_context", return_value=self.native); p.start(); self.addCleanup(p.stop)
        async def conv(context): return self.conversation
        p = patch.object(native_adapter, "_conversation", side_effect=conv); p.start(); self.addCleanup(p.stop)

    def observed(self, state):
        async def observe(conversation, context, **kwargs): return {"state": state}
        p = patch.object(native_adapter, "_observe", side_effect=observe); p.start(); self.addCleanup(p.stop)

    async def test_a_host_refresh_delivers_the_exact_sentence_once(self):
        self.observed("simulated_assurance_refreshed")
        result = await native_adapter.banking_refresh_verification(context=self.context)
        self.assertEqual(result.llm_response, {"state": "verified"})
        self.assertEqual(self.sent, [native_adapter.VERIFIED_TEXT])

    async def test_no_refresh_or_an_expired_phrase_says_nothing_refreshed(self):
        for state in ("simulated_assurance_expired", "not_submitted", None):
            with self.subTest(state=state):
                self.sent.clear(); self.observed(state)
                result = await native_adapter.banking_refresh_verification(context=self.context)
                self.assertEqual(result.llm_response, {"state": "refused", "reason": "verification_not_observed"})
                self.assertEqual(self.sent, [])

    async def test_without_the_raw_phrase_or_on_a_session_start_pass_nothing_is_verified(self):
        self.observed("simulated_assurance_refreshed")
        for turn in (SimpleNamespace(text="What is my balance?"),
                     SimpleNamespace(text="Verify me.", trigger="session_start")):
            with self.subTest(turn=turn):
                self.native.turn = turn
                result = await native_adapter.banking_refresh_verification(context=self.context)
                self.assertEqual(result.llm_response, {"state": "refused", "reason": "say_verify_me"})
        self.assertEqual(self.sent, [])


class UnknownBeforeFallback(unittest.IsolatedAsyncioTestCase):
    async def test_a_confirmation_after_an_unresolved_outcome_says_do_not_retry(self):
        from lib import reply_policy
        reply_policy._delivered.clear(); self.addCleanup(reply_policy._delivered.clear)
        sent = []
        async def send(text): sent.append(text)
        async def call(credential, name, args):
            return {"state": "pending", "reason": "unresolved_transfer_no_retry"}
        conversation = SimpleNamespace(lock=__import__("asyncio").Lock(), credential="c", pending_request=None,
                                       client=SimpleNamespace(call=call))
        native = SimpleNamespace(sender_id="caller", turn=SimpleNamespace(text="Yes."), is_cancelled=False)
        async def conv(context): return conversation
        async def observe(conversation, context, *, transfer=True): return {}
        with patch.object(native_adapter, "current_turn_context", return_value=native), \
                patch.object(reply_policy, "current_turn_context", return_value=native), \
                patch.object(native_adapter, "_conversation", side_effect=conv), \
                patch.object(native_adapter, "_observe", side_effect=observe):
            result = await native_adapter.banking_transfer_status(
                context=SimpleNamespace(is_cancelled=False, send=send))
        self.assertEqual(result.llm_response["reason"], "unresolved_transfer_no_retry")
        self.assertEqual(sent, [native_adapter.UNKNOWN_TEXT])
        self.assertNotIn("new transfer", sent[0].casefold())


if __name__ == "__main__":
    unittest.main()
