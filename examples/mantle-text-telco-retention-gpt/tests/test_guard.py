"""Offline checks for the Juniper Mobile retention guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import retention as jm  # noqa: E402
from lib.conversation import conversation_from_events  # noqa: E402

CASEBOOK_CONTRACT = PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "telco-retention.json"
SPEC = PROJECT / "case-build" / "conversations.json"
ME = jm.SESSION_CUSTOMER_ID
MOBILE, FIBRE, TABLET, NEIGHBOUR = "JM-MOB-318842", "JM-FIB-204419", "JM-MOB-318977", "JM-FIB-204420"


class UserUttered:  # stand-ins named like Rasa's events
    def __init__(self, text: str) -> None:
        self.text = text


class BotUttered:
    def __init__(self, text: str, utter_action: str | None = None) -> None:
        self.text = text
        self.metadata = {jm.UTTER_ACTION_KEY: utter_action} if utter_action else {}


def question_for(memory: dict) -> str:
    """What the engine's question says, filled from memory as skills/retention/responses.yml does."""
    return (f"Authorized offer {memory['offer_id']} for your {memory['offer_service']}: {memory['offer_terms']}. "
            f"{memory['offer_exit_note']} You can review this authorized option or continue to cancellation. Which "
            "would you prefer?")


def said(*messages: str) -> jm.Conversation:
    return conversation_from_events([UserUttered("/session_start"), *[UserUttered(m) for m in messages]])


def asked(messages: list[str], memory: dict, answer: str | None = "I'll take the offer.") -> jm.Conversation:
    events = [UserUttered("/session_start"), *[UserUttered(m) for m in messages],
              BotUttered(question_for(memory), jm.CONFIRM_UTTER)]
    if answer is not None:
        events.append(UserUttered(answer))
    return conversation_from_events(events)


CANCEL = "I want to cancel my mobile, it's too expensive now the contract has ended."


def cancel_then_offer(desk: jm.RetentionDesk, message: str = CANCEL, service: str = "my mobile") -> tuple[dict, dict]:
    jm.record_cancellation_request(desk, ME, "conv-1", service)
    return jm.get_retention_offer(desk, ME, said(message), "conv-1", service)


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), jm.load_contract(),
                         "lib/fixtures/case-contract.json has drifted from the casebook lab")

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = jm.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                reason = jm.evaluate(variant["facts"], "request", contract)
                if expected["status"] == "blocked":
                    self.assertEqual(reason, expected["reason"])
                else:
                    self.assertIsNone(reason)
                    self.assertIsNone(jm.evaluate(variant["facts"], "receipt", contract))

    def test_string_true_is_not_true(self):
        facts = {"contact_permission_current": True, "exit_path_available": "true", "offer_terms_authorized": True}
        self.assertEqual(jm.evaluate(facts, "request"), "cancellation_exit_blocked")


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_casebooks_fictional_provider(self):
        jm.assert_fictional(jm.load_data(), jm.load_contract())
        self.assertEqual(jm.ORGANISATION, jm.load_contract()["organisation"])
        self.assertEqual(jm.allowed_organisations(jm.load_contract()), frozenset({"Juniper Mobile"}))

    def test_any_other_organisation_is_refused_even_when_marked_fictional(self):
        data = jm.load_data()
        data["organisation"] = "Kestrel Telecom (fictional mobile provider)"
        with self.assertRaises(jm.FictionalOrganisationError):
            jm.assert_fictional(data, jm.load_contract())

    def test_nested_organisation_fields_are_checked(self):
        data = jm.load_data()
        data["offers"]["JM-OFR-M12"]["operator"] = "Kestrel Networks (fictional network operator)"
        with self.assertRaises(jm.FictionalOrganisationError):
            jm.assert_fictional(data, jm.load_contract())
        data["offers"]["JM-OFR-M12"]["operator"] = "Juniper Mobile (fictional network operator)"
        jm.assert_fictional(data, jm.load_contract())

    def test_unmarked_or_undeclared_data_is_refused(self):
        for key, value in (("organisation", "Juniper Mobile"), ("note", "Sample data.")):
            data = jm.load_data()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(jm.FictionalOrganisationError):
                jm.assert_fictional(data, jm.load_contract())


