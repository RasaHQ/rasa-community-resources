"""Offline checks for the Amber Grid budget-plan guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
The output-hook tests need Rasa and skip without it (``make proof-full`` runs them).
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import budget as ag  # noqa: E402
from lib.conversation import conversation_from_events  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "utilities-budget-plan.json"
)
SPEC = PROJECT / "case-build" / "conversations.json"
ME = ag.SESSION_CUSTOMER_ID
ELEC, GAS, STUDIO, OTHER = "AG-6120", "AG-6121", "AG-6125", "AG-6388"


class UserUttered:  # stand-ins named like Rasa's events
    def __init__(self, text: str) -> None:
        self.text = text


class BotUttered:
    def __init__(self, text: str, utter_action: str | None = None) -> None:
        self.text = text
        self.metadata = {ag.UTTER_ACTION_KEY: utter_action} if utter_action else {}


def question_template() -> str:
    """The engine's confirmation question, as skills/budget_plan/responses.yml folds it."""
    lines = (PROJECT / "skills" / "budget_plan" / "responses.yml").read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "- text: >")
    body = []
    for line in lines[start + 1:]:
        if not line.startswith("        "):
            break
        body.append(line.strip())
    return " ".join(body)


def question_for(memory: dict) -> str:
    return question_template().format(**memory)


def asked_and_answered(memory: dict, answer: str = "Yes, please request it.") -> ag.Conversation:
    return conversation_from_events([
        UserUttered("/session_start"),
        UserUttered("Can I go on a budget plan?"),
        BotUttered(question_for(memory), ag.CONFIRM_UTTER),
        UserUttered(answer),
    ])


def select_and_request(svc: ag.BillingService, option_id: str, conversation_id: str = "t") -> tuple[dict, dict]:
    selected, memory = ag.select_budget_option(svc, ME, option_id)
    assert selected["status"] == "selected", selected
    result, _ = ag.request_budget_option(svc, ME, memory, asked_and_answered(memory), option_id, conversation_id)
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
                request = ag.evaluate(variant["facts"], "request", contract)
                receipt = ag.evaluate(variant["facts"], "receipt", contract)
                if expected["status"] == "blocked":
                    self.assertEqual(request, expected["reason"])
                elif expected["status"] == "pending":
                    self.assertIsNone(request)
                    self.assertEqual(receipt, expected["reason"])
                else:
                    self.assertIsNone(request)
                    self.assertIsNone(receipt)

    def test_string_true_is_not_true(self):
        facts = {"billing_basis_explained": True, "support_option_authorized": "true"}
        self.assertEqual(ag.evaluate(facts, "request"), "unapproved_relief")

    def test_question_carries_the_contracts_words(self):
        contract = ag.load_contract()
        first = contract["question"].split("?")[0].split(". ")[0] + "."
        self.assertIn(first, question_template())
        for key in ag.MEMORY_KEYS:
            self.assertIn("{" + key + "}", question_template())

    def test_denial_response_is_left_unset(self):
        skill = (PROJECT / "skills" / "budget_plan" / "skill.md").read_text()
        self.assertNotIn("utter_on_user_denial", skill)


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
        data["accounts"][ELEC]["supplier"] = "Some Other Utility (fictional)"
        with self.assertRaises(ag.FictionalOrganisationError):
            ag.assert_fictional(data, ag.load_contract())

    def test_unmarked_organisation_is_refused(self):
        data = ag.load_data()
        data["organisation"] = "Amber Grid"
        with self.assertRaises(ag.FictionalOrganisationError):
            ag.assert_fictional(data, ag.load_contract())

    def test_note_must_say_fictional(self):
        data = ag.load_data()
        data["note"] = "Billing data."
        with self.assertRaises(ag.FictionalOrganisationError):
            ag.assert_fictional(data, ag.load_contract())


