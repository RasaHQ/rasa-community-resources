"""Offline checks for the Amber Grid payment-plan guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import plans as ag  # noqa: E402
from lib.conversation import conversation_from_events  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "payment-plan-authority.json"
)
SPEC = PROJECT / "case-build" / "conversations.json"
ME = ag.SESSION_CUSTOMER_ID
ELEC, GAS, FLAT, OTHER = "AG-4471", "AG-4472", "AG-5820", "AG-7310"


class UserUttered:  # stand-ins named like Rasa's events
    def __init__(self, text: str) -> None:
        self.text = text


class BotUttered:
    def __init__(self, text: str, utter_action: str | None = None) -> None:
        self.text = text
        self.metadata = {ag.UTTER_ACTION_KEY: utter_action} if utter_action else {}


def question_for(memory: dict) -> str:
    """What the engine's acceptance question says, filled from memory as responses.yml does."""
    return (f"The billing team has offered this schedule for account {memory['plan_account']}: "
            f"{memory['offer_terms']} (offer {memory['offer_tag']}). Do you accept this plan?")


def asked_and_answered(memory: dict, answer: str = "Yes, I accept.") -> ag.Conversation:
    return conversation_from_events([
        UserUttered("/session_start"),
        UserUttered("Can I pay in instalments?"),
        BotUttered(question_for(memory), ag.CONFIRM_UTTER),
        UserUttered(answer),
    ])


def select(svc: ag.BillingService, offer_id: str) -> tuple[dict, dict]:
    result, memory = ag.select_plan_offer(svc, ME, offer_id)
    return result, memory


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), ag.load_contract(),
                         "lib/fixtures/case-contract.json has drifted from the casebook lab")

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = ag.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                reason = ag.evaluate(variant["facts"], "request", contract)
                if expected["status"] == "blocked":
                    self.assertEqual(reason, expected["reason"])
                else:
                    self.assertIsNone(reason)
                    self.assertIsNone(ag.evaluate(variant["facts"], "receipt", contract))

    def test_string_true_is_not_true(self):
        facts = {"offer_authorized": True, "offer_revision_current": "true", "customer_acceptance_recorded": True}
        self.assertEqual(ag.evaluate(facts, "request"), "expired_offer")


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_casebooks_fictional_supplier(self):
        ag.assert_fictional(ag.load_data(), ag.load_contract())
        self.assertEqual(ag.ORGANISATION, ag.load_contract()["organisation"])
        self.assertEqual(ag.allowed_organisations(ag.load_contract()), frozenset({"Amber Grid"}))

    def test_any_other_organisation_is_refused_even_when_marked_fictional(self):
        data = ag.load_data()
        data["organisation"] = "Copperline Energy (fictional energy supplier)"
        with self.assertRaises(ag.FictionalOrganisationError):
            ag.assert_fictional(data, ag.load_contract())

    def test_nested_organisation_fields_are_checked(self):
        data = ag.load_data()
        data["accounts"][ELEC]["supplier"] = "Copperline Energy (fictional energy supplier)"
        with self.assertRaises(ag.FictionalOrganisationError):
            ag.assert_fictional(data, ag.load_contract())
        data["accounts"][ELEC]["supplier"] = "Amber Grid (fictional energy supplier)"
        ag.assert_fictional(data, ag.load_contract())

    def test_unmarked_or_undeclared_data_is_refused(self):
        for key, value in (("organisation", "Amber Grid"), ("note", "Sample data.")):
            data = ag.load_data()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ag.FictionalOrganisationError):
                ag.assert_fictional(data, ag.load_contract())