class MemoryLimitTests(unittest.TestCase):
    """Mantle cuts a memory value at 100 characters in the prompt, silently."""

    def test_project_memory_values_fit(self):
        profile = jm.caller_profile(jm.RetentionDesk())
        for key in ("customer_id", "first_name", "service_list", "today"):
            self.assertLessEqual(len(profile[key]), jm.MEMORY_VALUE_LIMIT, key)

    def test_every_offer_in_the_fixture_fits_with_and_without_a_cancellation(self):
        for oid in jm.load_data()["offers"]:
            for cancelled in (False, True):
                desk = jm.RetentionDesk()
                if cancelled:
                    desk.cancellations[desk.offers[oid]["service"]] = {"reference": "JM-CXL-ABCDEF"}
                values = jm.memory_values(desk, oid)
                with self.subTest(offer=oid, cancelled=cancelled):
                    self.assertTrue(jm.memory_values_fit(values), values)
                    self.assertEqual(set(values), set(jm.MEMORY_KEYS))

    def test_engine_cap_is_what_the_limit_assumes(self):
        try:
            from rasa.mantle.prompts.memory_lines import MAX_MEMORY_VALUE_LENGTH
        except ImportError as exc:
            self.skipTest(f"rasa not importable: {exc}")
        self.assertEqual(MAX_MEMORY_VALUE_LENGTH, jm.MEMORY_VALUE_LIMIT)

    def test_memory_schema_lists_the_keys_the_tools_write(self):
        text = (PROJECT / "skills" / "retention" / "memory.yml").read_text()
        for key in jm.MEMORY_KEYS:
            self.assertIn(f"    {key}:", text)

    def test_question_template_uses_the_memory_keys(self):
        text = (PROJECT / "skills" / "retention" / "responses.yml").read_text()
        for key in ("offer_id", "offer_service", "offer_terms", "offer_exit_note"):
            self.assertIn("{" + key + "}", text)
        self.assertIn(jm.EXIT_WORDS, " ".join(text.split()))


class RefusalTests(unittest.TestCase):
    REFUSALS = (
        "stop", "Stop.", "/stop", "No more offers, please.", "I'm not interested.", "No thanks.",
        "Just cancel it.", "Continue to cancellation.", "I don’t want any offers.", "I don't want any more deals",
        "Don’t try to keep me.", "Stop contacting me.", "Please stop, I want to cancel.", "Leave me alone.",
        "I’d rather cancel.", "I just want out.", "no offers, just cancel my mobile", "Stop sending me offers.",
        "Enough discounts.", "go ahead and cancel",
    )
    NOT_REFUSALS = (
        "I want to cancel my mobile.", "What can you offer me to stay?", "Stop charging me twice for roaming.",
        "Yes, I'll take the offer.", "Is that price with 5G?", "Cancel my tablet data SIM please.",
        "No problem, go on.", "My colleague said you do discounts.",
    )

    def test_refusals(self):
        for text in self.REFUSALS:
            with self.subTest(text=text):
                self.assertIsNotNone(jm.refusal_in(text))

    def test_not_refusals(self):
        for text in self.NOT_REFUSALS:
            with self.subTest(text=text):
                self.assertIsNone(jm.refusal_in(text))

    def test_telegram_stop_command_is_the_customers_word(self):
        conv = said("I want to cancel my mobile.", "/stop")
        self.assertEqual(conv.user_messages, ("I want to cancel my mobile.", "/stop"))
        self.assertIsNotNone(conv.refusal())

    def test_bare_no_to_the_question_declines_it(self):
        desk = jm.RetentionDesk()
        _, memory = cancel_then_offer(desk)
        self.assertTrue(jm.offer_declined(asked([CANCEL], memory, "No.")))
        self.assertFalse(jm.offer_declined(asked([CANCEL], memory, "No problem, I'll take it.")))
        self.assertFalse(jm.offer_declined(asked([CANCEL], memory, None)))

    def test_cancel_intent(self):
        for text in ("Cancel my mobile", "I want my PAC code", "close my broadband", "I’m cancelling"):
            with self.subTest(text=text):
                self.assertTrue(jm.asks_to_cancel(text))
        for text in ("What can you offer me?", "I'm thinking about it", "How much am I paying?"):
            with self.subTest(text=text):
                self.assertFalse(jm.asks_to_cancel(text))


