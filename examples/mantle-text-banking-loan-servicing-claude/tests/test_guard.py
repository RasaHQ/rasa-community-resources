"""Offline checks for the Northgate payoff-quote guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
(The hook and engine-limit tests need rasa and are skipped under a bare
python3; `make proof-full` runs them in the project venv.)
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

from lib import servicing as nb  # noqa: E402

CASEBOOK_CONTRACT = PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "banking-loan-servicing.json"
MARISOL = "NB-CUST-6130"
TOMAS = "NB-CUST-7001"
SPEC = json.loads((PROJECT / "case-build" / "conversations.json").read_text())


def lab_outcome(facts: dict, contract: dict) -> tuple[str, str]:
    """The lab's execute() order. This contract has request rules only."""
    reason = nb.evaluate(facts, contract)
    return ("blocked", reason) if reason else ("succeeded", "verified_fixture_receipt")


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), nb.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = nb.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(lab_outcome(variant["facts"], contract), (expected["status"], expected["reason"]))

    def test_all_three_rules_are_request_rules(self):
        self.assertEqual([r["field"] for r in nb.request_rules()],
                         ["quote_valid_today", "included_charges_explicit", "servicing_route_available"])


class FictionalOrganisationTests(unittest.TestCase):
    def test_the_fixture_is_marked_fictional(self):
        data = nb.load_data()
        self.assertIn("(fictional)", data["organisation"])
        self.assertIn("fictional", data["note"].lower())
        self.assertEqual(nb.ORGANISATION, "Northgate Bank")

    def test_the_guard_refuses_unmarked_or_real_names(self):
        data = nb.load_data()
        with self.assertRaises(nb.FictionalOrganisationError):
            nb.assert_fictional({**data, "organisation": "Northgate Bank"})
        with self.assertRaises(nb.FictionalOrganisationError):
            nb.assert_fictional({**data, "note": "Sample data."})
        renamed = json.loads(json.dumps(data))
        renamed["loans"]["NB-LN-5108"]["servicing_route"]["detail"] = "Transferred to Wells Fargo."
        with self.assertRaises(nb.FictionalOrganisationError):
            nb.assert_fictional(renamed)