class MemoryLimitTests(unittest.TestCase):
    """Mantle cuts a memory value at 100 characters in the prompt, silently."""

    def test_project_memory_values_fit(self):
        profile = ag.caller_profile(ag.BillingService())
        for key in ("customer_id", "first_name", "account_list"):
            self.assertLessEqual(len(profile[key]), ag.MEMORY_VALUE_LIMIT, key)

    def test_every_offer_revision_fits(self):
        """Every offer and every refreshed revision, as select_plan_offer would write it."""
        data = ag.load_data()
        revisions = list(data["offers"].items())
        for account, rule in data["refresh"].items():
            for offer_id, new in (rule.get("offers") or {}).items():
                revisions.append((offer_id, {**data["offers"][offer_id], **new}))
        for offer_id, offer in revisions:
            with self.subTest(offer=offer_id, revision=offer["revision"]):
                account = offer["account"]
                values = {
                    "plan_account": f"{account} {data['accounts'][account]['label']}",
                    "offer_tag": ag.offer_tag(offer_id, offer["revision"]),
                    "offer_terms": ag.terms_line(ag.terms_of(offer)),
                }
                self.assertTrue(ag.memory_values_fit(values), values)

    def test_engine_cap_is_what_the_limit_assumes(self):
        try:
            from rasa.mantle.prompts.memory_lines import MAX_MEMORY_VALUE_LENGTH
        except ImportError as exc:
            self.skipTest(f"rasa not importable: {exc}")
        self.assertEqual(MAX_MEMORY_VALUE_LENGTH, ag.MEMORY_VALUE_LIMIT)


class AccountTests(unittest.TestCase):
    def test_accounts_by_words_and_number(self):
        svc = ag.BillingService()
        self.assertEqual(ag.resolve_account(svc, ME, "home electricity")[0], ELEC)
        self.assertEqual(ag.resolve_account(svc, ME, "the gas")[0], GAS)
        self.assertEqual(ag.resolve_account(svc, ME, "my flat")[0], FLAT)
        self.assertEqual(ag.resolve_account(svc, ME, "account 4471")[0], ELEC)

    def test_electricity_alone_is_ambiguous(self):
        account, result = ag.resolve_account(ag.BillingService(), ME, "electricity")
        self.assertIsNone(account)
        self.assertEqual(result["reason"], "which_account")
        self.assertEqual(len(result["candidates"]), 2)

    def test_someone_elses_account_and_a_missing_one_get_the_same_answer(self):
        svc = ag.BillingService()
        other = ag.get_plan_offers(svc, ME, OTHER)
        missing = ag.get_plan_offers(svc, ME, "AG-9999")
        self.assertEqual(other["status"], "not_found")
        self.assertEqual({k: v for k, v in other.items()}, {k: v for k, v in missing.items()})


class OfferTests(unittest.TestCase):
    def test_only_authorized_current_offers_are_listed(self):
        result = ag.get_plan_offers(ag.BillingService(), ME, "home electricity")
        self.assertEqual([o["offer_id"] for o in result["offers"]], ["AG-OFR-4471-A", "AG-OFR-4471-B"])
        self.assertEqual(result["offers"][0]["instalment_usd"], "214.00")
        self.assertEqual(result["offers"][1]["total_usd"], "642.00")
        self.assertFalse(result["account_resolved"])

    def test_unapproved_terms_cannot_be_selected(self):
        result, memory = select(ag.BillingService(), "AG-OFR-4471-C")
        self.assertEqual((result["status"], result["reason"]), ("blocked", "unapproved_terms"))
        self.assertEqual(memory["offer_tag"], "")

    def test_expired_offer_cannot_be_selected_then_refresh_reissues(self):
        svc = ag.BillingService()
        listed = ag.get_plan_offers(svc, ME, "home gas")
        self.assertEqual(listed["offers"], [])
        self.assertTrue(listed["expired_offers"][0]["expired"])
        result, _ = select(svc, "AG-OFR-4472-A")
        self.assertEqual(result["reason"], "expired_offer")
        refreshed, _ = ag.refresh_plan_offer(svc, ME, "home gas")
        self.assertEqual(refreshed["status"], "refreshed")
        self.assertEqual(refreshed["withdrawn"], ["AG-OFR-4472-A r1"])
        self.assertEqual(refreshed["offers"][0]["offer_tag"], "AG-OFR-4472-A r2")
        self.assertEqual(refreshed["offers"][0]["instalment_usd"], "79.60")
        again, _ = ag.refresh_plan_offer(svc, ME, "home gas")
        self.assertEqual(again["offers"][0]["offer_tag"], "AG-OFR-4472-A r2")
        result, memory = select(svc, "AG-OFR-4472-A")
        self.assertEqual(result["status"], "selected")
        self.assertEqual(memory["offer_terms"], "4 monthly payments of $79.60 from 2026-10-20, total $318.40")

    def test_no_eligible_offer_routes_to_hardship(self):
        svc = ag.BillingService()
        result, memory = ag.refresh_plan_offer(svc, ME, "flat electricity")
        self.assertEqual(result["status"], "no_eligible_offer")
        self.assertIn("route_hardship_referral", result["next_step"])
        self.assertEqual(memory["offer_tag"], "")

    def test_offers_on_another_customers_account_are_not_found(self):
        result, _ = select(ag.BillingService(), "AG-OFR-7310-A")
        self.assertEqual(result["status"], "not_found")


