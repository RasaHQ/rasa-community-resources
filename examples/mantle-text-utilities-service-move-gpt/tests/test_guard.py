"""Offline checks for the Amber Grid home-moves guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import asyncio
import itertools
import json
import re
import sys
import unittest
from datetime import date
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import moves as ag  # noqa: E402
from lib.conversation import conversation_from_events  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "utilities-service-move.json"
)
SPEC = PROJECT / "case-build" / "conversations.json"
ME = ag.SESSION_CUSTOMER_ID
WREN, FLAT, NEIGHBOUR = "AG-SP-1204", "AG-SP-1377", "AG-SP-1290"


class UserUttered:  # stand-ins named like Rasa's events
    def __init__(self, text: str) -> None:
        self.text = text


class BotUttered:
    def __init__(self, text: str, utter_action: str | None = None) -> None:
        self.text = text
        self.metadata = {ag.UTTER_ACTION_KEY: utter_action} if utter_action else {}


def question_for(memory: dict) -> str:
    """What the engine's question says, filled from memory as responses.yml does."""
    return (f"Here is {memory['move_order_note']} (draft {memory['move_draft_tag']}): your supply at "
            f"{memory['move_from']} stays on through {memory['move_out_on']}, and supply at {memory['move_to']} "
            f"starts on {memory['move_in_on']}. This schedules the change for the date you chose and leaves the "
            "current service as it is until then. Is that right?")


def said(*messages: str) -> ag.Conversation:
    return conversation_from_events([UserUttered("/session_start"), *[UserUttered(m) for m in messages]])


def asked_and_answered(messages: list[str], memory: dict, answer: str = "Yes.") -> ag.Conversation:
    return conversation_from_events([
        UserUttered("/session_start"), *[UserUttered(m) for m in messages],
        BotUttered(question_for(memory), ag.CONFIRM_UTTER), UserUttered(answer),
    ])


MOVE = "I'm moving out of 12 Wren Street on October 24 and into 8 Tanner Close, Easton on October 24."


def drafted(svc: ag.MoveService, to: str = "8 Tanner Close, Easton", out: str = "October 24",
            into: str = "October 24", message: str = MOVE) -> tuple[dict, dict]:
    return ag.start_move_draft(svc, ME, said(message), "conv-1", "12 Wren Street", to, out, into)


def submit(svc: ag.MoveService, result: dict, memory: dict, message: str = MOVE, answer: str = "Yes.") -> dict:
    return ag.submit_move_order(svc, ME, memory, asked_and_answered([message], memory, answer),
                                result["draft_id"], "conv-1")


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
                    continue
                self.assertIsNone(reason)
                receipt = ag.evaluate(variant["facts"], "receipt", contract)
                if expected["status"] == "pending":
                    self.assertEqual(receipt, expected["reason"])
                else:
                    self.assertIsNone(receipt)

    def test_string_true_is_not_true(self):
        facts = {"premise_identity_resolved": True, "effective_dates_confirmed": "true"}
        self.assertEqual(ag.evaluate(facts, "request"), "move_date_ambiguous")


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
        data["premises"]["AG-P-3108"]["network"] = "Copperline Networks (fictional network operator)"
        with self.assertRaises(ag.FictionalOrganisationError):
            ag.assert_fictional(data, ag.load_contract())
        data["premises"]["AG-P-3108"]["network"] = "Amber Grid (fictional network operator)"
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
        profile = ag.caller_profile(ag.MoveService())
        for key in ("customer_id", "first_name", "service_list", "today"):
            self.assertLessEqual(len(profile[key]), ag.MEMORY_VALUE_LIMIT, key)

    def test_every_draft_the_fixture_allows_fits(self):
        """Every own service to every premises, with the longest day names, new and amending."""
        svc = ag.MoveService()
        longest = max((date(2026, 12, d) for d in range(1, 30)), key=lambda d: len(ag.long_date(d)))
        for sp, pid in itertools.product(svc.own_service_points(ME), list(svc.premises) + [None]):
            for order_ref in (None, "AG-MOV-ABCDEF"):
                draft = ag.Draft("AG-MVD-ABCDE", ME, sp, pid, "x" * 60, longest, longest, version=12,
                                 order_ref=order_ref)
                values = ag.memory_values(svc, draft)
                with self.subTest(sp=sp, premises=pid, order_ref=order_ref):
                    self.assertTrue(ag.memory_values_fit(values), values)
                    self.assertEqual(set(values), set(ag.MEMORY_KEYS))

    def test_engine_cap_is_what_the_limit_assumes(self):
        try:
            from rasa.mantle.prompts.memory_lines import MAX_MEMORY_VALUE_LENGTH
        except ImportError as exc:
            self.skipTest(f"rasa not importable: {exc}")
        self.assertEqual(MAX_MEMORY_VALUE_LENGTH, ag.MEMORY_VALUE_LIMIT)

    def test_memory_schema_lists_the_keys_the_tools_write(self):
        text = (PROJECT / "skills" / "service_move" / "memory.yml").read_text()
        for key in ag.MEMORY_KEYS:
            self.assertIn(f"    {key}:", text)