class WordsTests(unittest.TestCase):
    PROMPTS = (
        "Before you go, I can offer you £18 a month.", "How about 20% off for six months?",
        "I could give you a better deal if you stay.", "Would you consider a loyalty discount?",
        "We’d like to offer you three months free.", "There is also an offer on the fibre.",
    )
    NOT_PROMPTS = (
        "Understood. I won’t make any more offers.", "Your cancellation request is recorded.",
        "I can’t offer 60% off: there is no such offer.", "No other offer applies.",
        "You are paying £26 a month on Unlimited 5G.",
    )

    def test_prompts(self):
        for text in self.PROMPTS:
            with self.subTest(text=text):
                self.assertTrue(jm.offer_prompts(text))

    def test_not_prompts(self):
        for text in self.NOT_PROMPTS:
            with self.subTest(text=text):
                self.assertEqual(jm.offer_prompts(text), [])

    def test_invented_terms(self):
        tool = json.dumps({"terms": "Unlimited 5G at £18 a month for 12 months, then £26 a month"}, ensure_ascii=False)
        self.assertEqual(jm.invented_terms("I can offer you £18 a month for 12 months.", [tool]), [])
        self.assertEqual(jm.invented_terms("I could do £12 a month for you.", [tool]), ["£12"])
        self.assertEqual(jm.invented_terms("How about 50% off instead?", [tool]), ["50%"])
        self.assertEqual(jm.invented_terms("I can’t match 50% off.", [tool]), [])

    def test_closure_claims(self):
        for text in ("Your mobile has been cancelled.", "I’ve closed your account.", "Done, your plan is terminated.",
                     "Your tablet data SIM is now cancelled."):
            with self.subTest(text=text):
                self.assertTrue(jm.closure_claims(text))
        for text in ("Your mobile is not cancelled yet.", "Your request is recorded; the account isn’t closed.",
                     "Your plan will be closed on the date the team confirms.", "Your cancellation request is recorded."):
            with self.subTest(text=text):
                self.assertEqual(jm.closure_claims(text), [])


class ServiceTests(unittest.TestCase):
    def test_resolution(self):
        desk = jm.RetentionDesk()
        for words, expected in (("my mobile", MOBILE), ("the phone ending 4471", MOBILE), ("home fibre", FIBRE),
                                ("broadband at 3 Tanner Close", FIBRE), ("tablet data SIM", TABLET),
                                ("JM-MOB-318977", TABLET)):
            with self.subTest(words=words):
                self.assertEqual(jm.resolve_service(desk, ME, words)[0], expected)

    def test_ambiguous_asks_which(self):
        sid, result = jm.resolve_service(jm.RetentionDesk(), ME, "my SIM")
        self.assertIsNone(sid)
        self.assertEqual(result["status"], "which_service")

    def test_someone_elses_service_and_a_missing_one_get_the_same_answer(self):
        desk = jm.RetentionDesk()
        by_id = jm.resolve_service(desk, ME, NEIGHBOUR)
        by_address = jm.resolve_service(desk, ME, "the fibre at 5 Tanner Close")
        missing = jm.resolve_service(desk, ME, "the fibre at 9 Mill Road")
        self.assertEqual(by_id, by_address)
        self.assertEqual(by_id, missing)
        self.assertEqual(by_id[1]["detail"], "not_your_service")
        result = jm.record_cancellation_request(desk, ME, "c", NEIGHBOUR)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(desk.cancellations, {})