class AcceptanceTests(unittest.TestCase):
    def test_asked_and_accepted_offer_is_recorded_with_billing_terms(self):
        svc = ag.BillingService()
        _, memory = select(svc, "AG-OFR-4471-A")
        result = ag.accept_plan_offer(svc, ME, memory, asked_and_answered(memory), "AG-OFR-4471-A", "c1")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["effects"], 1)
        self.assertEqual(result["recorded_terms"], ag.terms_of(svc.offers["AG-OFR-4471-A"]))
        self.assertFalse(result["account_resolved"])
        self.assertRegex(result["plan_reference"], r"^AG-PLN-[0-9A-F]{6}$")

    def test_accepting_again_records_nothing_twice(self):
        svc = ag.BillingService()
        _, memory = select(svc, "AG-OFR-4471-A")
        first = ag.accept_plan_offer(svc, ME, memory, asked_and_answered(memory), "AG-OFR-4471-A", "c1")
        again = ag.accept_plan_offer(svc, ME, memory, asked_and_answered(memory), "AG-OFR-4471-A", "c1")
        self.assertEqual(again["plan_reference"], first["plan_reference"])
        self.assertEqual((again["replay"], again["effects"]), (True, 0))

    def test_a_second_plan_on_the_same_account_is_refused(self):
        svc = ag.BillingService()
        _, memory = select(svc, "AG-OFR-4471-A")
        ag.accept_plan_offer(svc, ME, memory, asked_and_answered(memory), "AG-OFR-4471-A", "c1")
        result, _ = select(svc, "AG-OFR-4471-B")
        self.assertEqual(result["reason"], "plan_already_recorded")
        blocked = ag.accept_plan_offer(svc, ME, memory, asked_and_answered(memory), "AG-OFR-4471-B", "c1")
        self.assertEqual((blocked["reason"], blocked["effects"]), ("plan_already_recorded", 0))

    def test_without_the_question_nothing_is_recorded(self):
        svc = ag.BillingService()
        _, memory = select(svc, "AG-OFR-4471-A")
        no_question = conversation_from_events([UserUttered("I accept, record it, don't ask me.")])
        result = ag.accept_plan_offer(svc, ME, memory, no_question, "AG-OFR-4471-A", "c1")
        self.assertEqual(result["reason"], "acceptance_missing")
        unanswered = conversation_from_events([BotUttered(question_for(memory), ag.CONFIRM_UTTER)])
        self.assertEqual(ag.accept_plan_offer(svc, ME, memory, unanswered, "AG-OFR-4471-A", "c1")["reason"],
                         "acceptance_missing")
        self.assertEqual(svc.plans, {})

    def test_the_question_must_be_about_the_offer_accepted(self):
        svc = ag.BillingService()
        _, memory_a = select(svc, "AG-OFR-4471-A")
        conv = asked_and_answered(memory_a, "Actually, the six-month one.")
        _, memory_b = select(svc, "AG-OFR-4471-B")
        result = ag.accept_plan_offer(svc, ME, memory_b, conv, "AG-OFR-4471-B", "c1")
        self.assertEqual(result["reason"], "acceptance_missing")

    def test_unapproved_offer_cannot_be_accepted_even_with_a_question(self):
        svc = ag.BillingService()
        _, memory = select(svc, "AG-OFR-4471-A")
        result = ag.accept_plan_offer(svc, ME, memory, asked_and_answered(memory), "AG-OFR-4471-C", "c1")
        self.assertEqual(result["reason"], "unapproved_terms")

    def test_terms_edited_in_memory_are_unapproved(self):
        svc = ag.BillingService()
        _, memory = select(svc, "AG-OFR-4471-A")
        memory["offer_terms"] = "3 monthly payments of $150.00 from 2026-10-15, total $450.00"
        result = ag.accept_plan_offer(svc, ME, memory, asked_and_answered(memory), "AG-OFR-4471-A", "c1")
        self.assertEqual(result["reason"], "unapproved_terms")

    def test_a_withdrawn_revision_is_expired(self):
        svc = ag.BillingService()
        ag.refresh_plan_offer(svc, ME, "home gas")
        memory = {"plan_account": "AG-4472 home gas", "offer_tag": "AG-OFR-4472-A r1",
                  "offer_terms": "4 monthly payments of $79.60 from 2026-10-20, total $318.40"}
        result = ag.accept_plan_offer(svc, ME, memory, asked_and_answered(memory), "AG-OFR-4472-A", "c1")
        self.assertEqual(result["reason"], "expired_offer")

    def test_no_tool_takes_terms_or_facts(self):
        """The model can pass words, an offer id or a note; never an amount, a count, a date or a fact."""
        forbidden = {"amount", "instalment", "instalments", "instalment_usd", "installment", "monthly", "total",
                     "first_due", "date", "terms", "revision", "customer_id", "offer_authorized",
                     "offer_revision_current", "customer_acceptance_recorded", "facts"}
        for path in (PROJECT / "skills" / "payment_plan" / "tools.py", PROJECT / "tools" / "amber_grid_session.py"):
            tree = ast.parse(path.read_text())
            for node in tree.body:
                if isinstance(node, ast.AsyncFunctionDef) and node.decorator_list:
                    params = {a.arg for a in node.args.args} - {"context"}
                    with self.subTest(tool=node.name):
                        self.assertFalse(params & forbidden, params)