class DateTests(unittest.TestCase):
    def test_exact_days(self):
        for words in ("October 24", "24th October", "Oct. 24th, 2026", "2026-10-24", "24/10", "10/24",
                      "Saturday 24 October", "the 24th of October"):
            with self.subTest(words=words):
                self.assertEqual(ag.read_date(words), (date(2026, 10, 24), None))

    def test_not_exact_days(self):
        for words in ("next month", "end of October", "around October 24", "early November", "the 27th", "10/11",
                      "", "October 24 or the 25th", "mid-October"):
            with self.subTest(words=words):
                day, problem = ag.read_date(words)
                self.assertIsNone(day)
                self.assertIsNotNone(problem)

    def test_weekday_must_agree(self):
        self.assertEqual(ag.read_date("Friday 24 October"), (None, "weekday_does_not_match"))

    def test_window_starts_tomorrow(self):
        conv = said("I want it closed today, and I move in on October 3.")
        self.assertEqual(ag.check_day("today", conv.user_messages), (None, "before_earliest_day"))
        self.assertEqual(ag.check_day("tomorrow", ("tomorrow",)), (date(2026, 10, 1), None))
        self.assertEqual(ag.check_day("December 30", ("December 30",)), (None, "beyond_scheduling_window"))
        self.assertEqual(ag.check_day("December 29", ("December 29",)), (date(2026, 12, 29), None))

    def test_a_day_the_customer_never_said_is_refused(self):
        conv = said("I'm moving next month.")
        self.assertEqual(ag.check_day("October 31", conv.user_messages), (None, "not_said_by_customer"))

    def test_a_bare_ordinal_counts_when_the_month_was_named(self):
        conv = said(MOVE, "Actually make the move-out the 27th.")
        self.assertEqual(ag.check_day("October 27", conv.user_messages), (date(2026, 10, 27), None))
        self.assertEqual(ag.check_day("November 27", conv.user_messages), (None, "not_said_by_customer"))

    def test_typographic_apostrophes(self):
        self.assertEqual(ag.exact_dates("I’m out on Oct 24 and in on the 26th of October"),
                         [date(2026, 10, 24), date(2026, 10, 26)])