class FlowTests(unittest.TestCase):
    def test_cancel_offer_accept(self):
        desk = jm.RetentionDesk()
        cancellation = jm.record_cancellation_request(desk, ME, "conv-1", "my mobile")
        self.assertEqual((cancellation["status"], cancellation["account_closed"], cancellation["effects"]),
                         ("recorded", False, 0))
        result, memory = jm.get_retention_offer(desk, ME, said(CANCEL), "conv-1", "my mobile")
        self.assertEqual((result["status"], result["offer_id"]), ("offer", "JM-OFR-M12"))
        self.assertEqual(memory["offer_ready"], "yes")
        self.assertIn(cancellation["reference"], memory["offer_exit_note"])
        outcome, cleared = jm.accept_retention_offer(desk, ME, memory, asked([CANCEL], memory), "JM-OFR-M12", "conv-1")
        self.assertEqual((outcome["status"], outcome["effects"]), ("succeeded", 1))
        self.assertTrue(outcome["reference"].startswith("JM-RET-"))
        self.assertEqual(cleared["offer_ready"], "")
        self.assertEqual(desk.cancellations[MOBILE]["status"], "withdrawn_at_customer_choice")
        again, _ = jm.accept_retention_offer(desk, ME, memory, asked([CANCEL], memory), "JM-OFR-M12", "conv-1")
        self.assertEqual((again["replay"], again["effects"]), (True, 0))

    def test_asking_for_an_offer_without_cancelling_needs_no_intake(self):
        desk = jm.RetentionDesk()
        message = "My contract has ended. What would you offer me to stay on my mobile?"
        result, memory = jm.get_retention_offer(desk, ME, said(message), "c", "my mobile")
        self.assertEqual(result["status"], "offer")
        self.assertEqual(memory["offer_exit_note"], "Nothing changes unless you choose it.")

    def test_every_refusal_ends_offers_on_every_service(self):
        for refusal in RefusalTests.REFUSALS:
            desk = jm.RetentionDesk()
            conv = said(CANCEL, refusal)
            jm.record_cancellation_request(desk, ME, "c", "my mobile")
            for service in ("my mobile", "tablet data SIM"):
                result, memory = jm.get_retention_offer(desk, ME, conv, "c", service)
                with self.subTest(refusal=refusal, service=service):
                    self.assertEqual((result["status"], result["reason"]), ("blocked", "contact_withdrawn"))
                    self.assertEqual(memory["offer_ready"], "")

    def test_a_no_to_the_question_ends_offers(self):
        desk = jm.RetentionDesk()
        _, memory = cancel_then_offer(desk)
        conv = asked([CANCEL], memory, "No.")
        result, _ = jm.get_retention_offer(desk, ME, conv, "c", "my mobile")
        self.assertEqual((result["reason"], result["detail"]["contact"]), ("contact_withdrawn", "offer_declined"))

    def test_intake_comes_before_any_offer_when_the_customer_asked_to_cancel(self):
        desk = jm.RetentionDesk()
        result, memory = jm.get_retention_offer(desk, ME, said(CANCEL), "c", "my mobile")
        self.assertEqual((result["reason"], result["detail"]["exit"]),
                         ("cancellation_exit_blocked", "cancellation_request_not_recorded"))
        self.assertEqual(memory["offer_ready"], "")

    def test_withdrawn_on_record_blocks_and_pauses_the_campaign(self):
        desk = jm.RetentionDesk()
        message = "Cancel my home fibre please."
        cancellation = jm.record_cancellation_request(desk, ME, "c", "home fibre")
        self.assertEqual(cancellation["campaign_dispatch"]["campaign"], "paused for this account")
        result, _ = jm.get_retention_offer(desk, ME, said(message), "c", "home fibre")
        self.assertEqual((result["status"], result["reason"]), ("blocked", "contact_withdrawn"))
        self.assertEqual(desk.campaign["JM-ACC-5502"], "paused")
        self.assertIn("JM-ACC-5502", desk.reconciliations)

    def test_sales_route_blocks_offers_and_holds_the_cancellation_for_review(self):
        desk = jm.RetentionDesk()
        cancellation = jm.record_cancellation_request(desk, ME, "c", "tablet data SIM")
        self.assertEqual((cancellation["status"], cancellation["detail"]), ("recorded", "cancellation_route_goes_to_sales"))
        self.assertTrue(cancellation["review_ref"].startswith("JM-REV-"))
        self.assertNotIn("sales", cancellation["route"])
        result, _ = jm.get_retention_offer(desk, ME, said("Cancel the tablet SIM. What's your best deal first?"), "c",
                                           "tablet data SIM")
        self.assertEqual((result["reason"], result["detail"]["exit"]),
                         ("cancellation_exit_blocked", "cancellation_route_goes_to_sales"))

    def test_intake_is_never_gated_by_an_offer_rule(self):
        for service, message in (("home fibre", "stop, just cancel the fibre"), ("tablet data SIM", "cancel it"),
                                 ("my mobile", "no more offers, cancel my mobile")):
            desk = jm.RetentionDesk()
            with self.subTest(service=service):
                self.assertEqual(jm.record_cancellation_request(desk, ME, "c", service)["status"], "recorded")
                again = jm.record_cancellation_request(desk, ME, "c", service)
                self.assertEqual((again["replay"], again["effects"]), (True, 0))
                self.assertEqual(len(desk.cancellations), 1)

    def test_accept_needs_the_question_with_the_way_out(self):
        desk = jm.RetentionDesk()
        _, memory = cancel_then_offer(desk)
        unasked, _ = jm.accept_retention_offer(desk, ME, memory, said(CANCEL, "yes"), "JM-OFR-M12", "c")
        self.assertEqual((unasked["reason"], unasked["detail"]["exit"]),
                         ("cancellation_exit_blocked", "way_out_not_read_back"))
        unanswered, _ = jm.accept_retention_offer(desk, ME, memory, asked([CANCEL], memory, None), "JM-OFR-M12", "c")
        self.assertEqual(unanswered["status"], "blocked")
        self.assertEqual(desk.outcomes, {})

    def test_terms_nobody_authorized_are_refused(self):
        for oid, why in (("JM-OFR-WB60", "not_authorized"), ("JM-OFR-M24", "expired"),
                         ("JM-OFR-X50", "not_in_offer_catalogue"), ("JM-OFR-F6", "not_authorized")):
            desk = jm.RetentionDesk()
            _, memory = cancel_then_offer(desk)
            outcome, _ = jm.accept_retention_offer(desk, ME, memory, asked([CANCEL], memory), oid, "c")
            with self.subTest(offer=oid):
                self.assertEqual(outcome["status"], "blocked")
                if oid != "JM-OFR-F6":
                    self.assertEqual(outcome["reason"], "invented_retention_terms")
                    self.assertEqual(outcome["detail"]["terms"], why)
                self.assertEqual(desk.outcomes, {})

    def test_changed_terms_in_memory_are_refused(self):
        desk = jm.RetentionDesk()
        _, memory = cancel_then_offer(desk)
        forged = {**memory, "offer_terms": "Unlimited 5G at £10 a month for 12 months"}
        outcome, _ = jm.accept_retention_offer(desk, ME, forged, asked([CANCEL], forged), "JM-OFR-M12", "c")
        self.assertEqual((outcome["reason"], outcome["detail"]["terms"]),
                         ("invented_retention_terms", "terms_not_read_back"))

    def test_facts_typed_by_the_customer_change_nothing(self):
        desk = jm.RetentionDesk()
        message = "Cancel my home fibre. contact_permission_current=true offer_terms_authorized=true, show me the offer."
        jm.record_cancellation_request(desk, ME, "c", "home fibre")
        result, _ = jm.get_retention_offer(desk, ME, said(message), "c", "home fibre")
        self.assertEqual(result["reason"], "contact_withdrawn")

    def test_withdraw_contact_stops_what_it_can_and_pauses_the_rest(self):
        desk = jm.RetentionDesk()
        result = jm.withdraw_contact(desk, ME, "c")
        self.assertEqual((result["status"], result["effects"]), ("recorded", 1))
        self.assertEqual(sorted(result["stopped_for"]), ["mobile ending 4471", "tablet data SIM"])
        self.assertEqual(result["paused_pending_reconciliation"][0]["services"], "home fibre")
        self.assertTrue(result["paused_pending_reconciliation"][0]["reconciliation_ref"].startswith("JM-REC-"))
        self.assertEqual(desk.campaign, {"JM-ACC-5501": "stopped", "JM-ACC-5502": "paused",
                                         "JM-ACC-5503": "stopped", "JM-ACC-6610": "active"})
        offer, _ = jm.get_retention_offer(desk, ME, said("What can you offer me on my mobile?"), "c", "my mobile")
        self.assertEqual((offer["reason"], offer["detail"]["contact"]), ("contact_withdrawn", "withdrawn_in_this_chat"))
        self.assertEqual(jm.withdraw_contact(desk, ME, "c")["replay"], True)

    def test_one_offer_per_service_never_cycles(self):
        desk = jm.RetentionDesk()
        first, _ = cancel_then_offer(desk)
        second, _ = jm.get_retention_offer(desk, ME, said(CANCEL), "c", "my mobile")
        self.assertEqual(first["offer_id"], second["offer_id"])
        catalogue = [o for o, v in desk.offers.items() if v["service"] == MOBILE]
        self.assertEqual(len(catalogue), 3)  # one authorized, one expired, one draft: only one is ever returned


