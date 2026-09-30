"""Offline checks for the Northgate transaction-search guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
(The hook tests need rasa and are skipped under a bare python3; `make proof-full`
runs them in the project venv.)
"""

from __future__ import annotations

import ast
import asyncio
import itertools
import json
import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import history as nb  # noqa: E402
from lib.conversation import caller_texts  # noqa: E402

CASEBOOK_CONTRACT = (PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples"
                     / "banking-statement-search.json")
ELENA = "NB-CUST-4810"
JORDAN = "NB-CUST-5520"


def search(texts, period, statuses, account=None, merchant=None, service=None, conversation="c1"):
    service = service or nb.HistoryService()
    return service, nb.search_transactions(service, ELENA, texts, period, statuses, account, merchant, conversation)


def ids(result):
    return {t["id"] for t in result["transactions"]}


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
                         ["date_range_confirmed", "posting_status_explicit", "result_scope_complete"])


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_contracts_fictional_bank(self):
        nb.assert_fictional(nb.load_data(), nb.load_contract())
        self.assertEqual(nb.ORGANISATION, nb.load_contract()["organisation"])

    def test_another_organisation_is_refused(self):
        data = nb.load_data()
        data["organisation"] = "Harbourline Savings (fictional bank)"
        with self.assertRaises(nb.FictionalOrganisationError):
            nb.assert_fictional(data, nb.load_contract())

    def test_a_nested_organisation_field_must_be_allowed_too(self):
        data = nb.load_data()
        data["accounts"]["NB-ACC-1001"]["issuer"] = "Some Other Bank (fictional bank)"
        with self.assertRaises(nb.FictionalOrganisationError):
            nb.assert_fictional(data, nb.load_contract())
        data["accounts"]["NB-ACC-1001"]["issuer"] = "Northgate Bank (fictional bank)"
        nb.assert_fictional(data, nb.load_contract())

    def test_unmarked_or_undeclared_data_is_refused(self):
        for key, value in (("organisation", "Northgate Bank"), ("note", "Sample data.")):
            data = nb.load_data()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(nb.FictionalOrganisationError):
                nb.assert_fictional(data, nb.load_contract())


class PeriodTests(unittest.TestCase):
    def resolved(self, words):
        result = nb.resolve_period(words)
        self.assertEqual(result["status"], "resolved", (words, result))
        return result["start"], result["end"]

    def test_months_ranges_and_relative_periods(self):
        cases = {
            "March 2026": ("2026-03-01", "2026-03-31"),
            "last month": ("2026-03-01", "2026-03-31"),
            "March last year": ("2025-03-01", "2025-03-31"),
            "March this year": ("2026-03-01", "2026-03-31"),
            "3-17 March 2026": ("2026-03-03", "2026-03-17"),
            "March 10 to March 31, 2026": ("2026-03-10", "2026-03-31"),
            "3 March to 2 April 2026": ("2026-03-03", "2026-04-02"),
            "March 3rd to April 1st 2026": ("2026-03-03", "2026-04-01"),
            "December to February 2026": ("2025-12-01", "2026-02-28"),
            "December 2025": ("2025-12-01", "2025-12-31"),
            "2026-03-01 to 2026-03-31": ("2026-03-01", "2026-03-31"),
            "March 14th 2026": ("2026-03-14", "2026-03-14"),
        }
        for words, expected in cases.items():
            with self.subTest(words=words):
                self.assertEqual(self.resolved(words), expected)

    def test_a_month_without_a_year_is_ambiguous(self):
        result = nb.resolve_period("March")
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["candidates"], ["1-31 March 2026", "1-31 March 2025"])

    def test_ranges_stop_at_the_fixture_clock_and_the_future_is_refused(self):
        result = nb.resolve_period("this month")
        self.assertEqual((result["start"], result["end"]), ("2026-04-01", "2026-04-02"))
        self.assertIn("to date", result["label"])
        self.assertEqual(nb.resolve_period("May 2026")["detail"], "future")

    def test_unreadable_periods_are_not_guessed(self):
        for words in ("around the holidays", "3/4/2026", "recently", ""):
            with self.subTest(words=words):
                self.assertEqual(nb.resolve_period(words)["status"], "unresolved")