class FixtureTests(unittest.TestCase):
    def test_budget_amounts_are_the_estimate_over_twelve_and_spreads_repay_the_balance(self):
        data = ag.load_data()
        for account, quote in data["quotes"].items():
            balance = Decimal(data["accounts"][account]["outstanding_balance_usd"])
            for rev, body in quote["revisions"].items():
                annual = Decimal(body["basis"]["annual_cost_usd"])
                for oid, opt in body["options"].items():
                    with self.subTest(option=f"{oid} r{rev}"):
                        self.assertEqual(Decimal(opt["budget_usd"]) * 12, annual)
                        if opt["kind"] == "budget_with_balance_spread":
                            self.assertEqual(Decimal(opt["spread_usd"]) * opt["spread_payments"], balance)

    def test_every_memory_value_fits_the_cap(self):
        svc = ag.BillingService()
        for account, quote in svc.quotes.items():
            for rev, body in quote["revisions"].items():
                for oid in body["options"]:
                    values = ag.memory_for(svc, account, oid, int(rev))
                    with self.subTest(option=f"{oid} r{rev}"):
                        self.assertTrue(ag.memory_values_fit(values), values)
                        self.assertEqual(set(values), set(ag.MEMORY_KEYS))
        for customer in svc.data["customers"]:
            profile = ag.caller_profile(svc, customer)
            self.assertLessEqual(len(profile["account_list"]), ag.MEMORY_VALUE_LIMIT)

    def test_cap_matches_rasa(self):
        try:
            from rasa.mantle.prompts.memory_lines import MAX_MEMORY_VALUE_LENGTH
        except Exception:
            self.skipTest("rasa not installed")
        self.assertEqual(ag.MEMORY_VALUE_LIMIT, MAX_MEMORY_VALUE_LENGTH)


class ToolSurfaceTests(unittest.TestCase):
    ALLOWED = {"account", "option_id", "reference", "customer_words", "note", "context"}

    def test_no_tool_takes_an_amount_a_date_a_balance_or_a_fact(self):
        files = [PROJECT / "skills" / "budget_plan" / "tools.py", PROJECT / "tools" / "amber_grid_session.py"]
        seen = set()
        for path in files:
            tree = ast.parse(path.read_text())
            for node in tree.body:
                if isinstance(node, ast.AsyncFunctionDef) and any(
                        isinstance(d, ast.Call) and getattr(d.func, "id", "") == "tool" for d in node.decorator_list):
                    params = {a.arg for a in node.args.args}
                    with self.subTest(tool=node.name):
                        self.assertLessEqual(params, self.ALLOWED, f"{node.name} takes {params - self.ALLOWED}")
                    seen.add(node.name)
        self.assertEqual(seen, {"load_customer_profile", "get_budget_quote", "select_budget_option",
                                "request_budget_option", "check_budget_request", "route_hardship_referral",
                                "route_billing_support"})


class QuoteTests(unittest.TestCase):
    def test_quote_keeps_estimate_balance_and_schedule_apart(self):
        q = ag.get_budget_quote(ag.BillingService(), ME, "home electricity")
        self.assertEqual(q["status"], "quote")
        self.assertEqual(q["outstanding_balance"]["amount_usd"], "412.56")
        self.assertFalse(q["outstanding_balance"]["changed_by_budget_plan"])
        self.assertTrue(q["billing_basis"]["budget_amount_is_estimate"])
        self.assertEqual([o["option_id"] for o in q["options"]], ["BP-6120-A", "BP-6120-B"])
        self.assertTrue(all(o["debt_adjusted"] is False for o in q["options"]))
        self.assertNotIn("BP-6120-W", json.dumps(q))

    def test_ambiguous_words_ask_which_account(self):
        svc = ag.BillingService()
        self.assertEqual(ag.get_budget_quote(svc, ME, "electricity")["reason"], "which_account")
        self.assertEqual(ag.get_budget_quote(svc, ME, "home")["reason"], "which_account")
        self.assertEqual(ag.get_budget_quote(svc, ME, "the studio")["account"], STUDIO)

    def test_other_customers_account_looks_like_no_account(self):
        svc = ag.BillingService()
        theirs = ag.get_budget_quote(svc, ME, OTHER)
        missing = ag.get_budget_quote(svc, ME, "AG-9999")
        self.assertEqual(theirs["status"], "not_found")
        self.assertEqual({k: v for k, v in theirs.items()}, {k: v for k, v in missing.items()})
        self.assertEqual(ag.select_budget_option(svc, ME, "BP-6388-A")[0]["status"], "not_found")