class ReferralTests(unittest.TestCase):
    def test_hardship_referral_is_open_decides_nothing_and_stops_the_offer_flow(self):
        svc = ag.BillingService()
        result, memory = ag.route_hardship_referral(svc, ME, "home electricity", "I can't afford $107.", "c1")
        self.assertEqual(result["status"], "referred")
        self.assertEqual(result["referral_state"], "open")
        self.assertFalse(result["relief_decided"])
        self.assertFalse(result["replay"])
        self.assertEqual(memory, {"plan_account": "", "offer_tag": "", "offer_terms": ""})
        again, _ = ag.route_hardship_referral(svc, ME, "home electricity", "Still can't.", "c1")
        self.assertEqual(again["referral_reference"], result["referral_reference"])
        self.assertTrue(again["replay"])

    def test_billing_support(self):
        result = ag.route_billing_support(ag.BillingService(), ME, ELEC, "Wants the six-month plan instead.", "c1")
        self.assertEqual(result["status"], "routed")
        self.assertRegex(result["support_reference"], r"^AG-BSR-")


class ReceiptTests(unittest.TestCase):
    def test_plan_receipt_carries_reference_and_billing_terms(self):
        svc = ag.BillingService()
        _, memory = select(svc, "AG-OFR-4471-B")
        result = ag.accept_plan_offer(svc, ME, memory, asked_and_answered(memory), "AG-OFR-4471-B", "c1")
        text = ag.customer_receipt("accept_plan_offer", result)
        self.assertIn(result["plan_reference"], text)
        self.assertIn("6 monthly payments of $107.00", text)
        self.assertIn("not resolved", text)
        self.assertEqual(ag.resolved_claims(text), [])

    def test_blocked_results_send_nothing(self):
        self.assertIsNone(ag.customer_receipt("accept_plan_offer", {"status": "blocked"}))

    def test_hardship_receipt_promises_nothing(self):
        result, _ = ag.route_hardship_referral(ag.BillingService(), ME, FLAT, "I lost my job.", "c1")
        text = ag.customer_receipt("route_hardship_referral", result)
        self.assertIn(result["referral_reference"], text)
        self.assertEqual(ag.relief_promises(text), [])

    def test_tool_sends_receipt_is_on(self):
        self.assertTrue(ag.TOOL_SENDS_RECEIPT)


