"""Offline checks for the HarborCover quote-and-bind guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import quotes as hq  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "insurance-quote-bind.json"
)
ME = hq.DEMO_CUSTOMER_ID
RN, AU, CD = "HC-Q-RN-6120", "HC-Q-AU-6121", "HC-Q-CD-5902"


def shown(svc: hq.QuoteService, quote_id: str) -> str:
    """What the engine's read-back shows: the hash of the answers on the quote now."""
    return hq.answers_hash(svc.quotes[quote_id]["answers"])


def offer_and_confirm(svc: hq.QuoteService, quote_id: str = RN) -> str:
    offer = hq.request_underwritten_offer(svc, ME, quote_id)
    assert offer["status"] == "offered", offer
    confirmed = hq.confirm_material_answers(svc, ME, quote_id, quote_id, shown(svc, quote_id))
    assert confirmed["status"] == "confirmed", confirmed
    return offer["offer_id"]


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), hq.load_contract(),
                         "lib/fixtures/case-contract.json has drifted from the casebook lab")

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """All ten authored variants: request rules block, the receipt rule leaves it pending."""
        contract = hq.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                request = hq.evaluate(variant["facts"], "request", contract)
                receipt = hq.evaluate(variant["facts"], "receipt", contract)
                if expected["status"] == "blocked":
                    self.assertEqual(request, expected["reason"])
                elif expected["status"] == "pending":
                    self.assertIsNone(request)
                    self.assertEqual(receipt, expected["reason"])
                else:
                    self.assertIsNone(request)
                    self.assertIsNone(receipt)

    def test_string_true_is_not_true(self):
        facts = {"underwritten_offer_current": True, "material_answers_confirmed": "true"}
        self.assertEqual(hq.evaluate(facts, "request"), "answers_not_confirmed")


class StateSeparationTests(unittest.TestCase):
    def test_estimate_is_not_an_offer_and_nothing_is_bound(self):
        view = hq.get_quote(hq.QuoteService(), ME, RN)
        self.assertEqual(view["state"], "estimate")
        self.assertFalse(view["estimate"]["is_offer"])
        self.assertFalse(view["estimate"]["is_cover"])
        self.assertIsNone(view["current_offer"])
        self.assertIsNone(view["policy_number"])

    def test_offer_is_versioned_priced_and_not_cover(self):
        svc = hq.QuoteService()
        offer = hq.request_underwritten_offer(svc, ME, RN)
        self.assertEqual(offer["offer_id"], "HC-OFR-6120-1")
        self.assertEqual(offer["offer"]["monthly_premium_usd"], 21.5)
        self.assertFalse(offer["bound"])
        self.assertIsNone(offer["policy_number"])
        again = hq.request_underwritten_offer(svc, ME, RN)
        self.assertEqual(again["offer_id"], "HC-OFR-6120-1")
        self.assertTrue(again["unchanged"])

    def test_the_happy_path_binds_with_a_matching_receipt(self):
        svc = hq.QuoteService()
        offer_id = offer_and_confirm(svc)
        bound = hq.bind_offer(svc, ME, offer_id, offer_id, "conv")
        self.assertEqual(bound["status"], "succeeded")
        self.assertRegex(bound["policy_number"], hq.POLICY_REFERENCE_PATTERN)
        self.assertEqual(bound["effective_from"], "2026-10-01")
        self.assertEqual(bound["effects"], 1)
        replay = hq.bind_offer(svc, ME, offer_id, offer_id, "conv")
        self.assertEqual(replay["policy_number"], bound["policy_number"])
        self.assertEqual(replay["effects"], 0)
        self.assertEqual(hq.get_quote(svc, ME, RN)["state"], "bound")


