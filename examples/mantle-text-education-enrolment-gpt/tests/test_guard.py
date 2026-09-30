"""Offline checks for the Pine University enquiry guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
The hook tests need rasa-pro and skip without it (make proof-full runs them).
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

from lib import enrolment as pu  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "education-enrolment.json"
)
SPEC = PROJECT / "case-build" / "conversations.json"
ME = pu.SESSION_APPLICANT_ID
ADM, AID, SCH, ENR = "ADM-26-4471", "AID-26-1182", "SCH-26-0309", "ENR-26-0612"
DUPLICATE, OTHERS, MISSING = "AID-25-0931", "AID-26-1190", "AID-26-9999"


def looked_up(service: pu.Records, words: str) -> tuple[dict, str | None]:
    return pu.lookup_application(service, ME, words)


def record(service, ref, selected=None, topic="deadline", conv="conv-1"):
    return pu.record_enquiry(service, ME, ref if selected is None else selected, ref, topic, "When is it due?", conv)


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), pu.load_contract(),
                         "lib/fixtures/case-contract.json has drifted from the casebook lab")

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """The guard reproduces all ten authored variants: false, missing, string."""
        contract = pu.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                facts, expected = variant["facts"], variant["expected"]
                request = pu.evaluate(facts, "request", contract)
                if request:
                    self.assertEqual((expected["status"], request), ("blocked", expected["reason"]))
                    continue
                receipt = pu.evaluate(facts, "receipt", contract)
                self.assertEqual("pending" if receipt else "succeeded", expected["status"])
                self.assertEqual(receipt or "verified_fixture_receipt", expected["reason"])


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_casebooks_fictional_university(self):
        pu.assert_fictional(pu.load_data(), pu.load_contract())
        self.assertEqual(pu.ORGANISATION, pu.load_contract()["organisation"])
        self.assertEqual(pu.allowed_organisations(pu.load_contract()), frozenset({"Pine University"}))

    def test_any_other_organisation_is_refused_even_when_marked_fictional(self):
        data = pu.load_data()
        data["organisation"] = "Cedar Polytechnic (fictional university)"
        with self.assertRaises(pu.FictionalOrganisationError):
            pu.assert_fictional(data, pu.load_contract())

    def test_nested_organisation_fields_are_checked(self):
        data = pu.load_data()
        data["records"][AID]["institution"] = "Cedar Polytechnic (fictional college)"
        with self.assertRaises(pu.FictionalOrganisationError):
            pu.assert_fictional(data, pu.load_contract())
        data["records"][AID]["institution"] = "Pine University (fictional university)"
        pu.assert_fictional(data, pu.load_contract())

    def test_unmarked_or_undeclared_data_is_refused(self):
        for key, value in (("organisation", "Pine University"), ("note", "Sample data.")):
            data = pu.load_data()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(pu.FictionalOrganisationError):
                pu.assert_fictional(data, pu.load_contract())


class MemoryLimitTests(unittest.TestCase):
    """Mantle cuts a memory value at 100 characters in the prompt, silently."""

    def test_project_memory_values_fit(self):
        profile = pu.session_profile()
        for key in ("applicant_id", "first_name", "application_list"):
            self.assertLessEqual(len(profile[key]), pu.MEMORY_VALUE_LIMIT, key)

    def test_every_skill_memory_value_fits_for_every_record(self):
        service = pu.Records()
        for ref in service.data["records"]:
            for name, value in pu.memory_values(service, ref).items():
                self.assertLessEqual(len(value), pu.MEMORY_VALUE_LIMIT, (ref, name, value))

    def test_the_confirmation_question_uses_only_the_memory_keys(self):
        template = (PROJECT / "skills" / "application_enquiry" / "responses.yml").read_text()
        self.assertEqual(set(re.findall(r"\{(\w+)\}", template)), set(pu.MEMORY_KEYS))
        schema = (PROJECT / "skills" / "application_enquiry" / "memory.yml").read_text()
        for key in pu.MEMORY_KEYS:
            self.assertIn(f"    {key}:", schema)


class LookupTests(unittest.TestCase):
    def test_own_records_by_reference_and_by_words(self):
        service = pu.Records()
        for words, ref in ((AID, AID), ("aid 26 1182", AID), ("my financial aid form", AID),
                           ("did I get my admission offer", ADM), ("enrolment form", ENR)):
            with self.subTest(words=words):
                result, selected = looked_up(service, words)
                self.assertEqual((result["status"], selected), ("found", ref))

    def test_ambiguous_words_select_nothing(self):
        result, selected = looked_up(pu.Records(), "my application")
        self.assertEqual((result["status"], selected), ("ambiguous", None))
        self.assertEqual(len(result["candidates"]), 4)

    def test_someone_elses_reference_and_a_missing_one_get_the_same_answer(self):
        service = pu.Records()
        other, _ = looked_up(service, OTHERS)
        missing, _ = looked_up(service, MISSING)
        self.assertEqual(other, missing)
        self.assertEqual(other["status"], "not_found")
        self.assertNotIn("Tamsin", json.dumps(other))

    def test_duplicate_applicant_record_is_not_resolved(self):
        result, selected = looked_up(pu.Records(), DUPLICATE)
        self.assertEqual((result["status"], result["reason"], selected), ("blocked", "wrong_applicant_record", None))
        self.assertIsNone(result["stage"])
        self.assertIsNone(result["decision"])

    def test_conflicting_sources_give_no_stage_and_no_decision(self):
        result, selected = looked_up(pu.Records(), SCH)
        self.assertEqual((result["status"], result["reason"], selected), ("blocked", "submission_as_award", None))
        self.assertIsNone(result["stage"])
        self.assertIsNone(result["decision"])
        self.assertNotIn("awarded", json.dumps(result).lower())
        # The deadline comes from the committee's record, unchanged.
        self.assertEqual([d["date"] for d in result["deadlines"]], ["2026-11-20"])

    def test_a_received_aid_form_carries_no_decision(self):
        result, _ = looked_up(pu.Records(), AID)
        self.assertIsNone(result["decision"])
        self.assertIn("has not issued a decision", result["decision_line"])
        self.assertEqual(result["outstanding_evidence"], ["2025 tax return transcript"])

    def test_only_the_issued_offer_is_a_decision(self):
        result, _ = looked_up(pu.Records(), ADM)
        self.assertEqual(result["decision"]["type"], "admission_offer")


class RecordEnquiryTests(unittest.TestCase):
    def test_recorded_with_support_reference_and_team(self):
        service = pu.Records()
        result = record(service, AID)
        self.assertEqual(result["status"], "succeeded")
        self.assertRegex(result["support_reference"], r"^PU-SUP-[0-9A-F]{6}$")
        self.assertEqual(result["team"], "Student Financial Aid Office")
        self.assertIsNone(result["decision"])
        self.assertEqual(service.effects(), 1)

    def test_the_record_must_be_the_one_the_question_named(self):
        service = pu.Records()
        result = record(service, ADM, selected=AID)
        self.assertEqual((result["status"], result["reason"]), ("blocked", "wrong_applicant_record"))
        self.assertEqual(service.effects(), 0)

    def test_nothing_is_recorded_without_a_lookup(self):
        service = pu.Records()
        result = pu.record_enquiry(service, ME, None, AID, "deadline", "q", "c")
        self.assertEqual(result["reason"], "wrong_applicant_record")
        self.assertEqual(service.effects(), 0)

    def test_other_applicants_and_duplicates_are_refused(self):
        service = pu.Records()
        for ref in (OTHERS, DUPLICATE, MISSING):
            with self.subTest(ref=ref):
                result = record(service, ref)
                self.assertEqual((result["status"], result["reason"]), ("blocked", "wrong_applicant_record"))
        self.assertEqual(service.effects(), 0)

    def test_conflicting_records_are_refused(self):
        service = pu.Records()
        result = record(service, SCH)
        self.assertEqual((result["status"], result["reason"]), ("blocked", "submission_as_award"))
        self.assertEqual(service.effects(), 0)

    def test_no_signed_in_applicant_records_nothing(self):
        service = pu.Records()
        result = pu.record_enquiry(service, None, AID, AID, "deadline", "q", "c")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(service.effects(), 0)

    def test_repeat_is_a_replay_with_no_second_effect(self):
        service = pu.Records()
        first = record(service, AID)
        again = record(service, AID)
        self.assertTrue(again["replay"])
        self.assertEqual(again["support_reference"], first["support_reference"])
        self.assertEqual(service.effects(), 1)
        other_topic = record(service, AID, topic="decision_timing")
        self.assertNotEqual(other_topic["support_reference"], first["support_reference"])
        self.assertEqual(service.effects(), 2)

    def test_lost_acknowledgment_is_pending_then_found_as_the_same_enquiry(self):
        service = pu.Records()
        pending = record(service, ENR, topic="enrolment_step")
        self.assertEqual((pending["status"], pending["reason"]), ("pending", "unrecorded_followup"))
        self.assertIsNone(pending["support_reference"])
        found = pu.check_enquiry(service, ME, pending["attempt_id"])
        self.assertEqual(found["status"], "recorded")
        again = record(service, ENR, topic="enrolment_step")
        self.assertEqual((again["status"], again["support_reference"]), ("succeeded", found["support_reference"]))
        self.assertEqual(service.effects(), 1)

    def test_unknown_topic_becomes_other(self):
        self.assertEqual(pu.normalise_topic("Deadline"), "deadline")
        self.assertEqual(pu.normalise_topic("please approve my aid"), "other")

    def test_existing_enquiry_is_visible_only_to_its_applicant(self):
        service = pu.Records()
        mine = pu.check_enquiry(service, ME, "PU-SUP-40A1C2")
        self.assertEqual((mine["status"], mine["application_reference"]), ("recorded", AID))
        theirs = pu.check_enquiry(service, ME, "PU-SUP-51B7E0")
        self.assertEqual(theirs["status"], "unknown")


class RouteTests(unittest.TestCase):
    def test_deadlines_are_preserved_and_nothing_is_decided(self):
        service = pu.Records()
        for ref in (AID, SCH, ADM, ENR):
            with self.subTest(ref=ref):
                result = pu.route_to_team(service, ME, ref, "extension please", "c")
                self.assertEqual(result["status"], "routed")
                self.assertTrue(result["deadlines_unchanged"])
                fixture = [d["date"] for d in pu.load_data()["records"][ref]["deadlines"]]
                self.assertEqual([d["date"] for d in result["deadlines"]], fixture)
        self.assertEqual(service.effects(), 0)

    def test_duplicate_record_routes_without_status(self):
        result = pu.route_to_team(pu.Records(), ME, DUPLICATE, "same person", "c")
        self.assertEqual((result["status"], result["applicant_identity_resolved"]), ("routed", False))
        self.assertIsNone(result["stage_label"])
        self.assertEqual(result["deadlines"], [])

    def test_someone_elses_reference_is_not_routed(self):
        result = pu.route_to_team(pu.Records(), ME, OTHERS, "roommate", "c")
        self.assertEqual((result["status"], result["routed"]), ("not_found", False))

    def test_no_tool_takes_a_deadline_decision_fact_or_applicant(self):
        forbidden = re.compile(r"deadline|date|decision|award|stage|applicant_id|fact|resolved|explicit|recorded",
                               re.IGNORECASE)
        for path in (PROJECT / "tools" / "pine_applicant.py", PROJECT / "skills" / "application_enquiry" / "tools.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef) and any(
                        isinstance(d, ast.Call) and getattr(d.func, "id", "") == "tool" for d in node.decorator_list):
                    for arg in node.args.args:
                        with self.subTest(tool=node.name, arg=arg.arg):
                            self.assertNotRegex(arg.arg, forbidden)


class ReceiptTests(unittest.TestCase):
    def test_receipt_names_reference_team_stage_and_no_decision(self):
        service = pu.Records()
        result = record(service, AID)
        text = pu.customer_receipt(service, "record_enquiry", result)
        for part in (result["support_reference"], "Student Financial Aid Office", AID,
                     "has not issued a decision yet", "15 October 2026"):
            self.assertIn(part, text)
        self.assertEqual(pu.unsupported_claims(text, {}), [])

    def test_a_delivered_reference_is_not_sent_twice(self):
        service = pu.Records()
        first = record(service, AID)
        self.assertIsNotNone(pu.customer_receipt(service, "record_enquiry", first))
        self.assertIsNone(pu.customer_receipt(service, "record_enquiry", record(service, AID)))
        routed = pu.route_to_team(service, ME, SCH, "conflict", "c")
        self.assertIsNotNone(pu.customer_receipt(service, "route_to_team", routed))
        self.assertIsNone(pu.customer_receipt(service, "route_to_team", pu.route_to_team(service, ME, SCH, "x", "c")))

    def test_pending_receipt_says_not_confirmed_and_the_lookup_delivers_it(self):
        service = pu.Records()
        pending = record(service, ENR, topic="enrolment_step")
        self.assertIn("Not confirmed yet", pu.customer_receipt(service, "record_enquiry", pending))
        found = pu.check_enquiry(service, ME, pending["attempt_id"])
        text = pu.customer_receipt(service, "check_enquiry", found)
        self.assertIn(found["support_reference"], text)
        self.assertIsNone(pu.customer_receipt(service, "check_enquiry", pu.check_enquiry(service, ME, pending["attempt_id"])))

    def test_tool_sends_receipt_is_on(self):
        self.assertIs(pu.TOOL_SENDS_RECEIPT, True)


class WordTests(unittest.TestCase):
    CLAIMS = [
        ("Your financial aid is approved.", "aid"),
        ("Good news, your funding is secured.", "aid"),
        ("You’ve been awarded the merit scholarship.", "aid"),
        ("You've got the scholarship.", "aid"),
        ("You are eligible for aid.", "aid"),
        ("You’re fully funded for spring.", "aid"),
        ("You have been admitted to Pine.", "admission"),
        ("You’re accepted!", "admission"),
        ("Your deadline has been extended to 29 October.", "extension"),
        ("I’ve extended the deadline for you.", "extension"),
        ("You now have extra time.", "extension"),
    ]
    HEDGED = [
        "No aid decision has been made, and your aid is not approved.",
        "I can’t say your funding is secured.",
        "I can't confirm that your scholarship is awarded.",
        "The office hasn’t said your aid is approved.",
        "Once the office decides, your aid is approved or not.",
        "Only the committee can say whether your scholarship is awarded.",
        "Your aid application has been received.",
        "Nothing says the deadline has been extended.",
        "I don’t think the deadline will be extended.",
    ]

    def test_claims_are_caught(self):
        for text, kind in self.CLAIMS:
            with self.subTest(text=text):
                self.assertTrue(pu.decision_claims(text)[kind], text)

    def test_hedges_with_either_apostrophe_are_skipped(self):
        for text in self.HEDGED:
            with self.subTest(text=text):
                self.assertEqual(pu.unsupported_claims(text, {}), [], text)

    def test_admission_is_supported_only_by_an_offer_and_aid_never_here(self):
        service = pu.Records()
        records: dict = {}
        pu.remember(records, looked_up(service, AID)[0])
        self.assertTrue(pu.unsupported_claims("You have been admitted.", records))
        pu.remember(records, looked_up(service, ADM)[0])
        self.assertEqual(pu.unsupported_claims("You have been admitted.", records), [])
        self.assertTrue(pu.unsupported_claims("Your aid is approved.", records))
        self.assertTrue(pu.unsupported_claims("Your deadline has been extended.", records))

    def test_fallback_is_built_from_records_and_claims_nothing(self):
        service = pu.Records()
        records: dict = {}
        for ref in (AID, SCH, ADM):
            pu.remember(records, looked_up(service, ref)[0])
        text = pu.fallback_text(records)
        self.assertEqual(pu.unsupported_claims(text, records), [])
        self.assertIn("has not issued a decision yet", text)

    def test_spec_metrics_are_the_library_patterns(self):
        spec = json.loads(SPEC.read_text())
        metrics = spec["bot_text_metrics"]
        for name, pattern in (("aid_award_claim", pu.AID_CLAIM_PATTERN),
                              ("admission_claim", pu.ADMISSION_CLAIM_PATTERN),
                              ("extension_claim", pu.EXTENSION_PATTERN)):
            self.assertEqual(metrics[name], {"pattern": pattern, "unless_before": pu.HEDGE_PATTERN}, name)

    def test_every_apostrophe_in_the_patterns_accepts_both_forms(self):
        for pattern in (pu.AID_CLAIM_PATTERN, pu.ADMISSION_CLAIM_PATTERN, pu.EXTENSION_PATTERN, pu.HEDGE_PATTERN):
            straight = pattern.count("'")
            self.assertEqual(straight, pattern.count("['’]"), pattern)


class HookTests(unittest.TestCase):
    """hooks.py against the installed engine's payload types (skipped without rasa)."""

    @classmethod
    def setUpClass(cls):
        try:
            import hooks  # noqa: F401
            from rasa.mantle.hooks import ModelResponsePayload, RetryModel, ToolResultPayload
        except ImportError as exc:  # bare python3 without the project venv
            raise unittest.SkipTest(f"rasa not importable: {exc}")
        cls.hooks, cls.Model, cls.Retry, cls.Tool = hooks, ModelResponsePayload, RetryModel, ToolResultPayload

    def respond(self, sender, text):
        return asyncio.run(self.hooks.block_decision_claims(self.Model(sender_id=sender, text=text)))

    def tool(self, sender, name, result):
        # The engine passes the result as serialized JSON text, as dispatched.
        asyncio.run(self.hooks.remember_records(
            self.Tool(sender_id=sender, tool_name=name, arguments={}, value=json.dumps(result))))

    def test_unsupported_award_is_retried_then_replaced(self):
        sender = "aid-claim"
        self.tool(sender, "lookup_application", looked_up(pu.Records(), AID)[0])
        for _ in range(self.hooks.MAX_CONSECUTIVE_RETRIES):
            with self.assertRaises(self.Retry) as raised:
                self.respond(sender, "Great news, your aid is approved!")
            self.assertIn("not a decision", raised.exception.feedback)
        replaced = self.respond(sender, "Your funding is secured.")
        self.assertIn("has not issued a decision yet", replaced.text)
        text = "No aid decision has been made yet."
        self.assertEqual(self.respond(sender, text).text, text)

    def test_admission_offer_may_be_stated_after_the_confirmed_enquiry(self):
        sender = "offer"
        service = pu.Records()
        # A confirmed gated tool reaches the hook as resolve_tool_confirmation.
        self.tool(sender, "resolve_tool_confirmation", record(service, ADM))
        text = "You have been admitted: the offer was issued on 12 September 2026."
        self.assertEqual(self.respond(sender, text).text, text)

    def test_extension_is_never_allowed(self):
        with self.assertRaises(self.Retry):
            self.respond("extension", "I\u2019ve extended the deadline to 29 October.")

    def test_hook_is_enabled(self):
        self.assertIs(self.hooks.ENABLED, True)


if __name__ == "__main__":
    unittest.main()