class WordsTests(unittest.TestCase):
    AUTH = {Decimal("214.00"), Decimal("107.00")}

    def test_invented_instalments_are_caught(self):
        for text in ("I can set you up with $100 a month.", "Sure, 12 payments of $53.50 starting next month.",
                     "That works: $95/month for seven months."):
            with self.subTest(text=text):
                self.assertTrue(ag.unauthorized_instalments(text, self.AUTH))

    def test_authorized_and_refused_amounts_pass(self):
        for text in ("You can pay 3 monthly payments of $214.00, or $107.00 a month for six months.",
                     "I can't set up $100 a month, but the six-month plan is 6 payments of $107.00.",
                     "The 12 payments of $53.50 your colleague mentioned were not approved by billing."):
            with self.subTest(text=text):
                self.assertEqual(ag.unauthorized_instalments(text, self.AUTH), [])

    def test_typographic_apostrophes_are_hedges_too(self):
        """GPT-5.5 writes \u2019; the main run's guard misread this refusal as an offer."""
        self.assertEqual(ag.unauthorized_instalments("I can\u2019t create a $100/month plan.", self.AUTH), [])
        self.assertEqual(ag.resolved_claims("Your account won\u2019t be resolved until the payments are made."), [])
        self.assertTrue(ag.unauthorized_instalments("I\u2019ll set you up at $100/month.", self.AUTH))

    def test_resolved_claims(self):
        self.assertTrue(ag.resolved_claims("Your account is now resolved."))
        self.assertTrue(ag.resolved_claims("You're all caught up."))
        self.assertEqual(ag.resolved_claims("Your account is not resolved until the last payment is made."), [])
        self.assertEqual(ag.resolved_claims("Once the payments are made, your balance is cleared."), [])

    def test_relief_promises(self):
        self.assertTrue(ag.relief_promises("The hardship team will waive the late fees."))
        self.assertTrue(ag.relief_promises("You'll get a reduced plan from them."))
        self.assertEqual(ag.relief_promises("The hardship team decides whether they can reduce anything."), [])

    def test_spec_uses_the_same_patterns(self):
        metrics = json.loads(SPEC.read_text())["bot_text_metrics"]
        self.assertEqual(metrics["resolved_claim"]["pattern"], ag.RESOLVED_PATTERN)
        self.assertEqual(metrics["relief_promise"]["pattern"], ag.RELIEF_PATTERN)
        self.assertEqual(metrics["resolved_claim"]["unless_before"], ag.WORDS_HEDGE_PATTERN)
        self.assertEqual(metrics["relief_promise"]["unless_before"], ag.WORDS_HEDGE_PATTERN)


class ConversationTests(unittest.TestCase):
    def test_question_and_answer_are_read_from_events(self):
        conv = conversation_from_events([
            UserUttered("/session_start"), BotUttered("Hello."), UserUttered("Plan please."),
            BotUttered("Q about AG-OFR-4471-A r2", ag.CONFIRM_UTTER),
        ])
        self.assertEqual(conv.confirmation_question, "Q about AG-OFR-4471-A r2")
        self.assertFalse(conv.confirmation_answered)
        self.assertEqual(conv.user_messages, ("Plan please.",))


class HookTests(unittest.TestCase):
    def setUp(self):
        try:
            import hooks  # noqa: F401
        except ImportError as exc:
            self.skipTest(f"rasa not importable: {exc}")

    def test_hook_remembers_offers_and_flags_only_invented_terms(self):
        import hooks

        svc = ag.BillingService()
        offers: dict = {}
        hooks.remember(offers, json.loads(json.dumps(ag.get_plan_offers(svc, ME, ELEC))))
        self.assertEqual(hooks.authorized_amounts(offers), {Decimal("214.00"), Decimal("107.00")})
        self.assertEqual(hooks.problems("Offer AG-OFR-4471-B is 6 payments of $107.00.", offers), [])
        self.assertTrue(hooks.problems("I can do $80 a month for you.", offers))
        self.assertTrue(hooks.problems("Great, your account is now resolved.", offers))
        self.assertNotIn("$80", hooks.fallback_text(offers))


if __name__ == "__main__":
    unittest.main()