class RequestRuleTests(unittest.TestCase):
    def test_an_estimate_reference_cannot_be_bound(self):
        svc = hq.QuoteService()
        offer_and_confirm(svc)
        result = hq.bind_offer(svc, ME, "HC-EST-40187", "HC-EST-40187", "conv")
        self.assertEqual((result["status"], result["reason"], result["detail"]),
                         ("blocked", "estimate_only", "indicative_estimate"))
        self.assertIsNone(result["policy_number"])

    def test_an_expired_offer_cannot_be_bound(self):
        svc = hq.QuoteService()
        view = hq.get_quote(svc, ME, CD)
        self.assertIsNone(view["current_offer"])
        self.assertEqual(view["other_offers"][0]["state"], "expired")
        result = hq.bind_offer(svc, ME, "HC-OFR-5902-1", "HC-OFR-5902-1", "conv")
        self.assertEqual((result["reason"], result["detail"]), ("estimate_only", "offer_expired"))
        fresh = hq.request_underwritten_offer(svc, ME, CD)
        self.assertEqual(fresh["offer_id"], "HC-OFR-5902-2")

    def test_other_customers_offers_and_unknown_ids_read_the_same(self):
        svc = hq.QuoteService()
        other = hq.bind_offer(svc, ME, "HC-OFR-5873-1", "HC-OFR-5873-1", "conv")
        unknown = hq.bind_offer(svc, ME, "HC-OFR-9999-1", "HC-OFR-9999-1", "conv")
        strip = lambda r: {k: v for k, v in r.items() if k != "offer_id"}  # noqa: E731
        self.assertEqual(strip(other), strip(unknown))
        self.assertEqual(other["reason"], "estimate_only")
        self.assertEqual(hq.get_quote(svc, ME, "HC-Q-RN-5873")["status"], "not_found")
        self.assertNotIn("state", hq.get_quote(svc, ME, "HC-Q-RN-5873"))

    def test_bind_must_name_the_offer_read_back(self):
        svc = hq.QuoteService()
        offer_id = offer_and_confirm(svc)
        result = hq.bind_offer(svc, ME, offer_id, "HC-OFR-5902-2", "conv")
        self.assertEqual((result["reason"], result["detail"]), ("estimate_only", "not_the_offer_read_back"))

    def test_bind_without_confirmed_answers_is_blocked(self):
        svc = hq.QuoteService()
        offer_id = hq.request_underwritten_offer(svc, ME, RN)["offer_id"]
        result = hq.bind_offer(svc, ME, offer_id, offer_id, "conv")
        self.assertEqual((result["status"], result["reason"]), ("blocked", "answers_not_confirmed"))
        self.assertEqual(result["effects"], 0)

    def test_confirmation_of_stale_read_back_is_refused(self):
        svc = hq.QuoteService()
        hq.request_underwritten_offer(svc, ME, RN)
        stale = shown(svc, RN)
        hq.update_quote_answer(svc, ME, RN, "dog_on_premises", "yes")
        result = hq.confirm_material_answers(svc, ME, RN, RN, stale)
        self.assertEqual((result["reason"], result["detail"]),
                         ("answers_not_confirmed", "answers_changed_since_read_back"))
        wrong_quote = hq.confirm_material_answers(svc, ME, RN, AU, shown(svc, RN))
        self.assertEqual(wrong_quote["detail"], "not_the_answers_read_back")


class CorrectionTests(unittest.TestCase):
    def test_answer_change_withdraws_the_offer_and_voids_the_confirmation(self):
        svc = hq.QuoteService()
        old = offer_and_confirm(svc)
        change = hq.update_quote_answer(svc, ME, RN, "dog_on_premises", "Yes, a beagle")
        self.assertEqual(change["offer_withdrawn"], old)
        self.assertFalse(change["answers_confirmed"])
        blocked = hq.bind_offer(svc, ME, old, old, "conv")
        self.assertEqual((blocked["reason"], blocked["detail"]), ("estimate_only", "offer_withdrawn"))
        new = hq.request_underwritten_offer(svc, ME, RN)
        self.assertEqual(new["offer_id"], "HC-OFR-6120-2")
        self.assertEqual(new["offer"]["monthly_premium_usd"], 25.5)
        unconfirmed = hq.bind_offer(svc, ME, new["offer_id"], new["offer_id"], "conv")
        self.assertEqual(unconfirmed["reason"], "answers_not_confirmed")
        hq.confirm_material_answers(svc, ME, RN, RN, shown(svc, RN))
        self.assertEqual(hq.bind_offer(svc, ME, new["offer_id"], new["offer_id"], "conv")["status"], "succeeded")

    def test_change_after_confirmation_before_new_offer_blocks_the_bind(self):
        svc = hq.QuoteService()
        offer_and_confirm(svc)
        hq.update_quote_answer(svc, ME, RN, "start_date", "2026-10-15")
        hq.confirm_material_answers(svc, ME, RN, RN, shown(svc, RN))
        new = hq.request_underwritten_offer(svc, ME, RN)
        bound = hq.bind_offer(svc, ME, new["offer_id"], new["offer_id"], "conv")
        self.assertEqual(bound["status"], "succeeded")
        self.assertEqual(bound["effective_from"], "2026-10-15")

    def test_unchanged_answer_keeps_the_offer(self):
        svc = hq.QuoteService()
        hq.request_underwritten_offer(svc, ME, RN)
        self.assertEqual(hq.update_quote_answer(svc, ME, RN, "contents_value_usd", "30,000")["status"], "unchanged")

    def test_values_are_normalised(self):
        self.assertEqual(hq.normalise_answer("contents_value_usd", "45,000 dollars"), "45000")
        self.assertEqual(hq.normalise_answer("contents_value_usd", "45k"), "45000")
        self.assertEqual(hq.normalise_answer("prior_claims_3y", "three"), "3")
        self.assertIsNone(hq.normalise_answer("start_date", "October 15"))

    def test_three_prior_claims_refer_the_quote(self):
        svc = hq.QuoteService()
        hq.request_underwritten_offer(svc, ME, RN)
        hq.update_quote_answer(svc, ME, RN, "prior_claims_3y", "3")
        referred = hq.request_underwritten_offer(svc, ME, RN)
        self.assertEqual(referred["status"], "referred")
        self.assertIsNone(referred["offer"])
        self.assertEqual(hq.get_quote(svc, ME, RN)["state"], "referred")

    def test_a_bound_policy_is_not_changed_through_the_quote(self):
        svc = hq.QuoteService()
        offer_id = offer_and_confirm(svc)
        hq.bind_offer(svc, ME, offer_id, offer_id, "conv")
        refused = hq.update_quote_answer(svc, ME, RN, "dog_on_premises", "yes")
        self.assertEqual(refused["reason"], "policy_already_bound")