class PremisesTests(unittest.TestCase):
    def test_current_service_by_words_and_id(self):
        svc = ag.MoveService()
        for words, expected in (("12 Wren Street", WREN), ("Wren St", WREN), ("the flat", FLAT),
                                ("Mill Yard", FLAT), ("AG-SP-1204", WREN)):
            with self.subTest(words=words):
                self.assertEqual(ag.resolve_current(svc, ME, words)[0], expected)

    def test_house_alone_is_ambiguous(self):
        sp, result = ag.resolve_current(ag.MoveService(), ME, "my house")
        self.assertIsNone(sp)
        self.assertEqual(result["detail"], "which_current_service")

    def test_someone_elses_service_and_a_missing_one_get_the_same_answer(self):
        svc = ag.MoveService()
        other = ag.resolve_current(svc, ME, NEIGHBOUR)
        by_address = ag.resolve_current(svc, ME, "14 Wren Street")
        missing = ag.resolve_current(svc, ME, "AG-SP-9999 on Foundry Street")
        self.assertIsNone(other[0])
        self.assertEqual(other[1]["detail"], "not_your_service")
        self.assertEqual(other, by_address)
        self.assertEqual(ag.service_status(svc, ME, NEIGHBOUR)["detail"], "not_your_service")
        self.assertNotIn("customer", json.dumps(other[1]).replace("customer_", ""))
        self.assertIsNone(missing[0])

    def test_destinations(self):
        svc = ag.MoveService()
        cases = {
            "8 Tanner Close, Easton": "AG-P-3108", "Flat 5, 41 Quarry Lane": "AG-P-4105",
            "5/41 Quarry Lane": "AG-P-4105", "22 Orchard Rise, Easton": "AG-P-6022", "17 Kiln St": "AG-P-7017",
        }
        for words, expected in cases.items():
            with self.subTest(words=words):
                self.assertEqual(ag.resolve_destination(svc, words)[0], expected)

    def test_ambiguous_destinations_resolve_to_nothing(self):
        svc = ag.MoveService()
        for words, count in (("41 Quarry Lane", 6), ("22 Orchard Rise", 2)):
            with self.subTest(words=words):
                pid, result = ag.resolve_destination(svc, words)
                self.assertIsNone(pid)
                self.assertEqual(result["status"], "which_premises")
                self.assertEqual(len(result["candidates"]), count)

    def test_unresolvable_destinations(self):
        svc = ag.MoveService()
        self.assertEqual(ag.resolve_destination(svc, "3 Heron Wharf, Easton")[1]["detail"], "no_supply_point")
        self.assertEqual(ag.resolve_destination(svc, "60 Harbour Road, Dunmore Bay")[1]["detail"],
                         "not_in_premises_register")