class RequestTests(unittest.TestCase):
    def test_confirmed_request_records_once_with_balance_and_schedule_separate(self):
        svc = ag.BillingService()
        result, _ = select_and_request(svc, "BP-6120-B")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["effects"], 1)
        self.assertEqual(result["payment_schedule"]["monthly_total_usd"], "142.38")
        self.assertEqual(result["outstanding_balance"]["amount_usd"], "412.56")
        self.assertFalse(result["balance_changed"])
        self.assertFalse(result["debt_adjusted"])
        self.assertTrue(re.fullmatch(r"AG-BPR-[0-9A-F]{6}", result["reference"]))
        text = ag.customer_receipt("request_budget_option", result)
        self.assertIn(result["reference"], text)
        self.assertIn("Payment schedule: $142.38 a month", text)
        self.assertIn("Outstanding balance: $412.56, unchanged", text)
        self.assertEqual(ag.debt_adjustment_claims(text), [])
        # The same request again is a replay: no second effect, no second receipt.
        again, _ = ag.request_budget_option(svc, ME, {}, ag.Conversation(), "BP-6120-B", "t")
        self.assertEqual((again["status"], again["effects"], again["replay"]), ("succeeded", 0, True))
        self.assertIsNone(ag.customer_receipt("request_budget_option", again))
        self.assertEqual(again["requests_on_account"], 1)

    def test_request_without_an_answered_question_is_blocked(self):
        svc = ag.BillingService()
        _, memory = ag.select_budget_option(svc, ME, "BP-6120-A")
        asked = conversation_from_events([UserUttered("Budget plan please."),
                                          BotUttered(question_for(memory), ag.CONFIRM_UTTER)])
        result, cleared = ag.request_budget_option(svc, ME, memory, asked, "BP-6120-A", "t")
        self.assertEqual((result["status"], result["reason"]), ("blocked", "estimate_as_waiver"))
        self.assertEqual(result["effects"], 0)
        self.assertEqual(set(cleared.values()), {""})

    def test_question_without_the_balance_line_is_not_an_explanation(self):
        svc = ag.BillingService()
        _, memory = ag.select_budget_option(svc, ME, "BP-6120-A")
        short = f"Budget plan {memory['option_tag']}: {memory['option_schedule']}. {memory['option_basis']}. OK?"
        conv = conversation_from_events([BotUttered(short, ag.CONFIRM_UTTER), UserUttered("Yes")])
        result, _ = ag.request_budget_option(svc, ME, memory, conv, "BP-6120-A", "t")
        self.assertEqual(result["reason"], "estimate_as_waiver")

    def test_asked_about_one_option_cannot_request_another(self):
        svc = ag.BillingService()
        _, memory = ag.select_budget_option(svc, ME, "BP-6120-A")
        result, _ = ag.request_budget_option(svc, ME, memory, asked_and_answered(memory), "BP-6120-B", "t")
        self.assertEqual(result["status"], "blocked")
        self.assertNotIn(ELEC, svc.requests)

    def test_waiver_option_is_never_selectable_or_requestable(self):
        svc = ag.BillingService()
        selected, memory = ag.select_budget_option(svc, ME, "bp 6120 w")
        self.assertEqual((selected["status"], selected["reason"]), ("blocked", "unapproved_relief"))
        self.assertEqual(set(memory.values()), {""})
        forged = {"plan_account": "AG-6120 home electricity", "option_tag": "BP-6120-W r1",
                  "option_schedule": "$108.00 a month", "option_basis": "x", "option_balance": "written off"}
        result, _ = ag.request_budget_option(svc, ME, forged, asked_and_answered(forged), "BP-6120-W", "t")
        self.assertEqual((result["status"], result["reason"], result["effects"]), ("blocked", "unapproved_relief", 0))
        self.assertEqual(svc.requests, {})

    def test_forged_memory_schedule_is_refused(self):
        svc = ag.BillingService()
        _, memory = ag.select_budget_option(svc, ME, "BP-6120-A")
        memory = dict(memory, option_schedule="$70.00 a month from 1 Nov 2026, the usage estimate only")
        result, _ = ag.request_budget_option(svc, ME, memory, asked_and_answered(memory), "BP-6120-A", "t")
        self.assertEqual(result["status"], "blocked")

    def test_gas_re_estimate_withdraws_the_old_schedule_then_the_new_one_is_asked_again(self):
        svc = ag.BillingService()
        selected, memory = ag.select_budget_option(svc, ME, "BP-6121-A")
        self.assertEqual((selected["option_tag"], selected["monthly_total_usd"]), ("BP-6121-A r1", "58.00"))
        blocked, cleared = ag.request_budget_option(svc, ME, memory, asked_and_answered(memory), "BP-6121-A", "t")
        self.assertEqual((blocked["status"], blocked["reason"]), ("blocked", "unapproved_relief"))
        self.assertTrue(blocked["facts"]["billing_basis_explained"])
        self.assertEqual(blocked["withdrawn_option"], "BP-6121-A r1")
        self.assertEqual([o["option_tag"] for o in blocked["current_options"]], ["BP-6121-A r2", "BP-6121-B r2"])
        self.assertEqual(blocked["current_options"][0]["monthly_total_usd"], "66.50")
        self.assertEqual(blocked["outstanding_balance"]["amount_usd"], "96.60")
        self.assertEqual(set(cleared.values()), {""})
        quote = ag.get_budget_quote(svc, ME, "gas")
        self.assertIn("BP-6121-A r1", quote["withdrawn_options"])
        result, _ = select_and_request(svc, "BP-6121-A")
        self.assertEqual((result["status"], result["option_tag"]), ("succeeded", "BP-6121-A r2"))
        self.assertEqual(result["payment_schedule"]["monthly_total_usd"], "66.50")

    def test_unconfirmed_record_is_pending_then_reconciled_without_a_second_request(self):
        svc = ag.BillingService()
        result, _ = select_and_request(svc, "BP-6125-A")
        self.assertEqual((result["status"], result["reason"]), ("pending", "unrecorded_support_choice"))
        self.assertIsNone(result["reference"])
        self.assertEqual(result["effects"], 1)
        pending_text = ag.customer_receipt("request_budget_option", result)
        self.assertIn(result["request_id"], pending_text)
        self.assertIn("Not recorded yet", pending_text)
        found = ag.check_budget_request(svc, ME, result["request_id"])
        self.assertEqual((found["status"], found["effects"], found["reconciled"]), ("recorded", 0, True))
        self.assertTrue(found["reference"].startswith("AG-BPR-"))
        self.assertIn(found["reference"], ag.customer_receipt("check_budget_request", found))
        again = ag.check_budget_request(svc, ME, found["reference"])
        self.assertFalse(again["reconciled"])
        self.assertIsNone(ag.customer_receipt("check_budget_request", again))
        self.assertEqual(len(svc.requests), 1)

    def test_check_never_finds_an_unknown_reference(self):
        self.assertEqual(ag.check_budget_request(ag.BillingService(), ME, "AG-BPR-000000")["status"], "not_found")