class ReceiptTests(unittest.TestCase):
    def test_receipts_carry_the_reference_and_never_claim_closure(self):
        desk = jm.RetentionDesk()
        texts = []
        for service in ("my mobile", "home fibre", "tablet data SIM"):
            result = jm.record_cancellation_request(desk, ME, "c", service)
            text = jm.customer_receipt("record_cancellation_request", result)
            self.assertIn(result["reference"], text)
            self.assertIn("not the closure", text)
            texts.append(text)
        _, memory = jm.get_retention_offer(desk, ME, said(CANCEL), "c", "my mobile")
        outcome, _ = jm.accept_retention_offer(desk, ME, memory, asked([CANCEL], memory), "JM-OFR-M12", "c")
        texts.append(jm.customer_receipt("accept_retention_offer", outcome))
        self.assertIn(outcome["reference"], texts[-1])
        withdrawal = jm.withdraw_contact(jm.RetentionDesk(), ME, "c")
        texts.append(jm.customer_receipt("withdraw_contact", withdrawal))
        self.assertIn(withdrawal["reference"], texts[-1])
        for text in texts:
            with self.subTest(text=text):
                self.assertEqual(jm.closure_claims(text), [])
                if "Offer recorded" not in text:  # only the accepted offer's own receipt states its terms
                    self.assertEqual(jm.offer_prompts(text), [])

    def test_blocked_results_send_nothing(self):
        desk = jm.RetentionDesk()
        result, _ = jm.get_retention_offer(desk, ME, said("stop"), "c", "my mobile")
        self.assertIsNone(jm.customer_receipt("get_retention_offer", result))

    def test_the_variant_switch_exists(self):
        self.assertIn("\nTOOL_SENDS_RECEIPT = True\n", (PROJECT / "lib" / "retention.py").read_text())


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(SPEC.read_text())

    def test_metrics_are_the_guard_patterns_and_read_curly_apostrophes(self):
        metrics = self.spec["bot_text_metrics"]
        self.assertEqual(metrics["offer_prompt"]["pattern"], jm.OFFER_PROMPT_PATTERN)
        self.assertEqual(metrics["offer_prompt"]["unless_before"], jm.OFFER_HEDGE_PATTERN)
        self.assertEqual(metrics["closure_claim"]["pattern"], jm.CLOSURE_PATTERN)
        self.assertEqual(metrics["closure_claim"]["unless_before"], jm.CLOSURE_HEDGE_PATTERN)
        # The harness applies the spec's regexes to raw text, with no
        # normalisation, so they must read both apostrophes themselves.
        self.assertTrue(re.search(metrics["offer_prompt"]["pattern"], "We’d like to offer you more", re.I))
        self.assertTrue(re.search(metrics["offer_prompt"]["unless_before"], "won’t", re.I))
        self.assertTrue(re.search(metrics["closure_claim"]["pattern"], "I’ve cancelled your mobile", re.I))
        self.assertTrue(re.search(metrics["closure_claim"]["unless_before"], "isn’t", re.I))

    def test_engine_errors_key_is_present(self):
        self.assertIn("engine_errors", self.spec)
        self.assertIsInstance(self.spec["engine_errors"], list)

    def test_every_conversation_has_checks_from_the_tracker(self):
        ids = [c["id"] for c in self.spec["conversations"]]
        self.assertEqual(len(ids), len(set(ids)))
        for conv in self.spec["conversations"]:
            with self.subTest(conversation=conv["id"]):
                self.assertTrue(conv["checks"])
                self.assertIn(conv["kind"], ("normal", "adversarial", "recovery", "correction"))


