"""Characterisation of the status lookup after an unresolved bind. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -p "test_status*" -v
(or all offline tests: python -m unittest discover -s tests -v)

This records what the fixture does TODAY. It is not a specification of how a status lookup should behave:
if the lookup is later changed to say that a receipt arrived, these assertions change with it, and so does
any review worksheet that cites them.

The two unresolved binds share one lookup answer. The first reply tells them apart (receipt_received), the
saved service record tells them apart (a receipt for older answers carries a policy number), the later
lookup does not.
"""

from __future__ import annotations

import unittest

import test_guard as guard
from test_guard import hq


def unresolved(quote_id: str, binding_service: str | None):
    data = hq.load_data()
    if binding_service:
        data["quotes"][quote_id]["binding_service"] = binding_service
    svc = hq.QuoteService(data)
    offer_id = guard.offer_and_confirm(svc, quote_id)
    first = hq.bind_offer(svc, guard.ME, offer_id, offer_id, "conv")
    return svc, offer_id, first


class StatusLookupCharacterisation(unittest.TestCase):
    def test_a_receipt_for_older_answers_is_saved_with_a_policy_number_but_not_exposed(self):
        svc, offer_id, first = unresolved(guard.RN, "mismatched_receipt")
        self.assertEqual((first["status"], first["reason"]), ("pending", "policy_not_bound"))
        self.assertIs(first["receipt_received"], True)
        self.assertIsNone(first["policy_number"])
        self.assertIs(first["bound"], False)
        saved = svc.binds[f"conv:{offer_id}"]["receipt"]
        self.assertTrue(saved["policy_number"].startswith("HC-POL-"))
        self.assertNotEqual(saved["answers_hash"], svc.offers[offer_id]["answers_hash"])

    def test_the_later_lookup_after_that_receipt_does_not_say_a_receipt_arrived(self):
        svc, offer_id, _ = unresolved(guard.RN, "mismatched_receipt")
        binds_before = len(svc.binds)
        lookup = hq.check_bind_status(svc, guard.ME, offer_id, "conv")
        self.assertEqual((lookup["status"], lookup["reason"]), ("pending", "policy_not_bound"))
        self.assertNotIn("receipt_received", lookup)
        self.assertIn("Still no binding receipt", lookup["next_step"])
        self.assertIsNone(lookup["policy_number"])
        self.assertIs(lookup["bound"], False)
        self.assertEqual(len(svc.binds), binds_before, "a lookup must not create a bind request")

    def test_the_lookup_is_the_same_for_a_missing_receipt_and_a_receipt_for_older_answers(self):
        missing_svc, missing_id, missing_first = unresolved(guard.AU, None)
        older_svc, older_id, older_first = unresolved(guard.RN, "mismatched_receipt")
        self.assertIs(missing_first["receipt_received"], False)
        self.assertIs(older_first["receipt_received"], True)

        def without_offer_id(lookup):
            return {key: value for key, value in lookup.items() if key != "offer_id"}

        missing = without_offer_id(hq.check_bind_status(missing_svc, guard.ME, missing_id, "conv"))
        older = without_offer_id(hq.check_bind_status(older_svc, guard.ME, older_id, "conv"))
        self.assertEqual(missing, older)


if __name__ == "__main__":
    unittest.main()