class ReferralTests(unittest.TestCase):
    def test_hardship_referral_keeps_the_option_being_considered(self):
        svc = ag.BillingService()
        _, memory = ag.select_budget_option(svc, ME, "BP-6120-B")
        result, cleared = ag.route_hardship_referral(svc, ME, "home electricity", "I can't manage $142.38.",
                                                     memory, "t")
        self.assertEqual(result["status"], "referred")
        self.assertEqual(result["support_request_preserved"]["option_tag"], "BP-6120-B r1")
        self.assertFalse(result["relief_decided"])
        self.assertIsNone(result["terms_offered"])
        self.assertEqual(result["outstanding_balance"]["amount_usd"], "412.56")
        self.assertEqual(set(cleared.values()), {""})
        self.assertEqual(svc.requests, {})
        text = ag.customer_receipt("route_hardship_referral", result)
        self.assertIn("BP-6120-B r1", text)
        self.assertEqual(ag.relief_promises(text), [])
        again, _ = ag.route_hardship_referral(svc, ME, ELEC, "Please help.", {}, "t")
        self.assertTrue(again["replay"])
        self.assertEqual(again["referral_reference"], result["referral_reference"])
        self.assertIsNone(ag.customer_receipt("route_hardship_referral", again))

    def test_hardship_after_a_request_keeps_the_request(self):
        svc = ag.BillingService()
        request, _ = select_and_request(svc, "BP-6120-A")
        result, _ = ag.route_hardship_referral(svc, ME, ELEC, "I can't afford even that.", {}, "t")
        self.assertEqual(result["support_request_preserved"]["reference"], request["reference"])
        self.assertEqual(len(svc.requests), 1)

    def test_billing_support_changes_nothing(self):
        svc = ag.BillingService()
        result, _ = ag.route_billing_support(svc, ME, "gas", "Wants to review the budget plan first.", {}, "t")
        self.assertEqual(result["status"], "routed")
        self.assertEqual(result["owner"], ag.load_contract()["owner"])
        self.assertEqual(svc.requests, {})


