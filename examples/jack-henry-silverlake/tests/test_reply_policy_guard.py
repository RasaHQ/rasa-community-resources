"""The reply hook never lets model text announce a review or acceptance the host did not deliver."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib import reply_policy as policy
from rasa.mantle.hooks.payloads import ModelResponsePayload


class HostOnlyWording(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        policy._delivered.clear()
        self.native = SimpleNamespace(sender_id="caller", turn=object(), is_cancelled=False)
        p = patch.object(policy, "current_turn_context", return_value=self.native)
        p.start(); self.addCleanup(p.stop); self.addCleanup(policy._delivered.clear)

    def payload(self, text):
        return ModelResponsePayload(sender_id="caller", text=text, tool_calls=[])

    async def test_imitated_review_or_acceptance_is_replaced(self):
        for text in ("Review: transfer USD 7.00 from checking-A to savings-A. Say confirm transfer next.",
                     "The transfer request was accepted. Accepted does not mean posted."):
            with self.subTest(text=text):
                self.assertEqual((await policy.keep_host_reply_once(self.payload(text))).text, policy.NO_TRANSFER_TEXT)

    async def test_ordinary_text_and_a_real_host_delivery_are_untouched(self):
        plain = self.payload("Your simulated verification was refreshed. It lasts about a minute.")
        self.assertEqual((await policy.keep_host_reply_once(plain)).text, plain.text)
        policy.remember_delivery()
        self.assertIsNone((await policy.keep_host_reply_once(self.payload("The transfer request was accepted."))).text)


if __name__ == "__main__":
    unittest.main()