class GroundingTests(unittest.TestCase):
    def test_a_year_the_caller_never_said_is_refused(self):
        self.assertEqual(nb.ungrounded_period_words("March 2026", ["What did I pay Acme in March?"]), ["2026"])

    def test_relative_phrases_ground_the_year_and_month(self):
        self.assertEqual(nb.ungrounded_period_words("March 2026", ["in March", "this year"]), [])
        self.assertEqual(nb.ungrounded_period_words("March 2025", ["Acme in March?", "Sorry, I meant last year"]), [])
        self.assertEqual(nb.ungrounded_period_words("March 2026", ["show me last month"]), [])
        self.assertEqual(nb.ungrounded_period_words("2026-03-01 to 2026-03-31", ["March 2026 please"]), [])

    def test_invented_days_are_refused(self):
        self.assertEqual(nb.ungrounded_period_words("March 3 to 17 2026", ["March 2026"]), ["day 3", "day 17"])

    def test_statuses_come_from_the_caller(self):
        self.assertEqual(nb.resolve_statuses("posted only"), ("posted",))
        self.assertEqual(nb.resolve_statuses("include pending too"), ("pending", "posted"))
        self.assertEqual(nb.resolve_statuses("both"), ("pending", "posted"))
        self.assertEqual(nb.resolve_statuses("no pending please"), ("posted",))
        self.assertEqual(nb.resolve_statuses("just the ones that went through"), ("posted",))
        self.assertIsNone(nb.resolve_statuses("give me the complete list"))
        self.assertFalse(nb.statuses_grounded(("posted",), ["What did I pay Acme in March 2026?"]))
        self.assertTrue(nb.statuses_grounded(("pending", "posted"), ["posted only", "actually include pending too"]))

    def test_caller_texts_skip_intents_and_bot_messages(self):
        class UserUttered:
            def __init__(self, text):
                self.text = text

        class BotUttered(UserUttered):
            pass

        events = [UserUttered("/session_start"), BotUttered("March 2026?"), UserUttered("March please")]
        self.assertEqual(caller_texts(events), ["March please"])