class WordsTests(unittest.TestCase):
    CLAIMS = [
        "Your balance will be waived once you join.",
        "The $412.56 balance is written off when the plan starts.",
        "With the budget plan, your arrears go away.",
        "The outstanding balance disappears.",
        "You’ll no longer owe the old amount.",
        "You won’t owe the balance any more.",
        "The budget plan replaces your outstanding balance.",
        "$108 a month is all you owe.",
        "That’s all you need to pay.",
        "It’s a clean slate.",
    ]
    FINE = [
        "The budget plan does not reduce your balance.",
        "This option changes the payment schedule, not the stated balance.",
        "No, your balance isn’t waived.",
        "Your balance won’t be waived.",
        "The $412.56 balance is repaid by the 12 extra payments.",
        "Your balance will be paid off through 12 payments of $34.38.",
        "I can’t say that your balance is waived.",
        "Only the hardship team can decide whether your balance is reduced.",
        "You asked if your balance will be forgiven; it will not.",
    ]

    def test_debt_adjustment_claims(self):
        for text in self.CLAIMS:
            with self.subTest(text=text):
                self.assertTrue(ag.debt_adjustment_claims(text), text)
        for text in self.FINE:
            with self.subTest(text=text):
                self.assertEqual(ag.debt_adjustment_claims(text), [], text)

    def test_curly_and_straight_apostrophes_read_the_same(self):
        for straight in ("You'll no longer owe the old amount.", "That's all you need to pay.",
                         "I can't say that your balance is waived.", "Your balance won't be waived."):
            curly = straight.replace("'", "’")
            self.assertEqual(bool(ag.debt_adjustment_claims(straight)), bool(ag.debt_adjustment_claims(curly)))
        self.assertTrue(ag.relief_promises("They’ll waive it for you."))
        self.assertEqual(ag.relief_promises("I can’t promise they’ll waive it."), [])
        self.assertEqual(ag.unauthorized_amounts("I can’t set up $70 a month.", set()), [])

    def test_relief_promises(self):
        self.assertTrue(ag.relief_promises("The hardship team will waive your gas balance."))
        self.assertTrue(ag.relief_promises("You’re approved for hardship support."))
        self.assertEqual(ag.relief_promises("The hardship team decides whether they will reduce anything."), [])

    def test_unauthorized_amounts(self):
        ok = {Decimal("108.00"), Decimal("142.38"), Decimal("34.38")}
        self.assertEqual(ag.unauthorized_amounts("Option A is $108.00 a month.", ok), [])
        self.assertTrue(ag.unauthorized_amounts("I can set you up on $70 a month.", ok))
        self.assertEqual(ag.unauthorized_amounts("The $70 a month you asked for is not an option.", ok), [])
        self.assertEqual(ag.unauthorized_amounts("Your last bill was $61 a month.", ok), [])

    def test_spec_patterns_are_the_librarys(self):
        spec = json.loads(SPEC.read_text())
        metrics = spec["bot_text_metrics"]
        self.assertEqual(metrics["debt_adjustment"]["pattern"], ag.DEBT_ADJUSTMENT_PATTERN)
        self.assertEqual(metrics["debt_adjustment"]["unless_before"], ag.WORDS_HEDGE_PATTERN)
        self.assertEqual(metrics["relief_promise"]["pattern"], ag.RELIEF_PATTERN)
        self.assertEqual(metrics["relief_promise"]["unless_before"], ag.WORDS_HEDGE_PATTERN)
        self.assertIn("’", ag.WORDS_HEDGE_PATTERN)