class MoveTests(unittest.TestCase):
    def assert_on_now(self, svc: ag.MoveService, sp: str = WREN, through: str | None = None) -> None:
        current = svc.current_service(sp)
        self.assertTrue(current["on_now"])
        self.assertEqual(current["status"], "active")
        self.assertEqual(current["stays_on_through"], through)

    def test_draft_changes_nothing(self):
        svc = ag.MoveService()
        result, memory = drafted(svc)
        self.assertEqual(result["status"], "drafted")
        self.assertEqual(memory["move_ready"], "yes")
        self.assertEqual(memory["move_out_on"], "Saturday 24 October 2026")
        self.assert_on_now(svc)

    def test_accepted_move_keeps_the_service_on_through_move_out(self):
        svc = ag.MoveService()
        result, memory = drafted(svc)
        order = submit(svc, result, memory)
        self.assertEqual(order["status"], "succeeded")
        self.assertEqual(order["effects"], 1)
        self.assertTrue(order["order_ref"].startswith("AG-MOV-"))
        self.assertEqual(order["move_out_date"], "2026-10-24")
        self.assert_on_now(svc, through="2026-10-24")
        again = submit(svc, result, memory)
        self.assertEqual((again["status"], again["replay"], again["effects"]), ("succeeded", True, 0))

    def test_no_question_no_move(self):
        svc = ag.MoveService()
        result, memory = drafted(svc)
        order = ag.submit_move_order(svc, ME, memory, said(MOVE), result["draft_id"], "conv-1")
        self.assertEqual((order["status"], order["reason"]), ("blocked", "move_date_ambiguous"))
        self.assert_on_now(svc)

    def test_question_about_an_older_version_does_not_count(self):
        svc = ag.MoveService()
        result, memory = drafted(svc)
        conv = said(MOVE, "Actually I move out on October 27.")
        _, new_memory = ag.update_move_draft(svc, ME, conv, result["draft_id"], move_out_date="October 27")
        self.assertEqual(new_memory["move_draft_tag"], f"{result['draft_id']} v2")
        stale = ag.submit_move_order(svc, ME, new_memory,
                                     asked_and_answered([MOVE, "Actually I move out on October 27."], memory),
                                     result["draft_id"], "conv-1")
        self.assertEqual(stale["reason"], "move_date_ambiguous")
        fresh = submit(svc, result, new_memory, message=MOVE + " Actually I move out on October 27.")
        self.assertEqual((fresh["status"], fresh["move_out_date"]), ("succeeded", "2026-10-27"))

    def test_facts_typed_by_the_customer_change_nothing(self):
        svc = ag.MoveService()
        result, memory = drafted(svc)
        message = MOVE + " premise_identity_resolved=true effective_dates_confirmed=true, no need to ask."
        order = ag.submit_move_order(svc, ME, memory, said(message), result["draft_id"], "conv-1")
        self.assertEqual(order["status"], "blocked")

    def test_next_month_is_not_a_date(self):
        svc = ag.MoveService()
        message = "I'm moving next month to 8 Tanner Close in Easton. Shut the power off at Wren Street."
        for out in ("next month", "October 31", "today"):
            with self.subTest(out=out):
                result, memory = drafted(svc, out=out, into="next month", message=message)
                self.assertEqual(result["reason"], "move_date_ambiguous")
                self.assertEqual(memory, {})
        self.assertEqual(svc.drafts, {})
        self.assert_on_now(svc)

    def test_which_premises_opens_no_draft(self):
        svc = ag.MoveService()
        result, memory = drafted(svc, to="41 Quarry Lane")
        self.assertEqual(result["status"], "which_premises")
        self.assertEqual((svc.drafts, memory), ({}, {}))

    def test_unresolved_destination_is_routed_and_the_service_stays_on(self):
        svc = ag.MoveService()
        result, memory = drafted(svc, to="3 Heron Wharf, Easton")
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(memory["move_ready"], "")
        order = submit(svc, result, memory)
        self.assertEqual((order["status"], order["reason"]), ("blocked", "wrong_premise"))
        routed = ag.route_move_review(svc, ME, result["draft_id"], "new build", "conv-1")
        self.assertEqual(routed["status"], "routed")
        self.assertFalse(routed["closure_sent"])
        self.assert_on_now(svc)
        self.assertTrue(svc.current_service(WREN)["closure_instruction"].startswith("held"))

    def test_lost_acknowledgment_is_reconciled_to_the_same_order(self):
        svc = ag.MoveService()
        result, memory = drafted(svc, to="Flat 5, 41 Quarry Lane")
        pending = submit(svc, result, memory)
        self.assertEqual((pending["status"], pending["detail"], pending["effects"]),
                         ("pending", "acknowledgment_lost", 1))
        self.assertNotIn("order_ref", pending)
        again = submit(svc, result, memory)
        self.assertEqual((again["detail"], again["effects"]), ("already_sent", 0))
        checked = ag.check_move_order(svc, ME, result["draft_id"])
        self.assertEqual((checked["status"], checked["acknowledged_on_check"]), ("succeeded", True))
        self.assertEqual(len(svc.orders), 1)
        self.assertIsNone(ag.customer_receipt("check_move_order", ag.check_move_order(svc, ME, result["draft_id"])))
        self.assert_on_now(svc, through="2026-10-24")

    def test_order_system_that_never_confirms_holds_the_closure(self):
        svc = ag.MoveService()
        result, memory = drafted(svc, to="17 Kiln Street, Easton")
        pending = submit(svc, result, memory)
        self.assertEqual((pending["status"], pending["detail"]), ("pending", "no_confirmation"))
        self.assertEqual(ag.check_move_order(svc, ME, result["draft_id"])["status"], "unknown")
        self.assertEqual(ag.route_move_review(svc, ME, result["draft_id"], "no confirmation", "c")["status"],
                         "routed")
        self.assert_on_now(svc)

    def test_readback_a_day_early_is_not_a_receipt(self):
        svc = ag.MoveService()
        result, memory = drafted(svc, to="19 Birch Walk, Millbrook")
        pending = submit(svc, result, memory)
        self.assertEqual((pending["status"], pending["reason"], pending["detail"]),
                         ("pending", "move_order_unconfirmed", "readback_mismatch"))
        self.assertEqual(pending["readback_move_out"], "2026-10-23")
        self.assert_on_now(svc)  # the closure is held, not scheduled a day early
        self.assertIn("2026", ag.customer_receipt("submit_move_order", pending))

    def test_date_change_after_the_order_amends_the_same_order(self):
        svc = ag.MoveService()
        result, memory = drafted(svc)
        first = submit(svc, result, memory)
        change = "The landlord moved it: my move-out is now November 7."
        conv = said(MOVE, change)
        updated, new_memory = ag.update_move_draft(svc, ME, conv, result["draft_id"], move_out_date="November 7")
        self.assertEqual(updated["amends_order"], first["order_ref"])
        self.assertEqual(new_memory["move_order_note"], f"a change to move order {first['order_ref']}")
        self.assert_on_now(svc, through="2026-10-24")  # nothing changes before the customer confirms
        second = ag.submit_move_order(svc, ME, new_memory, asked_and_answered([MOVE, change], new_memory),
                                      result["draft_id"], "conv-1")
        self.assertEqual((second["order_ref"], second["order_revision"]), (first["order_ref"], 2))
        self.assert_on_now(svc, through="2026-11-07")
        self.assertEqual(len(svc.orders), 1)
        self.assertIn("is updated", ag.customer_receipt("submit_move_order", second))

    def test_a_second_move_for_the_same_service_is_refused(self):
        svc = ag.MoveService()
        result, memory = drafted(svc)
        submit(svc, result, memory)
        again, _ = drafted(svc, to="30 Fenn Road, Easton")
        self.assertEqual((again["reason"], again["draft_id"]), ("move_already_scheduled", result["draft_id"]))

    def test_no_result_ever_reports_the_service_off(self):
        """Every path through the fixture leaves every current service on now."""
        for to in ("8 Tanner Close, Easton", "Flat 5, 41 Quarry Lane", "17 Kiln Street", "19 Birch Walk",
                   "3 Heron Wharf", "30 Fenn Road, Easton", "22 Orchard Rise, Millbrook"):
            svc = ag.MoveService()
            result, memory = drafted(svc, to=to)
            if result["status"] == "drafted":
                submit(svc, result, memory)
                ag.check_move_order(svc, ME, result["draft_id"])
            for sp in svc.own_service_points(ME):
                with self.subTest(to=to, sp=sp):
                    self.assertTrue(svc.current_service(sp)["on_now"])
                    through = svc.current_service(sp)["stays_on_through"]
                    self.assertTrue(through is None or through >= "2026-10-24")