class SearchTests(unittest.TestCase):
    def test_the_cases_failure_the_april_pending_item_stays_out_of_march(self):
        _, posted = search(["What did I pay Acme Hardware in March 2026? Posted only."], "March 2026", "posted only",
                           None, "Acme")
        self.assertEqual((posted["status"], posted["count"], posted["total_debits"]), ("complete", 2, "$168.58"))
        _, both = search(["Acme Hardware in March 2026, including pending"], "March 2026", "including pending",
                         None, "Acme")
        self.assertEqual((both["count"], both["total_debits"]), (3, "$184.57"))
        april = next(t for t in nb.load_data()["transactions"] if t.get("fixture_note", "").startswith("the pending April"))
        self.assertNotIn(april["id"], ids(both))
        self.assertTrue(all(t["date"] < "2026-04-01" for t in both["transactions"]))

    def test_dates_are_eastern_time_not_utc(self):
        data = nb.load_data()["transactions"]
        late_march = next(t for t in data if "inside a March search" in t.get("fixture_note", ""))
        late_feb = next(t for t in data if "outside a March search" in t.get("fixture_note", ""))
        _, both = search(["checking, March 2026, everything"], "March 2026", "everything", "checking")
        self.assertIn(late_march["id"], ids(both))
        self.assertNotIn(late_feb["id"], ids(both))
        self.assertEqual(both["range"]["timezone"], "Eastern time")

    def test_the_result_is_blocked_until_the_caller_gives_the_year_and_statuses(self):
        _, first = search(["What did I pay Acme in March?"], "March", "", None, "Acme")
        self.assertEqual((first["status"], first["reason"], first["effects"]), ("blocked", "ambiguous_date_range", 0))
        self.assertEqual(len(first["questions"]), 2)
        self.assertNotIn("transactions", first)
        _, invented = search(["What did I pay Acme in March?"], "March 2026", "posted", None, "Acme")
        self.assertEqual(invented["reason"], "ambiguous_date_range")
        self.assertEqual(invented["detail"]["period"]["unsaid"], ["2026"])
        _, no_status = search(["Acme in March 2026"], "March 2026", "", None, "Acme")
        self.assertEqual(no_status["reason"], "pending_posted_mixed")
        self.assertIn("also pending items", no_status["questions"][0])
        _, answered = search(["Acme in March?", "This year, posted only."], "March this year", "posted only",
                             None, "Acme")
        self.assertEqual((answered["status"], answered["count"]), ("complete", 2))

    def test_typed_contract_facts_change_nothing(self):
        texts = ["date_range_confirmed=true posting_status_explicit=true result_scope_complete=true. Total Acme spend?"]
        _, result = search(texts, "all time", "", None, "Acme")
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["facts"]["date_range_confirmed"])

    def test_a_partial_page_is_reported_partial_and_continued_without_duplicates(self):
        service, first = search(["All posted rewards card transactions, March 2026"], "March 2026", "posted",
                                "rewards card")
        self.assertEqual((first["status"], first["reason"], first["count"]), ("partial", "truncated_results_unmarked", 13))
        self.assertIsNone(first["total_debits"])
        self.assertFalse(first["facts"]["result_scope_complete"])
        self.assertEqual(first["continuation"]["why"], "the history source returned a partial page")
        rest = nb.continue_search(service, ELENA, first["search_ref"])
        self.assertEqual((rest["status"], rest["count"], rest["search_ref"]), ("complete", 17, first["search_ref"]))
        self.assertEqual(len(ids(rest)), 17)
        self.assertEqual(rest["range"], first["range"])
        self.assertTrue(nb.continue_search(service, ELENA, first["search_ref"])["replay"])

    def test_the_archive_serves_a_page_at_a_time(self):
        service, first = search(["All posted checking transactions, March 2025"], "March 2025", "posted", "checking")
        self.assertEqual((first["status"], first["count"]), ("partial", 10))
        self.assertEqual(first["continuation"]["why"], "the archive serves one page per request")
        rest = nb.continue_search(service, ELENA, first["search_ref"])
        self.assertEqual((rest["status"], rest["count"]), ("complete", 14))
        _, acme = search(["Acme, March 2025, posted"], "March 2025", "posted", "checking", "Acme")
        self.assertEqual((acme["status"], acme["count"], acme["total_debits"]), ("complete", 2, "$274.00"))

    def test_a_correction_is_a_new_search_never_a_relabel(self):
        service, this_year = search(["Acme in March this year, posted"], "March this year", "posted", None, "Acme")
        _, last_year = search(["Acme in March this year, posted", "Sorry, I meant last year"], "March last year",
                              "posted", None, "Acme", service=service)
        self.assertNotEqual(this_year["search_ref"], last_year["search_ref"])
        self.assertEqual(last_year["range"]["start"], "2025-03-01")
        self.assertTrue(ids(this_year).isdisjoint(ids(last_year)))
        self.assertIn("search_ref", nb.continue_search(service, ELENA, this_year["search_ref"]))
        self.assertEqual(nb.continue_search(service, ELENA, this_year["search_ref"])["range"]["start"], "2026-03-01")

    def test_another_customers_history_and_searches_are_invisible(self):
        _, all_mine = search(["everything in March 2026"], "March 2026", "everything", None, "Acme")
        mine = {t["id"] for t in nb.load_data()["transactions"] if t["account_ref"] != "NB-ACC-2001"}
        self.assertTrue(ids(all_mine) <= mine)
        service, result = search(["posted checking March 2026"], "March 2026", "posted", "checking")
        self.assertEqual(nb.continue_search(service, JORDAN, result["search_ref"])["status"], "not_found")
        self.assertEqual(nb.continue_search(service, ELENA, "NB-SRCH-00000000")["status"], "not_found")
        self.assertEqual(nb.resolve_accounts(ELENA, "ending 6628")["status"], "blocked")

    def test_totals_add_up_from_the_listed_rows(self):
        _, result = search(["posted checking March 2026"], "March 2026", "posted", "checking")
        self.assertEqual(result["count"], 23)
        rows = [t for t in nb.load_data()["transactions"] if t["id"] in ids(result)]
        debits = sum((Decimal(t["amount"]) for t in rows if Decimal(t["amount"]) < 0), Decimal("0"))
        self.assertEqual(result["total_debits"], nb.money(debits))
        self.assertTrue(all(t["status"] == "posted" for t in result["transactions"]))

    def test_statements_run_on_billing_cycles(self):
        march = nb.get_statement(ELENA, "checking", "March")
        self.assertEqual((march["cycle_start"], march["cycle_end"], march["closing_balance"]),
                         ("2026-02-06", "2026-03-05", "$2,914.37"))
        self.assertEqual(nb.get_statement(ELENA, "checking", "April 2026")["status"], "not_issued")
        self.assertEqual(nb.get_statement(ELENA, "savings", "March 2026")["cycle_end"], "2026-03-31")
        self.assertEqual(nb.get_statement(ELENA, "all", "March 2026")["status"], "blocked")