class LoanResolutionTests(unittest.TestCase):
    def setUp(self):
        self.svc = nb.Servicing()

    def resolve(self, words, customer=MARISOL):
        return nb.resolve_loan(self.svc, customer, words)

    def test_names_endings_and_ids_resolve(self):
        self.assertEqual(self.resolve("my car loan")["loan_ref"], "NB-LN-4417")
        self.assertEqual(self.resolve("the personal one")["loan_ref"], "NB-LN-2290")
        self.assertEqual(self.resolve("loan ending 2290")["loan_ref"], "NB-LN-2290")
        self.assertEqual(self.resolve("NB-LN-7702")["loan_ref"], "NB-LN-7702")
        self.assertEqual(self.resolve("Auto loan ending 4417")["loan_ref"], "NB-LN-4417")
        self.assertEqual(self.resolve("HELOC")["loan_ref"], "NB-LN-7702")

    def test_my_loan_is_ambiguous(self):
        got = self.resolve("my loan")
        self.assertEqual((got["status"], got["reason"]), ("blocked", "loan_ambiguous"))
        self.assertEqual(len(got["candidates"]), 4)

    def test_another_customers_loan_looks_like_no_loan(self):
        others = self.resolve("NB-LN-8830")
        missing = self.resolve("NB-LN-9999")
        self.assertEqual(others, missing)
        self.assertEqual(others["reason"], "loan_not_found")
        self.assertEqual(self.resolve("NB-LN-8830", customer=TOMAS)["loan_ref"], "NB-LN-8830")


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.svc = nb.Servicing()

    def present(self, words, customer=MARISOL):
        return nb.present_payoff_quote(self.svc, customer, words)

    def test_current_scoped_quote_is_presented_with_its_receipt(self):
        got = self.present("personal loan")
        self.assertEqual((got["status"], got["quote_ref"], got["payoff_amount"], got["effects"]),
                         ("presented", "PQ-2290-0930", "$6,878.21", 1))
        self.assertEqual(got["good_through"], "Oct 14, 2026, 5:00 PM ET")
        self.assertEqual(got["quoted_at"], "Sep 30, 2026, 8:02 AM ET")
        self.assertEqual(len(got["included_charges"]), 2)
        self.assertIn("closes only after", got["next_step"])
        self.assertEqual(self.svc.presentations, [{"quote_ref": "PQ-2290-0930", "loan_ref": "NB-LN-2290"}])

    def test_each_bad_fact_blocks_with_the_contract_reason_and_no_amount(self):
        cases = {"car loan": "quote_expired", "home equity": "quote_scope_missing", "boat": "no_servicing_route"}
        for words, reason in cases.items():
            with self.subTest(loan=words):
                got = self.present(words)
                self.assertEqual((got["status"], got["reason"], got["effects"]), ("blocked", reason, 0))
                self.assertNotIn("payoff_amount", got)
                self.assertNotIn("$", json.dumps(got))
        self.assertEqual(self.svc.presentations, [])

    def test_expiry_is_measured_on_the_servicing_clock(self):
        quote = self.svc.quotes["PQ-4417-0929"]
        self.assertIs(self.svc.facts(quote)["quote_valid_today"], False)
        self.svc.clock = self.svc.clock.replace(day=29, hour=16)
        self.assertIs(self.svc.facts(quote)["quote_valid_today"], True)

    def test_charges_must_add_up_to_the_quote(self):
        quote = dict(self.svc.quotes["PQ-2290-0930"])
        quote["amount"] = Decimal("6900.00")
        self.assertIs(self.svc.facts(quote)["included_charges_explicit"], False)

    def test_refresh_issues_a_dated_quote_that_then_presents(self):
        issued = nb.refresh_payoff_quote(self.svc, MARISOL, "car loan")
        self.assertEqual(issued["status"], "issued")
        self.assertRegex(issued["quote_ref"], r"^PQ-4417-(?!0929$)")
        self.assertNotIn("$", json.dumps(issued))
        got = self.present("car loan")
        self.assertEqual((got["status"], got["quote_ref"], got["payoff_amount"]),
                         ("presented", issued["quote_ref"], "$14,252.82"))
        self.assertEqual(got["good_through"], "Oct 9, 2026, 5:00 PM ET")
        # The refreshed quote is deterministic, so conversations can check it.
        self.assertEqual(nb.refresh_payoff_quote(self.svc, MARISOL, "auto")["quote_ref"], issued["quote_ref"])

    def test_refresh_source_unavailable_gives_no_figure(self):
        got = nb.refresh_payoff_quote(self.svc, MARISOL, "home equity")
        self.assertEqual((got["status"], got["reason"]), ("unavailable", "quote_source_unavailable"))
        self.assertNotIn("$", json.dumps(got))
        self.assertEqual(self.present("home equity")["reason"], "quote_scope_missing")

    def test_balance_is_a_view_not_a_payoff(self):
        got = nb.get_loan_balance(self.svc, MARISOL, "car loan")
        self.assertEqual((got["status"], got["principal_balance"], got["balance_as_of"]),
                         ("read", "$14,212.55", "Sep 29, 2026"))
        self.assertIn("not a payoff amount", got["not_a_payoff"])