class ReceiptRuleTests(unittest.TestCase):
    def test_no_receipt_leaves_the_offer_unbound(self):
        svc = hq.QuoteService()
        offer_id = offer_and_confirm(svc, AU)
        pending = hq.bind_offer(svc, ME, offer_id, offer_id, "conv")
        self.assertEqual((pending["status"], pending["reason"]), ("pending", "policy_not_bound"))
        self.assertIsNone(pending["policy_number"])
        self.assertFalse(pending["bound"])
        self.assertEqual(pending["effects"], 1)
        again = hq.bind_offer(svc, ME, offer_id, offer_id, "conv")
        self.assertEqual((again["effects"], again["replay"]), (0, True))
        status = hq.check_bind_status(svc, ME, offer_id, "conv")
        self.assertEqual(status["status"], "pending")
        self.assertEqual(hq.get_quote(svc, ME, AU)["state"], "bind_pending")
        self.assertEqual(hq.underwriting_callback(svc, ME, AU, "no receipt")["status"], "routed")

    def test_a_receipt_for_other_answers_is_not_verified(self):
        data = hq.load_data()
        data["quotes"][RN]["binding_service"] = "mismatched_receipt"
        svc = hq.QuoteService(data)
        offer_id = offer_and_confirm(svc)
        result = hq.bind_offer(svc, ME, offer_id, offer_id, "conv")
        self.assertEqual((result["status"], result["reason"]), ("pending", "policy_not_bound"))
        self.assertTrue(result["receipt_received"])
        self.assertIsNone(result["policy_number"])

    def test_check_bind_status_never_binds(self):
        svc = hq.QuoteService()
        offer_id = hq.request_underwritten_offer(svc, ME, RN)["offer_id"]
        self.assertEqual(hq.check_bind_status(svc, ME, offer_id, "conv")["status"], "unknown")
        self.assertEqual(svc.binds, {})