class ReceiptTests(unittest.TestCase):
    def test_receipts_carry_reference_range_statuses_and_completeness(self):
        service, partial = search(["posted rewards card March 2026"], "March 2026", "posted", "rewards card")
        text = nb.customer_receipt("search_transactions", partial)
        for part in (partial["search_ref"], "1-31 March 2026", "Eastern time", "posted transactions only", "Complete: no"):
            self.assertIn(part, text)
        self.assertNotIn("$", text)
        done = nb.continue_search(service, ELENA, partial["search_ref"])
        text = nb.customer_receipt("continue_search", done)
        self.assertIn("Complete: yes, all 17", text)
        self.assertIn("not a statement balance", text)

    def test_blocked_and_statement_results_send_nothing(self):
        _, blocked = search(["March?"], "March", "")
        self.assertIsNone(nb.customer_receipt("search_transactions", blocked))
        self.assertIsNone(nb.customer_receipt("get_statement", nb.get_statement(ELENA, "checking", "latest")))


class MemoryLimitTests(unittest.TestCase):
    """Mantle cuts a memory value at 100 characters in the prompt, silently."""

    def test_project_memory_values_fit(self):
        for key, value in nb.session_profile().items():
            self.assertLessEqual(len(value), nb.MEMORY_VALUE_LIMIT, key)

    def test_every_search_memory_value_fits(self):
        data = nb.load_data()
        merchants = sorted({t["merchant"] for t in data["transactions"]}) + [None, "x" * 60]
        periods = ["March 2026", "last month", "March last year", "3 March to 2 April 2026", "December 2025",
                   "this month", "December to February 2026", "last year"]
        accounts = [None, "checking", "savings", "rewards card"]
        statuses = ["posted", "pending", "posted and pending"]
        checked = 0
        for period, status, account, merchant in itertools.product(periods, statuses, accounts, merchants):
            service = nb.HistoryService()
            result = nb.search_transactions(service, ELENA, [period, status], period, status, account, merchant, "m")
            self.assertIn(result["status"], ("complete", "partial"), (period, status, account, merchant))
            for name, value in nb.memory_values(result).items():
                self.assertLessEqual(len(value), nb.MEMORY_VALUE_LIMIT, (name, value))
            checked += 1
        self.assertGreater(checked, 1000)