class InstructionsTests(unittest.TestCase):
    def setUp(self):
        self.svc = nb.Servicing()

    def test_instructions_follow_the_presented_quote_and_take_no_payment(self):
        quote = nb.present_payoff_quote(self.svc, MARISOL, "personal")
        got = nb.send_payoff_instructions(self.svc, MARISOL, quote["quote_ref"], quote["quote_ref"])
        self.assertEqual((got["status"], got["payment_taken"], got["effects"]), ("sent", False, 1))
        self.assertTrue(got["reference"].startswith("PI-2290-"))

    def test_an_unpresented_or_expired_quote_gets_no_instructions(self):
        for stored, given in ((None, "PQ-2290-0930"), ("PQ-2290-0930", "PQ-4417-0929"), ("PQ-4417-0929", "PQ-4417-0929")):
            with self.subTest(stored=stored, given=given):
                got = nb.send_payoff_instructions(self.svc, MARISOL, stored, given)
                self.assertEqual((got["status"], got["effects"]), ("blocked", 0))
        self.assertEqual(self.svc.instructions, [])

    def test_another_customers_quote_is_refused(self):
        got = nb.send_payoff_instructions(self.svc, MARISOL, "PQ-8830-0930", "PQ-8830-0930")
        self.assertEqual(got["reason"], "quote_not_presented")

    def test_hardship_stops_the_payoff_flow(self):
        quote = nb.present_payoff_quote(self.svc, MARISOL, "personal")
        routed = nb.route_hardship_support(self.svc, MARISOL, "personal loan", "lost job")
        self.assertEqual((routed["status"], routed["payoff_flow"]), ("routed", "stopped"))
        got = nb.send_payoff_instructions(self.svc, MARISOL, quote["quote_ref"], quote["quote_ref"])
        self.assertEqual((got["status"], got["reason"]), ("blocked", "hardship_referral_open"))

    def test_hardship_without_a_loan_covers_every_loan(self):
        nb.route_hardship_support(self.svc, MARISOL, "", "behind on payments")
        self.assertEqual(set(self.svc.hardship), set(self.svc.loans_of(MARISOL)))

    def test_callback_is_booked_with_the_owner(self):
        got = nb.schedule_servicing_callback(self.svc, MARISOL, "home equity", "quote source unavailable")
        self.assertEqual((got["status"], got["owner"]), ("scheduled", "loan servicing owner"))
        self.assertTrue(got["reference"].startswith("CB-7702-"))

    def test_conversations_do_not_share_a_servicing_system(self):
        nb.refresh_payoff_quote(nb.servicing_for("a"), MARISOL, "car")
        self.assertEqual(nb.present_payoff_quote(nb.servicing_for("b"), MARISOL, "car")["reason"], "quote_expired")


class MemoryLimitTests(unittest.TestCase):
    """Mantle cuts a memory value over 100 characters in the prompt, silently. Each value here is one short field."""

    def test_project_memory_is_one_short_field_per_loan(self):
        lines = nb.profile_memory_lines()
        self.assertEqual(set(lines), {"loan_auto", "loan_personal", "loan_home_equity", "loan_boat"})
        declared = (PROJECT / "memory.yml").read_text()
        for key, value in lines.items():
            self.assertLessEqual(len(value), nb.PROMPT_MEMORY_VALUE_LIMIT, key)
            self.assertIn(f"{key}:", declared)

    def test_quote_memory_values_fit_for_every_presentable_quote(self):
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("payoff_tools", PROJECT / "skills" / "loan_payoff" / "tools.py")
            tools = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tools)
        except ImportError as exc:
            self.skipTest(f"rasa not importable: {exc}")
        svc = nb.Servicing()
        for loan in svc.loans_of(MARISOL):
            nb.refresh_payoff_quote(svc, MARISOL, loan)
            result = nb.present_payoff_quote(svc, MARISOL, loan)
            for key, value in tools.quote_memory(result).items():
                self.assertLessEqual(len(value), nb.PROMPT_MEMORY_VALUE_LIMIT, (loan, key))
        declared = (PROJECT / "skills" / "loan_payoff" / "memory.yml").read_text()
        for key in tools.QUOTE_FIELDS:
            self.assertIn(f"{key}:", declared)

    def test_engine_limit_matches_ours(self):
        try:
            from rasa.mantle.prompts.memory_lines import MAX_MEMORY_VALUE_LENGTH
        except ImportError:
            self.skipTest("rasa not importable")
        self.assertEqual(MAX_MEMORY_VALUE_LENGTH, nb.PROMPT_MEMORY_VALUE_LIMIT)


