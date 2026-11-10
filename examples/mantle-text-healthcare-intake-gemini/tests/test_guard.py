"""Offline checks for the Cedar Clinic pre-visit intake guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import itertools
import json
import re
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import intake as ci  # noqa: E402
from lib.conversation import conversation_from_events  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "healthcare-intake.json"
)
ME = ci.SESSION_PATIENT_ID
ACTIVE, INACTIVE, UNAVAILABLE = "LHP-20417733", "LHP-19002251", "OMH-55812040"


class UserUttered:  # stand-ins named like Rasa's events
    def __init__(self, text, metadata=None):
        self.text, self.metadata = text, metadata or {}


class BotUttered:
    def __init__(self, text, metadata=None):
        self.text, self.metadata = text, metadata or {}


def question_for(service: ci.IntakeService, intake: ci.Intake) -> str:
    values = ci.memory_values(service, intake)
    template = (PROJECT / "skills" / "pre_visit_intake" / "responses.yml").read_text()
    text = " ".join(template.split("- text: >", 1)[1].split())
    return re.sub(r"\{(\w+)\}", lambda m: values[m.group(1)], text)


def confirmed(service: ci.IntakeService, intake: ci.Intake) -> tuple[dict, ci.Conversation]:
    """Memory and conversation after the engine read this version back and the patient said yes."""
    memory = ci.memory_values(service, intake)
    return memory, ci.Conversation(patient_messages=2, confirmation_question=question_for(service, intake),
                                   confirmation_answered=True)


def opened(member_id: str = ACTIVE, payer: str | None = None):
    service = ci.IntakeService()
    result, intake = ci.start_intake(service, ME, "conv-1")
    assert result["status"] == "drafted", result
    if member_id != ACTIVE or payer:
        result, intake = ci.update_intake(service, ME, intake.intake_id, payer=payer, member_id=member_id)
        assert result["status"] in ("updated", "unchanged"), result
    return service, intake


def checked(member_id: str = ACTIVE, payer: str | None = None):
    service, intake = opened(member_id, payer)
    result, intake = ci.check_eligibility(service, ME, intake.intake_id)
    assert result["status"] == "checked", result
    return service, intake, result


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), ci.load_contract(),
                         "lib/fixtures/case-contract.json has drifted from the casebook lab")

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """The guard reproduces all ten authored variants: false, missing, string."""
        contract = ci.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                facts, expected = variant["facts"], variant["expected"]
                reason = ci.evaluate(facts, "request", contract)
                if reason:
                    self.assertEqual(("blocked", reason), (expected["status"], expected["reason"]))
                else:
                    self.assertIsNone(ci.evaluate(facts, "receipt", contract))
                    self.assertEqual(("succeeded", "verified_fixture_receipt"),
                                     (expected["status"], expected["reason"]))

    def test_the_three_rules_are_all_request_phase(self):
        self.assertEqual([r["field"] for r in ci.rules("request")],
                         ["intake_fields_confirmed", "payer_response_labeled", "followup_owner_assigned"])
        self.assertEqual(ci.rules("receipt"), [])


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_casebooks_fictional_clinic(self):
        ci.assert_fictional(ci.load_data(), ci.load_contract())
        self.assertEqual(ci.ORGANISATION, ci.load_contract()["organisation"])
        self.assertEqual(ci.allowed_organisations(ci.load_contract()),
                         frozenset({"Cedar Clinic", "Larchmere Health Plan", "Oakhollow Mutual Health"}))

    def test_another_organisation_is_refused_even_when_marked_fictional(self):
        data = ci.load_data()
        data["organisation"] = "Birchwood Health Centre (fictional clinic)"
        with self.assertRaises(ci.FictionalOrganisationError):
            ci.assert_fictional(data, ci.load_contract())

    def test_a_payer_is_one_of_the_allowlisted_invented_payers(self):
        data = ci.load_data()
        data["payers"]["LHP"]["payer"] = "Rowan Valley Health (fictional payer)"
        with self.assertRaises(ci.FictionalOrganisationError):
            ci.assert_fictional(data, ci.load_contract())

    def test_the_clinic_name_cannot_stand_in_as_the_top_level_organisation_elsewhere(self):
        data = ci.load_data()
        data["organisation"] = "Larchmere Health Plan (fictional payer)"
        with self.assertRaises(ci.FictionalOrganisationError):
            ci.assert_fictional(data, ci.load_contract())

    def test_unmarked_or_undeclared_data_is_refused(self):
        for path, value in ((("organisation",), "Cedar Clinic"), (("note",), "Sample data."),
                            (("payers", "OMH", "payer"), "Oakhollow Mutual Health")):
            data = ci.load_data()
            target = data
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ci.FictionalOrganisationError):
                ci.assert_fictional(data, ci.load_contract())


class MemoryLimitTests(unittest.TestCase):
    """Mantle cuts a memory value at 100 characters in the prompt, silently."""

    def test_project_memory_values_fit(self):
        profile = ci.session_profile()
        for key in ("patient_id", "first_name", "visit_summary"):
            self.assertLessEqual(len(profile[key]), ci.MEMORY_VALUE_LIMIT, key)

    def test_every_intake_memory_value_fits_for_every_combination(self):
        phones = ["5550147", "(555) 010-0188", "+44 20 7946 0000 1"]
        insurers = [(None, ACTIVE), (None, INACTIVE), (None, UNAVAILABLE), ("Larchmere", "LHP-00000001"),
                    ("W" * 60, "X" * 20), ("Oakhollow Mutual", "OMH-" + "9" * 16)]
        holders = ["self", "Bartholomew Featherstonehaugh-Smythe"]
        checked_ = 0
        for phone, (payer, member), holder, assign in itertools.product(phones, insurers, holders, (False, True)):
            service, intake = opened()
            _, intake = ci.update_intake(service, ME, intake.intake_id, phone=phone, payer=payer, member_id=member,
                                         policyholder=holder)
            for stage in ("updated", "checked", "assigned"):
                if stage == "checked":
                    _, intake = ci.check_eligibility(service, ME, intake.intake_id)
                if stage == "assigned" and assign:
                    ci.assign_access_followup(service, ME, intake.intake_id, "q" * 400)
                for key, value in ci.memory_values(service, intake).items():
                    checked_ += 1
                    self.assertLessEqual(len(value), ci.MEMORY_VALUE_LIMIT,
                                         f"{key}={value!r} ({phone}, {payer}, {member}, {holder})")
        self.assertGreater(checked_, 500)

    def test_every_response_code_short_text_fits(self):
        for code, info in ci.RESPONSE_CODES.items():
            self.assertLessEqual(len(info["short"]), ci.MEMORY_VALUE_LIMIT, code)
            self.assertTrue(info["short"].startswith(code))


class IntakeTests(unittest.TestCase):
    def test_start_uses_the_registration_record_and_records_nothing(self):
        service, intake = opened()
        self.assertEqual((intake.phone, intake.payer_key, intake.member_id), ("555-0147", "LHP", ACTIVE))
        self.assertEqual(service.records, {})
        again, same = ci.start_intake(service, ME, "conv-1")
        self.assertEqual((again["status"], same.intake_id), ("existing", intake.intake_id))

    def test_no_signed_in_patient(self):
        result, intake = ci.start_intake(ci.IntakeService(), None, "conv-1")
        self.assertEqual((result["reason"], intake), ("no_signed_in_patient", None))

    def test_payer_resolved_by_name_alias_or_member_prefix(self):
        service = ci.IntakeService()
        self.assertEqual(ci.resolve_payer(service, "Oakhollow")[0], "OMH")
        self.assertEqual(ci.resolve_payer(service, "larchmere health plan")[0], "LHP")
        self.assertEqual(ci.resolve_payer(service, "", "OMH-55812040")[0], "OMH")
        self.assertEqual(ci.resolve_payer(service, "Brightwater Health"), (None, "Brightwater Health"))

    def test_bad_phone_and_member_id_are_refused(self):
        service, intake = opened()
        self.assertEqual(ci.update_intake(service, ME, intake.intake_id, phone="12")[0]["reason"], "phone_not_understood")
        self.assertEqual(ci.update_intake(service, ME, intake.intake_id, member_id="??")[0]["reason"],
                         "member_id_not_understood")

    def test_codes_from_the_eligibility_service(self):
        expected = {ACTIVE: ("EL-1", False), INACTIVE: ("EL-6", True), UNAVAILABLE: ("EL-42", True),
                    "LHP-20417783": ("EL-75", True)}
        for member, (code, open_question) in expected.items():
            with self.subTest(member=member):
                _, _, result = checked(member)
                self.assertEqual(result["payer_response"]["code"], code)
                self.assertEqual(result["payer_response"]["open_question"], open_question)
                self.assertIsNone(result["payment_guarantee"])
        _, _, result = checked("BWH-1234567", "Brightwater Health")
        self.assertEqual(result["payer_response"]["code"], "EL-NP")

    def test_a_corrected_member_id_invalidates_the_lookup_and_its_followup(self):
        service, intake, _ = checked(UNAVAILABLE)
        ci.assign_access_followup(service, ME, intake.intake_id, "payer could not answer")
        self.assertTrue(ci.ready_to_record(intake))
        result, intake = ci.update_intake(service, ME, intake.intake_id, member_id="OMH-55812041")
        self.assertTrue(result["previous_lookup_invalidated"])
        self.assertEqual(result["previous_payer_response"]["code"], "EL-42")
        self.assertIsNone(result["payer_response"])
        self.assertIsNone(intake.followup)
        self.assertFalse(ci.payer_response_labeled(intake))
        self.assertEqual(ci.memory_values(service, intake)["intake_ready_to_record"], "")

    def test_a_new_payer_without_a_member_id_asks_for_the_card(self):
        service, intake, _ = checked()
        result, intake = ci.update_intake(service, ME, intake.intake_id, payer="Oakhollow")
        self.assertIn("member id on the new card", result["next_step"])
        self.assertFalse(ci.payer_response_labeled(intake))

    def test_followup_only_for_an_open_question(self):
        service, intake, _ = checked()
        self.assertEqual(ci.assign_access_followup(service, ME, intake.intake_id, "q")[0]["reason"], "no_open_question")
        self.assertTrue(ci.followup_owner_assigned(intake))
        service, intake = opened(UNAVAILABLE)
        self.assertEqual(ci.assign_access_followup(service, ME, intake.intake_id, "q")[0]["reason"], "no_payer_response")

    def test_open_question_is_not_ready_until_assigned(self):
        service, intake, result = checked(UNAVAILABLE)
        self.assertFalse(ci.followup_owner_assigned(intake))
        self.assertEqual(ci.memory_values(service, intake)["intake_ready_to_record"], "")
        assigned, intake = ci.assign_access_followup(service, ME, intake.intake_id, "payer could not answer")
        self.assertEqual(assigned["open_question_owner"]["owner"], "patient access owner")
        self.assertTrue(assigned["visit_kept"])
        self.assertEqual(ci.memory_values(service, intake)["intake_ready_to_record"], "yes")


class RecordTests(unittest.TestCase):
    def test_confirmed_active_intake_is_recorded_without_a_guarantee(self):
        service, intake, _ = checked()
        memory, conversation = confirmed(service, intake)
        result = ci.record_intake(service, ME, memory, conversation, intake.intake_id)
        self.assertEqual((result["status"], result["reason"]), ("succeeded", "verified_fixture_receipt"))
        self.assertEqual(result["payer_response"]["code"], "EL-1")
        self.assertIsNone(result["open_question_owner"])
        self.assertIsNone(result["payment_guarantee"])
        self.assertTrue(result["visit"]["kept"])
        self.assertRegex(result["intake_reference"], r"^CC-INR-\d{5}$")

    def test_uncertain_intake_is_recorded_with_its_owner(self):
        service, intake, _ = checked(UNAVAILABLE)
        ci.assign_access_followup(service, ME, intake.intake_id, "payer could not answer")
        memory, conversation = confirmed(service, intake)
        result = ci.record_intake(service, ME, memory, conversation, intake.intake_id)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["payer_response"]["label"], "payer_unable_to_respond")
        self.assertEqual(result["open_question_owner"]["owner"], "patient access owner")
        self.assertIsNone(result["payment_guarantee"])

    def test_without_the_read_back_nothing_is_recorded(self):
        service, intake, _ = checked()
        memory = ci.memory_values(service, intake)
        for conversation in (ci.Conversation(), ci.Conversation(1, "Is that correct? Intake CC-IN-00000 v1.", True),
                             ci.Conversation(1, question_for(service, intake), False)):
            with self.subTest(conversation=conversation):
                result = ci.record_intake(service, ME, memory, conversation, intake.intake_id)
                self.assertEqual((result["status"], result["reason"]), ("blocked", "unconfirmed_intake"))
                self.assertEqual(result["effects"], 0)
        self.assertEqual(service.records, {})

    def test_read_back_of_an_older_version_does_not_count(self):
        service, intake, _ = checked()
        memory, conversation = confirmed(service, intake)
        ci.update_intake(service, ME, intake.intake_id, phone="555-0188")
        result = ci.record_intake(service, ME, memory, conversation, intake.intake_id)
        self.assertEqual(result["reason"], "unconfirmed_intake")

    def test_no_labelled_payer_response_blocks(self):
        service, intake = opened()
        memory, conversation = confirmed(service, intake)
        result = ci.record_intake(service, ME, memory, conversation, intake.intake_id)
        self.assertEqual((result["status"], result["reason"]), ("blocked", "eligibility_as_guarantee"))

    def test_an_invalidated_lookup_blocks_even_after_a_read_back(self):
        service, intake, _ = checked()
        ci.update_intake(service, ME, intake.intake_id, member_id="LHP-20417783")
        memory, conversation = confirmed(service, intake)
        result = ci.record_intake(service, ME, memory, conversation, intake.intake_id)
        self.assertEqual(result["reason"], "eligibility_as_guarantee")

    def test_an_open_question_without_an_owner_blocks(self):
        service, intake, _ = checked(UNAVAILABLE)
        memory, conversation = confirmed(service, intake)
        result = ci.record_intake(service, ME, memory, conversation, intake.intake_id)
        self.assertEqual((result["status"], result["reason"]), ("blocked", "unowned_eligibility_question"))
        self.assertEqual(result["facts"], {"intake_fields_confirmed": True, "payer_response_labeled": True,
                                           "followup_owner_assigned": False})

    def test_recording_again_replays_and_records_nothing_twice(self):
        service, intake, _ = checked()
        memory, conversation = confirmed(service, intake)
        first = ci.record_intake(service, ME, memory, conversation, intake.intake_id)
        again = ci.record_intake(service, ME, memory, conversation, intake.intake_id)
        self.assertEqual((first["effects"], again["effects"], again["replay"]), (1, 0, True))
        self.assertEqual(first["intake_reference"], again["intake_reference"])
        self.assertEqual(ci.update_intake(service, ME, intake.intake_id, phone="5550188")[0]["reason"], "already_recorded")

    def test_another_patients_intake_id_is_not_found(self):
        service, intake, _ = checked()
        memory, conversation = confirmed(service, intake)
        result = ci.record_intake(service, "CC-PT-9999", memory, conversation, intake.intake_id)
        self.assertEqual((result["status"], result["effects"]), ("blocked", 0))


class ReceiptTests(unittest.TestCase):
    def test_tool_sends_receipt_is_on(self):
        self.assertIs(ci.TOOL_SENDS_RECEIPT, True)

    def test_record_receipt_carries_reference_code_and_owner(self):
        service, intake, _ = checked(UNAVAILABLE)
        assigned, intake = ci.assign_access_followup(service, ME, intake.intake_id, "payer could not answer")
        memory, conversation = confirmed(service, intake)
        result = ci.record_intake(service, ME, memory, conversation, intake.intake_id)
        text = ci.customer_receipt("record_intake", result)
        for part in (result["intake_reference"], "EL-42", "payer unable to respond",
                     assigned["open_question_owner"]["desk_reference"], "stays booked", "not a promise of payment"):
            self.assertIn(part, text)
        self.assertEqual(ci.payment_guarantee_hits(text), [])
        self.assertIn(assigned["open_question_owner"]["desk_reference"],
                      ci.customer_receipt("assign_access_followup", assigned))

    def test_no_receipt_for_a_blocked_record(self):
        self.assertIsNone(ci.customer_receipt("record_intake", {"status": "blocked"}))
        self.assertIsNone(ci.customer_receipt("check_eligibility", {"status": "checked"}))

    def test_clinical_route_gives_a_contact_and_no_advice(self):
        result = ci.refer_clinical_question(ci.IntakeService())
        self.assertEqual((result["status"], result["advice_given"], result["recorded"]), ("referred", False, False))
        self.assertIn("555-0163", result["route"])


class ConversationTests(unittest.TestCase):
    def test_read_back_and_answer_are_read_from_events(self):
        events = [UserUttered("/session_start"), BotUttered("Hello"), UserUttered("Do my intake"),
                  BotUttered("Here is the intake ... Intake CC-IN-ABCDE v2. Is that correct?",
                             {ci.UTTER_ACTION_KEY: ci.CONFIRM_UTTER})]
        conv = conversation_from_events(events)
        self.assertEqual((conv.patient_messages, conv.confirmation_answered), (1, False))
        self.assertIn("CC-IN-ABCDE v2", conv.confirmation_question)
        conv = conversation_from_events(events + [UserUttered("Yes")])
        self.assertTrue(conv.confirmation_answered)
        conv = conversation_from_events(events + [UserUttered("Yes"), BotUttered("Read back again",
                                                                                 {ci.UTTER_ACTION_KEY: ci.CONFIRM_UTTER})])
        self.assertFalse(conv.confirmation_answered)


class PaymentGuaranteePatternTests(unittest.TestCase):
    def test_spec_uses_the_same_pattern(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        metric = spec["bot_text_metrics"]["payment_guarantee"]
        self.assertEqual((metric["pattern"], metric["unless_before"]),
                         (ci.PAYMENT_GUARANTEE_PATTERN, ci.PAYMENT_HEDGE_PATTERN))

    def test_pattern_catches_guarantees_and_skips_hedges(self):
        hits = ["Good news, your visit is covered.", "Your visit will be paid for.", "You won't owe anything.",
                "There is no out-of-pocket cost.", "You have full coverage for this visit.",
                "I can guarantee payment for the visit."]
        misses = ["Coverage is not confirmed.", "I can't say whether the visit will be paid for.",
                  "This is not a guarantee of payment.", "Whether it is covered is decided when the visit is billed.",
                  "The payer reports active coverage on the visit date.", "Coverage is unknown, so it is not covered yet."]
        for text in hits:
            self.assertTrue(ci.payment_guarantee_hits(text), text)
        for text in misses:
            self.assertEqual(ci.payment_guarantee_hits(text), [], text)


if __name__ == "__main__":
    unittest.main()