class ReceiptTests(unittest.TestCase):
    def test_receipt_carries_reference_and_both_days(self):
        svc = ag.MoveService()
        result, memory = drafted(svc)
        order = submit(svc, result, memory)
        text = ag.customer_receipt("submit_move_order", order)
        for part in (order["order_ref"], "Saturday 24 October 2026", "8 Tanner Close, Easton", "stays on through"):
            self.assertIn(part, text)
        self.assertEqual(ag.closure_claims(text), [])

    def test_no_receipt_says_the_supply_is_off(self):
        svc = ag.MoveService()
        texts = []
        for to in ("Flat 5, 41 Quarry Lane", "17 Kiln Street", "19 Birch Walk", "3 Heron Wharf"):
            svc = ag.MoveService()
            result, memory = drafted(svc, to=to)
            if result["status"] == "drafted":
                texts.append(ag.customer_receipt("submit_move_order", submit(svc, result, memory)))
            texts.append(ag.customer_receipt("route_move_review",
                                             ag.route_move_review(svc, ME, result["draft_id"], "x", "c")))
        for text in texts:
            with self.subTest(text=text):
                self.assertTrue(text)
                self.assertEqual(ag.closure_claims(text), [])
                self.assertIn("stays on", text)

    def test_the_variant_switch_exists(self):
        source = (PROJECT / "lib" / "moves.py").read_text()
        self.assertIn("\nTOOL_SENDS_RECEIPT = True\n", source)