class WordingTests(unittest.TestCase):
    def test_payoff_figures_are_found(self):
        cases = {
            "Your payoff is $14,252.82.": [Decimal("14252.82")],
            "The payoff amount today is $6,878.21, good through Oct 14.": [Decimal("6878.21")],
            "Paying $14,212.55 will pay the loan off.": [Decimal("14212.55")],
            "It would be about $48,900 to close it.": [Decimal("48900.00")],
            "Your payoff for the auto loan is $14,252.82.": [Decimal("14252.82")],
            "Payoff amount: $6,878.21": [Decimal("6878.21")],
            "That was yesterday's figure; your payoff is $14,230.08.": [Decimal("14230.08")],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(nb.payoff_figures(text), expected)

    def test_negated_dated_and_breakdown_figures_are_not_payoff_claims(self):
        for text in (
            "Yesterday's payoff of $14,230.08 has expired.",
            "Your payoff is not $14,212.55.",
            "The payoff quote includes principal $14,212.55 and interest $25.27.",
            "Is your payoff $14,212.55?",
            "Your balance is $14,212.55.",
        ):
            with self.subTest(text=text):
                self.assertEqual(nb.payoff_figures(text), [])

    def test_closure_promises(self):
        for text in ("Your loan will be closed today.", "I can close your loan today.", "The auto loan will be paid off."):
            with self.subTest(text=text):
                self.assertTrue(nb.closure_promises(text))
        for text in ("Once the payoff is received and posted, your loan will be closed.",
                     "I can't close your loan today.", "The loan closes only after the payoff posts."):
            with self.subTest(text=text):
                self.assertEqual(nb.closure_promises(text), [])

    def test_case_build_metric_uses_the_same_patterns(self):
        metric = SPEC["bot_text_metrics"]["closure_promise"]
        self.assertEqual(metric["pattern"], nb.CLOSURE_PROMISE_RE.pattern)
        self.assertEqual(metric["unless_before"], nb.CLOSURE_HEDGE_RE.pattern)


class SpecTests(unittest.TestCase):
    TOOLS = {"present_payoff_quote", "refresh_payoff_quote", "send_payoff_instructions", "get_loan_balance",
             "schedule_servicing_callback", "route_hardship_support", "*"}

    def walk(self, checks):
        for check in checks:
            if check["type"] == "any_of":
                yield from self.walk(check["checks"])
            else:
                yield check

    def test_spec_names_only_real_tools_and_quotes(self):
        quotes = set(nb.load_data()["quotes"])
        self.assertGreaterEqual(len(SPEC["conversations"]), 20)
        for conv in SPEC["conversations"]:
            for check in self.walk(conv["checks"]):
                if "tool" in check:
                    self.assertIn(check["tool"], self.TOOLS, conv["id"])
                ref = (check.get("result") or {}).get("quote_ref")
                if isinstance(ref, str) and not ref.startswith("re:"):
                    self.assertIn(ref, quotes, conv["id"])
                if "after_user_turn" in check:
                    self.assertLess(check["after_user_turn"], len(conv["turns"]), conv["id"])

    def test_model_price_is_the_vendor_price(self):
        price = SPEC["model_price"]
        self.assertEqual((price["input_cost_per_token"], price["output_cost_per_token"],
                          price["cache_creation_input_token_cost"], price["cache_read_input_token_cost"]),
                         (2e-06, 1e-05, 2.5e-06, 2e-07))


class ToolSurfaceTests(unittest.TestCase):
    """No tool lets the model assert an amount, a date, a fact or a customer."""

    def params(self, path: Path) -> dict[str, list[str]]:
        tree = ast.parse(path.read_text())
        return {n.name: [a.arg for a in n.args.args] for n in tree.body if isinstance(n, ast.AsyncFunctionDef)}

    def test_tool_parameters(self):
        skill = self.params(PROJECT / "skills" / "loan_payoff" / "tools.py")
        shared = self.params(PROJECT / "tools" / "northgate_loans.py")
        self.assertEqual(set(skill), {"present_payoff_quote", "refresh_payoff_quote", "send_payoff_instructions"})
        self.assertEqual(set(shared), {"load_caller_profile", "get_loan_balance", "schedule_servicing_callback",
                                       "route_hardship_support"})
        for name, args in {**skill, **shared}.items():
            for arg in args:
                self.assertNotRegex(arg, r"amount|balance|date|valid|explicit|route_available|customer|charge|payment",
                                    f"{name}({arg})")


class HookTests(unittest.TestCase):
    """hooks.py against the installed engine's payload types (skipped without rasa)."""

    @classmethod
    def setUpClass(cls):
        try:
            import hooks  # noqa: F401
            from rasa.mantle.hooks import ModelRequestPayload, ModelResponsePayload, RetryModel, ToolResultPayload
        except ImportError as exc:  # bare python3 without the project venv
            raise unittest.SkipTest(f"rasa not importable: {exc}")
        cls.hooks, cls.Request, cls.Model, cls.Retry, cls.Tool = (
            hooks, ModelRequestPayload, ModelResponsePayload, RetryModel, ToolResultPayload)

    def run_hook(self, coro):
        import asyncio

        return asyncio.run(coro)

    def respond(self, sender, text):
        return self.run_hook(self.hooks.block_unquoted_payoffs(self.Model(sender_id=sender, text=text)))

    def tool(self, sender, name, result):
        self.run_hook(self.hooks.remember_presented_quotes(
            self.Tool(sender_id=sender, tool_name=name, arguments={}, value=json.dumps(result))))

    def test_presented_amount_passes(self):
        sender = "presented"
        self.tool(sender, "present_payoff_quote", nb.present_payoff_quote(nb.Servicing(), MARISOL, "personal"))
        text = "Your payoff is $6,878.21, quote PQ-2290-0930, good through Oct 14, 2026, 5:00 PM ET."
        self.assertEqual(self.respond(sender, text).text, text)

    def test_balance_as_payoff_retries_then_is_replaced(self):
        sender = "balance"
        for _ in range(self.hooks.MAX_CONSECUTIVE_RETRIES):
            with self.assertRaises(self.Retry) as raised:
                self.respond(sender, "Your payoff is $14,212.55.")
            self.assertIn("no presented quote", raised.exception.feedback)
        replaced = self.respond(sender, "Your payoff is $14,212.55.")
        self.assertNotIn("$14,212.55", replaced.text)

    def test_closure_promise_retries(self):
        with self.assertRaises(self.Retry):
            self.respond("closure", "Done. Your loan will be closed today.")

    def test_request_ending_on_the_greeting_gets_the_user_turn_again(self):
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "Payoff on my car loan please."},
                    {"role": "assistant", "content": "Hello Marisol, this is Northgate Bank loan servicing."}]
        got = self.run_hook(self.hooks.ensure_trailing_user_turn(self.Request(sender_id="s", messages=messages)))
        self.assertEqual(got.messages[-1], {"role": "user", "content": "Payoff on my car loan please."})
        self.assertEqual(len(got.messages), 4)

    def test_request_ending_on_user_or_tool_is_untouched(self):
        for tail in ([{"role": "user", "content": "hi"}],
                     [{"role": "user", "content": "hi"},
                      {"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]},
                      {"role": "tool", "content": "{}", "tool_call_id": "1"}],
                     [{"role": "user", "content": "hi"}, {"role": "system", "content": "reminder"}]):
            messages = [{"role": "system", "content": "sys"}, *tail]
            got = self.run_hook(self.hooks.ensure_trailing_user_turn(self.Request(sender_id="s", messages=messages)))
            self.assertEqual(got.messages, messages)


if __name__ == "__main__":
    unittest.main()