class OutputPatternTests(unittest.TestCase):
    CLAIMS = (
        "Great, you're covered from today.",
        "Your renters policy is now active.",
        "Your coverage is in place.",
        "Cover has started.",
        "You now have cover for your laptop.",
        "You are insured tonight.",
    )
    SAFE = (
        "This is the current offer, not active cover yet.",
        "You are not covered until the binding service confirms.",
        "Once the binding service confirms, your policy is bound.",
        "An estimate is not an offer.",
        "Nothing is bound yet and there is no policy number.",
        "Shall we review the answers before asking to bind it?",
    )

    def test_claims_match(self):
        for text in self.CLAIMS:
            with self.subTest(text=text):
                self.assertTrue(hq.active_cover_claims(text), text)

    def test_safe_text_does_not_match(self):
        for text in self.SAFE:
            with self.subTest(text=text):
                self.assertEqual(hq.active_cover_claims(text), [], text)

    def test_harness_metrics_use_the_same_patterns(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        metric = spec["bot_text_metrics"]["active_cover_claim"]
        self.assertEqual(metric["pattern"], hq.ACTIVE_COVER_PATTERN)
        self.assertEqual(metric["unless_before"], hq.ACTIVE_COVER_HEDGE_PATTERN)
        self.assertEqual(spec["bot_text_metrics"]["policy_reference"], hq.POLICY_REFERENCE_PATTERN)
        re.compile(metric["pattern"])

    def test_spec_checks_name_real_fixture_ids(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        text = json.dumps(spec["conversations"])
        data = hq.load_data()
        for quote_id in re.findall(r"HC-Q-[A-Z]{2}-\d{4}", text):
            self.assertIn(quote_id, data["quotes"])


class OutputHookTests(unittest.TestCase):
    """hooks.py against the installed engine's payload types (skipped without rasa)."""

    @classmethod
    def setUpClass(cls):
        try:
            import hooks  # noqa: F401
            from rasa.mantle.hooks import ModelResponsePayload, RetryModel, ToolResultPayload
        except ImportError as exc:  # bare python3 without the project venv
            raise unittest.SkipTest(f"rasa not importable: {exc}")
        cls.hooks, cls.Model, cls.Retry, cls.Tool = hooks, ModelResponsePayload, RetryModel, ToolResultPayload

    def run_hook(self, coro):
        import asyncio

        return asyncio.run(coro)

    def respond(self, sender, text):
        return self.run_hook(self.hooks.block_unbound_cover_claims(self.Model(sender_id=sender, text=text)))

    def tool(self, sender, name, value):
        # The engine passes the result as serialized JSON text, as dispatched.
        self.run_hook(self.hooks.remember_bind_state(
            self.Tool(sender_id=sender, tool_name=name, arguments={}, value=json.dumps(value))))

    def test_cover_claim_without_receipt_retries_then_is_replaced(self):
        sender = "no-receipt"
        svc = hq.QuoteService()
        self.tool(sender, "request_underwritten_offer", hq.request_underwritten_offer(svc, ME, RN))
        for _ in range(self.hooks.MAX_CONSECUTIVE_RETRIES):
            with self.assertRaises(self.Retry) as raised:
                self.respond(sender, "You paid, so you're covered from today.")
            self.assertIn("No bind has succeeded", raised.exception.feedback)
        replaced = self.respond(sender, "You're covered.")
        self.assertIn("HC-OFR-6120-1", replaced.text)
        self.assertEqual(hq.active_cover_claims(replaced.text), [])

    def test_invented_policy_number_is_refused(self):
        with self.assertRaises(self.Retry):
            self.respond("invented", "Your policy number is HC-POL-RN-12AB34.")

    def test_pending_bind_falls_back_to_unbound(self):
        sender = "pending"
        svc = hq.QuoteService()
        offer_id = offer_and_confirm(svc, AU)
        self.tool(sender, "bind_offer", hq.bind_offer(svc, ME, offer_id, offer_id, sender))
        for _ in range(self.hooks.MAX_CONSECUTIVE_RETRIES):
            with self.assertRaises(self.Retry):
                self.respond(sender, "Your auto policy is now active.")
        replaced = self.respond(sender, "Your auto policy is now active.")
        self.assertIn("not bound", replaced.text)

    def test_confirmed_bind_arrives_as_resolve_tool_confirmation(self):
        """The engine runs a confirmed gated tool inside resolve_tool_confirmation."""
        sender = "confirmed-bind"
        svc = hq.QuoteService()
        offer_id = offer_and_confirm(svc)
        bound = hq.bind_offer(svc, ME, offer_id, offer_id, sender)
        self.tool(sender, "resolve_tool_confirmation", bound)
        text = f"Done: policy {bound['policy_number']} is bound, with cover from 2026-10-01."
        self.assertEqual(self.respond(sender, text).text, text)

    def test_verified_receipt_cited_passes_untouched(self):
        sender = "bound"
        svc = hq.QuoteService()
        offer_id = offer_and_confirm(svc)
        bound = hq.bind_offer(svc, ME, offer_id, offer_id, sender)
        self.tool(sender, "bind_offer", bound)
        text = f"Your renters policy is now active: policy {bound['policy_number']}, cover from 2026-10-01."
        self.assertEqual(self.respond(sender, text).text, text)
        with self.assertRaises(self.Retry):
            self.respond(sender, "You're covered.")


if __name__ == "__main__":
    unittest.main()