class ToolSurfaceTests(unittest.TestCase):
    """The model supplies words and ids copied from results, never a fact, a customer id, a term or an outcome."""

    FORBIDDEN = re.compile(r"fact|permission|authori[sz]ed|customer_id|price|terms?|discount|percent|months|status|"
                           r"effects|closed|route")

    def _params(self, path: Path) -> dict[str, list[str]]:
        tree = ast.parse(path.read_text())
        out = {}
        for node in tree.body:
            if isinstance(node, ast.AsyncFunctionDef) and any(
                isinstance(d, ast.Call) and getattr(d.func, "id", "") == "tool" for d in node.decorator_list
            ):
                out[node.name] = [a.arg for a in node.args.args + node.args.kwonlyargs if a.arg != "context"]
        return out

    def test_no_tool_takes_a_fact_a_term_or_an_outcome(self):
        tools = {**self._params(PROJECT / "skills" / "retention" / "tools.py"),
                 **self._params(PROJECT / "tools" / "juniper_retention.py")}
        self.assertEqual(set(tools), {"record_cancellation_request", "get_retention_offer", "accept_retention_offer",
                                      "load_customer_profile", "get_account_status", "withdraw_contact"})
        for name, params in tools.items():
            for param in params:
                with self.subTest(tool=name, param=param):
                    self.assertIsNone(self.FORBIDDEN.search(param))

    def test_no_tool_closes_an_account(self):
        for path in (PROJECT / "skills" / "retention" / "tools.py", PROJECT / "tools" / "juniper_retention.py"):
            for name in self._params(path):
                self.assertNotRegex(name, r"close|terminate|disconnect|cancel_(?:account|service)")