class WordingTests(unittest.TestCase):
    def test_complete_claims_are_caught(self):
        for text in (
            "In total you spent $412.10 on your card in March.",
            "That's all of your March transactions.",
            "Here are all the transactions for March.",
            "Your March total is $412.10.",
            "You spent $412.10 on the card.",
            "Altogether, 13 transactions.",
        ):
            with self.subTest(text=text):
                self.assertTrue(nb.complete_claims(text))

    def test_partial_and_hedged_language_passes(self):
        for text in (
            "This is a partial result: 13 transactions so far, and no total for the month yet.",
            "I haven't read all of your transactions yet.",
            "Would you like the complete list?",
            "Once the search is complete I can give you the total.",
            "So far, the transactions shown add up to $412.10.",
        ):
            with self.subTest(text=text):
                self.assertEqual(nb.complete_claims(text), [])

    def test_statement_claims_need_a_search_total(self):
        self.assertTrue(nb.statement_claims("Your March statement balance is $2,600.04.", ["$2,600.04"]))
        self.assertFalse(nb.statement_claims("That $2,600.04 is not your statement balance.", ["$2,600.04"]))
        self.assertFalse(nb.statement_claims("Your statement balance was $2,914.37.", ["$2,600.04"]))

    def test_case_build_metrics_use_the_same_patterns(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        metrics = spec["bot_text_metrics"]
        self.assertEqual(metrics["complete_claim"]["pattern"], nb.COMPLETE_CLAIM_PATTERN)
        self.assertEqual(metrics["complete_claim"]["unless_before"], nb.COMPLETE_HEDGE_PATTERN)


class ToolSurfaceTests(unittest.TestCase):
    """The model passes the caller's words and references, never a fact, a range, a total or a customer id."""

    ALLOWED = {
        "search_transactions": ["period", "statuses", "account", "merchant", "context"],
        "continue_search": ["search_ref", "context"],
        "load_caller_profile": ["context"],
        "get_statement": ["account", "month", "context"],
    }

    def test_tool_parameters(self):
        found = {}
        for path in (PROJECT / "skills" / "transaction_search" / "tools.py", PROJECT / "tools" / "northgate_history.py"):
            for node in ast.parse(path.read_text()).body:
                if isinstance(node, ast.AsyncFunctionDef) and any(
                        isinstance(d, ast.Call) and getattr(d.func, "id", "") == "tool" for d in node.decorator_list):
                    found[node.name] = [a.arg for a in node.args.args]
        self.assertEqual(found, self.ALLOWED)


try:
    import hooks  # noqa: E402

    HAVE_RASA = True
except ImportError:  # bare python3 without the project venv
    HAVE_RASA = False


@unittest.skipUnless(HAVE_RASA, "needs rasa (make proof-full)")
class OutputHookTests(unittest.TestCase):
    def setUp(self):
        hooks._searches.clear()
        hooks._retries.clear()

    def _tool(self, name, value, sender="s1"):
        from rasa.mantle.hooks import ToolResultPayload

        # The engine passes the result as serialized JSON text, as dispatched.
        asyncio.run(hooks.remember_searches(
            ToolResultPayload(sender_id=sender, tool_name=name, arguments={}, value=json.dumps(value))))

    def _model(self, text, sender="s1"):
        from rasa.mantle.hooks import ModelResponsePayload

        return asyncio.run(hooks.guard_search_scope(ModelResponsePayload(sender_id=sender, text=text)))

    def test_partial_total_retries_then_states_the_search(self):
        from rasa.mantle.hooks import RetryModel

        service, partial = search(["posted rewards card March 2026"], "March 2026", "posted", "rewards card")
        self._tool("search_transactions", partial)
        for _ in range(2):
            with self.assertRaises(RetryModel):
                self._model("In total you spent $700.00 on the card in March.")
        replaced = self._model("In total you spent $700.00 on the card in March.")
        self.assertIn("partial", replaced.text)
        self.assertIn(partial["search_ref"], replaced.text)

    def test_complete_search_may_be_totalled(self):
        service, partial = search(["posted rewards card March 2026"], "March 2026", "posted", "rewards card")
        self._tool("search_transactions", partial)
        self._tool("continue_search", nb.continue_search(service, ELENA, partial["search_ref"]))
        text = "In total you spent $819.31 on the card in March."
        self.assertEqual(self._model(text).text, text)

    def test_search_total_called_a_statement_balance_is_retried(self):
        from rasa.mantle.hooks import RetryModel

        _, result = search(["posted checking March 2026"], "March 2026", "posted", "checking")
        self._tool("search_transactions", result)
        with self.assertRaises(RetryModel):
            self._model(f"Your March statement balance is {result['total_debits']}.")


if __name__ == "__main__":
    unittest.main()