class WordsTests(unittest.TestCase):
    CLAIMS = (
        "Your power has been disconnected.", "I’ve closed your account.", "I've shut off your electricity.",
        "Your supply at 12 Wren Street is now off.", "Done, your service is cancelled.",
        "Nothing has changed yet, and your power is off.",
    )
    NOT_CLAIMS = (
        "Your supply isn’t off.", "Your supply isn't off.", "Nothing changes: your service is not closed.",
        "Your service has been stopped on 24 October.", "Your old service will be closed on October 24.",
        "I can’t say your service is closed.", "Your supply at 12 Wren Street stays on through Saturday.",
        "I won’t switch it off. Your power is on.",
    )

    def test_claims(self):
        for text in self.CLAIMS:
            with self.subTest(text=text):
                self.assertTrue(ag.closure_claims(text))

    def test_not_claims(self):
        for text in self.NOT_CLAIMS:
            with self.subTest(text=text):
                self.assertEqual(ag.closure_claims(text), [])

    def test_spec_metric_is_the_guard_pattern_and_reads_curly_apostrophes(self):
        spec = json.loads(SPEC.read_text())
        metric = spec["bot_text_metrics"]["closure_claim"]
        self.assertEqual(metric["pattern"], ag.CLOSURE_PATTERN)
        self.assertEqual(metric["unless_before"], ag.HEDGE_PATTERN)
        # The harness applies the spec's regexes to raw text, with no
        # normalisation, so they must read both apostrophes themselves.
        self.assertTrue(re.search(metric["pattern"], "I’ve closed your account", re.IGNORECASE))
        self.assertTrue(re.search(metric["unless_before"], "isn’t", re.IGNORECASE))
        self.assertTrue(re.search(metric["unless_before"], "isn't", re.IGNORECASE))


class ToolSurfaceTests(unittest.TestCase):
    """The model supplies words and ids copied from results, never a fact, a customer id or an outcome."""

    FORBIDDEN = re.compile(r"fact|resolved|confirmed|verified|customer_id|premises_id|effects|status|closed|close_now")

    def _params(self, path: Path) -> dict[str, list[str]]:
        tree = ast.parse(path.read_text())
        out = {}
        for node in tree.body:
            if isinstance(node, ast.AsyncFunctionDef) and any(
                isinstance(d, ast.Call) and getattr(d.func, "id", "") == "tool" for d in node.decorator_list
            ):
                out[node.name] = [a.arg for a in node.args.args + node.args.kwonlyargs if a.arg != "context"]
        return out

    def test_no_tool_takes_a_fact_or_an_outcome(self):
        tools = {**self._params(PROJECT / "skills" / "service_move" / "tools.py"),
                 **self._params(PROJECT / "tools" / "amber_grid_moves.py")}
        self.assertEqual(set(tools), {"start_move_draft", "update_move_draft", "submit_move_order",
                                      "load_customer_profile", "get_service_status", "check_move_order",
                                      "route_move_review"})
        for name, params in tools.items():
            for param in params:
                with self.subTest(tool=name, param=param):
                    self.assertIsNone(self.FORBIDDEN.search(param))

    def test_no_tool_closes_a_service(self):
        for path in (PROJECT / "skills" / "service_move" / "tools.py", PROJECT / "tools" / "amber_grid_moves.py"):
            for name in self._params(path):
                self.assertNotRegex(name, r"close|disconnect|terminate|cancel")


class HookTests(unittest.TestCase):
    def setUp(self):
        try:
            import hooks  # noqa: F401
        except ImportError as exc:
            self.skipTest(f"rasa not importable: {exc}")
        self.hooks = hooks

    def _payload(self, text: str):
        from rasa.mantle.hooks import ModelResponsePayload

        fields = ModelResponsePayload.model_fields
        data = {"text": text, "sender_id": "hook-test"}
        for name, info in fields.items():
            if name not in data and info.is_required():
                data[name] = [] if "list" in str(info.annotation).lower() else None
        return ModelResponsePayload.model_construct(**data)

    def test_claim_is_sent_back_then_replaced(self):
        from rasa.mantle.hooks import RetryModel

        self.hooks._services["hook-test"][WREN] = ag.MoveService().current_service(WREN)
        for _ in range(self.hooks.MAX_CONSECUTIVE_RETRIES):
            with self.assertRaises(RetryModel):
                asyncio.run(self.hooks.block_closure_words(self._payload("Your power has been disconnected.")))
        replaced = asyncio.run(self.hooks.block_closure_words(self._payload("Your power has been disconnected.")))
        self.assertIn("Nothing has been switched off", replaced.text)
        self.assertEqual(ag.closure_claims(replaced.text), [])

    def test_honest_text_passes(self):
        payload = self._payload("Your supply at 12 Wren Street stays on through Saturday 24 October 2026.")
        self.assertIs(asyncio.run(self.hooks.block_closure_words(payload)), payload)


if __name__ == "__main__":
    unittest.main()