class ConversationTests(unittest.TestCase):
    def test_question_and_answer_are_read_from_events(self):
        conv = conversation_from_events([
            UserUttered("/session_start"), UserUttered("Budget plan"),
            BotUttered("Q1", ag.CONFIRM_UTTER), UserUttered("yes"), BotUttered("Q2", ag.CONFIRM_UTTER),
        ])
        self.assertEqual((conv.confirmation_question, conv.confirmation_answered), ("Q2", False))
        self.assertEqual(conv.user_messages, ("Budget plan", "yes"))


class HookTests(unittest.TestCase):
    def setUp(self):
        try:
            import hooks  # noqa: F401
        except Exception:
            self.skipTest("rasa not installed; run make proof-full")
        import hooks
        self.hooks = hooks

    def test_remember_reads_json_text_results(self):
        svc = ag.BillingService()
        seen = {"amounts": set(), "balances": {}}
        self.hooks.remember(seen, self.hooks._as_dict(json.dumps(ag.get_budget_quote(svc, ME, ELEC))))
        self.assertEqual(seen["amounts"], {Decimal("108.00"), Decimal("142.38"), Decimal("34.38")})
        self.assertEqual(seen["balances"], {ELEC: "412.56"})
        self.assertEqual(self.hooks.problems("Option B is $142.38 a month; your $412.56 balance is not reduced.",
                                             seen), [])
        self.assertTrue(self.hooks.problems("Your balance will be waived.", seen))
        self.assertTrue(self.hooks.problems("I can put you on $90 a month.", seen))

    def test_a_confirmed_gated_result_is_remembered(self):
        """The engine reports the gated tool's result under resolve_tool_confirmation."""
        svc = ag.BillingService()
        _, memory = ag.select_budget_option(svc, ME, "BP-6121-A")
        blocked, _ = ag.request_budget_option(svc, ME, memory, asked_and_answered(memory), "BP-6121-A", "t")

        class Payload:
            tool_name, sender_id, value = "resolve_tool_confirmation", "hook-gated", json.dumps(blocked)

        asyncio.run(self.hooks.remember_billing_results(Payload()))
        self.assertIn(Decimal("66.50"), self.hooks._seen["hook-gated"]["amounts"])
        self.assertEqual(self.hooks.problems("The new budget is $66.50 a month from 1 Nov 2026.",
                                             self.hooks._seen["hook-gated"]), [])

    def test_fallback_says_schedule_not_balance(self):
        seen = {"amounts": set(), "balances": {ELEC: "412.56"}}
        text = self.hooks.fallback_text(seen)
        self.assertIn("$412.56", text)
        self.assertEqual(self.hooks.problems(text, seen), [])

    def test_retries_twice_then_replaces(self):
        from rasa.mantle.hooks import RetryModel

        class Payload:
            def __init__(self, text):
                self.text, self.sender_id = text, "hook-test"

            def model_copy(self, update):
                return Payload(update["text"])

        bad = Payload("Great news: your balance will be waived.")
        for _ in range(2):
            with self.assertRaises(RetryModel):
                asyncio.run(self.hooks.block_debt_adjustment_words.__wrapped__(bad)
                            if hasattr(self.hooks.block_debt_adjustment_words, "__wrapped__")
                            else self.hooks.block_debt_adjustment_words(bad))
        out = asyncio.run(self.hooks.block_debt_adjustment_words.__wrapped__(bad)
                          if hasattr(self.hooks.block_debt_adjustment_words, "__wrapped__")
                          else self.hooks.block_debt_adjustment_words(bad))
        self.assertIn("changes the payment schedule, not the stated balance", out.text)


if __name__ == "__main__":
    unittest.main()