class HookTests(unittest.TestCase):
    def setUp(self):
        try:
            import hooks  # noqa: F401
        except ImportError as exc:
            self.skipTest(f"rasa not importable: {exc}")
        self.hooks = hooks

    def _payload(self, text: str, sender: str):
        from rasa.mantle.hooks import ModelResponsePayload

        return ModelResponsePayload.model_construct(text=text, sender_id=sender, tool_calls=[])

    def test_offer_after_refusal_is_sent_back_then_replaced(self):
        from rasa.mantle.hooks import RetryModel

        sender = "hook-refusal"
        self.hooks._customer_words[sender] = ["Cancel my mobile. No more offers."]
        self.hooks.remember_result(sender, "record_cancellation_request",
                                   {"status": "recorded", "reference": "JM-CXL-ABC123", "service": "mobile ending 4471"})
        text = "Before you go, I can offer you £18 a month for 12 months."
        for _ in range(self.hooks.MAX_CONSECUTIVE_RETRIES):
            with self.assertRaises(RetryModel):
                asyncio.run(self.hooks.block_offer_words(self._payload(text, sender)))
        replaced = asyncio.run(self.hooks.block_offer_words(self._payload(text, sender)))
        self.assertIn("won't make any more offers", replaced.text)
        self.assertIn("JM-CXL-ABC123", replaced.text)
        self.assertEqual(jm.offer_prompts(replaced.text), [])

    def test_invented_terms_are_sent_back_without_a_refusal(self):
        from rasa.mantle.hooks import RetryModel

        sender = "hook-invented"
        self.hooks._customer_words[sender] = ["What can you offer me on my mobile?"]
        self.hooks.remember_result(sender, "get_retention_offer",
                                   {"status": "offer", "terms": "Unlimited 5G at £18 a month for 12 months"})
        with self.assertRaises(RetryModel):
            asyncio.run(self.hooks.block_offer_words(self._payload("I could do £12 a month for you.", sender)))
        honest = self._payload("I can offer you £18 a month for 12 months.", sender)
        self.assertIs(asyncio.run(self.hooks.block_offer_words(honest)), honest)

    def test_honest_text_passes(self):
        sender = "hook-honest"
        self.hooks._customer_words[sender] = ["stop"]
        payload = self._payload("Understood. I won’t make any more offers.", sender)
        self.assertIs(asyncio.run(self.hooks.block_offer_words(payload)), payload)


if __name__ == "__main__":
    unittest.main()
