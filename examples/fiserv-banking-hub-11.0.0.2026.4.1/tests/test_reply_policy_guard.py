"""The reply hook never lets model text announce a review or acceptance the host did not deliver."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib import reply_policy as policy
from rasa.mantle.hooks.payloads import ModelResponsePayload


class HostOnlyWording(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        policy._delivered.clear(); policy._retries.clear(); policy._sent.clear()
        self.native = SimpleNamespace(sender_id="caller", turn=object(), is_cancelled=False)
        p = patch.object(policy, "current_turn_context", return_value=self.native)
        p.start(); self.addCleanup(p.stop); self.addCleanup(policy._delivered.clear)

    def payload(self, text):
        return ModelResponsePayload(sender_id="caller", text=text, tool_calls=[])

    async def test_imitated_review_or_acceptance_is_retried_then_replaced(self):
        from rasa.mantle.hooks.exceptions import RetryModel
        for text in ("Review: transfer USD 7.00 from DDA-A to savings-A. Say confirm transfer next.",
                     "The transfer request was accepted. Accepted does not mean posted."):
            with self.subTest(text=text):
                self.native.turn = object()
                for _ in range(policy._MAX_RETRIES):
                    with self.assertRaises(RetryModel) as raised:
                        await policy.keep_host_reply_once(self.payload(text))
                    self.assertIn("banking_review_transfer", raised.exception.feedback)
                reply = await policy.keep_host_reply_once(self.payload(text))
                self.assertEqual(reply.text, policy.NO_TRANSFER_TEXT)
                self.assertNotIn("nothing was sent", reply.text.casefold())

    async def test_verify_me_answered_in_text_is_steered_to_its_trigger(self):
        from rasa.mantle.hooks.exceptions import RetryModel
        self.native.turn = SimpleNamespace(text="Verify me.")
        with self.assertRaises(RetryModel) as raised:
            await policy.keep_host_reply_once(self.payload("How can I assist you today?"))
        self.assertIn("banking_refresh_verification", raised.exception.feedback)
        activation = ModelResponsePayload(sender_id="caller", text=None, tool_calls=[
            {"id": "a", "tool_name": "activate", "tool_args": {"target_id": "banking"}, "type": "function"}])
        self.assertEqual((await policy.keep_host_reply_once(activation)).tool_calls, activation.tool_calls)

    async def test_ordinary_text_and_a_real_host_delivery_are_untouched(self):
        plain = self.payload("Your simulated verification was refreshed. It lasts about a minute.")
        self.assertEqual((await policy.keep_host_reply_once(plain)).text, plain.text)
        policy.remember_delivery()
        self.assertIsNone((await policy.keep_host_reply_once(self.payload("The transfer request was accepted."))).text)


    async def test_a_session_start_pass_speaks_nothing_and_steers_nothing(self):
        for text in ("How can I assist you with your banking accounts today?",
                     "Review: transfer USD 7.00 from DDA-A to savings-A.",
                     "Your simulated verification was refreshed."):
            with self.subTest(text=text):
                self.native.turn = SimpleNamespace(text="Verify me.", trigger="session_start")
                reply = await policy.keep_host_reply_once(self.payload(text))
                self.assertIsNone(reply.text)
                self.assertEqual([c["tool_name"] for c in reply.tool_calls], ["listen"])

    def test_the_retry_note_never_invites_a_new_transfer_after_an_unknown_outcome(self):
        self.assertIn("banking_transfer_status", policy.RETRY_REVIEW)
        self.assertIn("never request a new transfer", policy.RETRY_REVIEW)


if __name__ == "__main__":
    unittest.main()
