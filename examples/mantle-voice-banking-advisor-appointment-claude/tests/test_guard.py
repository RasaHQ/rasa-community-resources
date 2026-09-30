"""Offline checks for the Northgate advisor-appointment guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import appointments as na  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "banking-advisor-appointment.json"
)
ELEANOR = "NGB-CUST-4417"


def lab_outcome(facts: dict, contract: dict) -> tuple[str, str]:
    """The lab's execute() order: every rule here is a request rule."""
    reason = na.evaluate(facts, contract)
    return ("blocked", reason) if reason else ("succeeded", "verified_fixture_receipt")


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), na.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = na.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(lab_outcome(variant["facts"], contract), (expected["status"], expected["reason"]))

    def test_all_three_rules_are_request_rules_in_order(self):
        self.assertEqual([r["field"] for r in na.request_rules()],
                         ["purpose_matched", "slot_held", "channel_confirmed"])


class OrganisationGuardTests(unittest.TestCase):
    def test_fixture_is_the_casebook_organisation(self):
        self.assertEqual(na.ORGANISATION, "Northgate Bank")
        na.assert_fictional(na.load_data(), na.load_contract())

    def test_unmarked_organisation_is_refused(self):
        data = na.load_data()
        data["organisation"] = "Northgate Bank"
        with self.assertRaises(na.FictionalOrganisationError):
            na.assert_fictional(data, na.load_contract())

    def test_any_other_organisation_is_refused_even_when_marked(self):
        data = na.load_data()
        data["organisation"] = "Harbourline Bank (fictional)"
        with self.assertRaises(na.FictionalOrganisationError):
            na.assert_fictional(data, na.load_contract())

    def test_team_label_naming_another_bank_is_refused(self):
        data = na.load_data()
        data["teams"]["mortgage-team"]["label"] = "the Harbourline Bank mortgage team"
        with self.assertRaises(na.FictionalOrganisationError):
            na.assert_fictional(data, na.load_contract())

    def test_note_must_say_fictional(self):
        data = na.load_data()
        data["note"] = "Sample data."
        with self.assertRaises(na.FictionalOrganisationError):
            na.assert_fictional(data, na.load_contract())

    def test_contract_must_be_the_synthetic_fixture(self):
        contract = na.load_contract()
        contract["provenance"]["kind"] = "production-policy"
        with self.assertRaises(na.FictionalOrganisationError):
            na.assert_fictional(na.load_data(), contract)


class OwnWordsTests(unittest.TestCase):
    def test_purpose_from_the_customer_words(self):
        cases = {
            "I'd like to talk to someone about remortgaging.": "mortgage",
            "Can I speak to someone about my ISA?": "investments",
            "I want pension advice, but just put me down as a general appointment.": "investments",
            "I run a bakery and want to talk about a business loan.": "business_banking",
            "I need to set up a joint account.": "everyday_banking",
            "My business account needs a new signatory.": "business_banking",
            "Oh wait, it's actually about my mortgage, not the account.": "mortgage",
            "I'd like to open a savings account.": "everyday_banking",
            "Thursday at two thirty, please.": None,
            "My mortgage and my ISA, both please.": None,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(na.stated_purpose([text]), expected)

    def test_latest_message_that_names_a_purpose_wins(self):
        self.assertEqual(na.stated_purpose(["I need a joint account.", "Yes.", "Sorry, it's my mortgage."]),
                         "mortgage")
        self.assertEqual(na.stated_purpose(["It's about my mortgage.", "Thursday at two thirty."]), "mortgage")

    def test_channel_from_the_customer_words(self):
        cases = {
            "A phone call is fine.": "phone",
            "Make it a video call instead of phone.": "video",
            "I'd rather come into a branch.": "branch",
            "Book me in at Kingsmere.": "branch",
            "No, I won't do a phone call. Can someone call me back?": None,
            "Can someone call me back to arrange it?": None,
            "Thursday at eleven.": None,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(na.stated_channel([text]), expected)

    def test_step_free_access(self):
        self.assertTrue(na.step_free_needed(["It needs to be step-free, I use a wheelchair."]))
        self.assertTrue(na.step_free_needed(["I can't manage steps."]))
        self.assertFalse(na.step_free_needed(["I don't need step-free access."]))
        self.assertFalse(na.step_free_needed(["Thursday is fine."]))

    def test_engine_words_are_not_customer_words(self):
        self.assertIsNone(na.stated_purpose(["/session_start"]))

    def test_spoken_branch_names(self):
        data = na.load_data()
        for said, key in (("Ashcombe", "ashcombe"), ("Ash Combe", "ashcombe"), ("Ashcomb", "ashcombe"),
                          ("Kingsmere branch", "kingsmere"), ("Kings Mere", "kingsmere"),
                          ("Farrowdale", "farrowdale"), ("Farrow Dale", "farrowdale"), ("Barnsley", None)):
            with self.subTest(said=said):
                self.assertEqual(na.match_branch(said, data), key)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.s = na.SchedulingService()

    def find(self, words, purpose, **kw):
        return na.find_advisor_slots(self.s, ELEANOR, words, purpose, **kw)

    def test_mortgage_at_kingsmere_finds_no_capable_team_and_no_general_slot(self):
        r = self.find(["Book me in at Kingsmere, I'll ask about my mortgage there."], "mortgage",
                      channel="branch", branch="Kingsmere")
        self.assertEqual((r["status"], r["detail"]), ("no_capable_slot", "no_capable_team_at_branch"))
        self.assertTrue(r["callback_available"])
        teams = {a["team"] for a in r["alternatives"]}
        self.assertNotIn("the Kingsmere branch team", teams)
        self.assertTrue(all("mortgage" in t for t in teams))

    def test_proposals_are_not_reservations(self):
        r = self.find(["A mortgage appointment by phone, please."], "mortgage")
        self.assertEqual(r["status"], "proposed")
        self.assertFalse(r["reserved"])
        self.assertEqual([p["slot_id"] for p in r["proposals"]], ["SLT-MTG-P0814", "SLT-MTG-P0915"])
        self.assertEqual(r["proposals"][0]["starts_at_spoken"], "Thursday 8 October at 2:30 pm")
        self.assertEqual(self.s.holds, {})

    def test_substituted_purpose_is_refused(self):
        r = self.find(["I want pension advice, just put me down as a general appointment."], "everyday_banking")
        self.assertEqual((r["status"], r["reason"], r["detail"]),
                         ("blocked", "wrong_advisor_capability", "purpose_mismatch"))
        self.assertEqual(r["stated_purpose"], "investments")

    def test_no_stated_purpose_asks_first(self):
        r = self.find(["I need an appointment."], "everyday_banking")
        self.assertEqual(r["detail"], "purpose_not_stated")

    def test_step_free_branch_visit_skips_farrowdale(self):
        r = self.find(["A mortgage adviser in person, and I use a wheelchair."], "mortgage", channel="branch")
        self.assertEqual([p["slot_id"] for p in r["proposals"]], ["SLT-ASH-M0910"])
        self.assertTrue(r["proposals"][0]["step_free"])

    def test_no_mortgage_on_tuesday_offers_a_callback(self):
        r = self.find(["It's about my mortgage, and only Tuesday works."], "mortgage", day="Tuesday")
        self.assertEqual((r["status"], r["detail"]), ("no_capable_slot", "no_slot_matches"))
        self.assertTrue(r["alternatives"])

    def test_day_and_part_of_day(self):
        r = self.find(["My ISA, by video, Friday afternoon."], "investments", day="Friday", part_of_day="afternoon")
        self.assertEqual([p["slot_id"] for p in r["proposals"]], ["SLT-INV-V0913"])


class HoldAndBookTests(unittest.TestCase):
    def setUp(self):
        self.s = na.SchedulingService()

    def hold(self, words, slot, purpose):
        return na.hold_slot(self.s, ELEANOR, words, slot, purpose)

    def book(self, words, slot, read_back=None):
        return na.book_appointment(self.s, ELEANOR, words, read_back if read_back is not None else slot, slot,
                                   conversation_id="test")

    def test_happy_path_receipt_names_channel_purpose_and_slot(self):
        words = ["I'd like to talk about remortgaging. A phone call is fine."]
        held = self.hold(words, "SLT-MTG-P0814", "mortgage")
        self.assertEqual(held["status"], "held")
        self.assertFalse(held["reserved"])
        r = self.book(words + ["Yes."], "SLT-MTG-P0814")
        self.assertEqual(r["status"], "succeeded")
        self.assertRegex(r["booking_reference"], r"^APT-\d{6}$")
        self.assertEqual((r["purpose"], r["channel"]), ("mortgage", "phone"))
        self.assertEqual(r["starts_at_spoken"], "Thursday 8 October at 2:30 pm")
        self.assertIsNone(r["advice_given"])
        self.assertEqual(r["effects"], 1)
        self.assertEqual(self.book(words, "SLT-MTG-P0814")["effects"], 0)

    def test_general_slot_for_a_mortgage_is_wrong_capability(self):
        r = self.hold(["Put me in at Kingsmere, it's about my mortgage."], "SLT-KGM-0610", "mortgage")
        self.assertEqual((r["status"], r["reason"]), ("blocked", "wrong_advisor_capability"))
        self.assertEqual(self.s.holds, {})

    def test_booking_without_a_hold_is_slot_not_held(self):
        r = self.book(["My mortgage, by phone."], "SLT-MTG-P0814")
        self.assertEqual((r["status"], r["reason"]), ("blocked", "slot_not_held"))

    def test_booking_a_slot_other_than_the_one_read_back_is_refused(self):
        words = ["My mortgage, by phone."]
        self.hold(words, "SLT-MTG-P0814", "mortgage")
        r = self.book(words, "SLT-MTG-P0814", read_back="SLT-MTG-P0915")
        self.assertEqual(r["reason"], "slot_not_held")

    def test_taken_slot_is_not_held(self):
        r = self.hold(["I need to sort out a joint account at Kingsmere."], "SLT-KGM-0714", "everyday_banking")
        self.assertEqual((r["status"], r["reason"], r["detail"]), ("not_held", "slot_not_held", "taken_since_proposed"))

    def test_lapsed_hold_blocks_once_then_rehold_books(self):
        words = ["My ISA, by video."]
        self.hold(words, "SLT-INV-V0913", "investments")
        first = self.book(words, "SLT-INV-V0913")
        self.assertEqual((first["reason"], first["detail"]), ("slot_not_held", "hold_lapsed"))
        self.assertEqual(self.s.holds, {})
        self.assertEqual(self.hold(words, "SLT-INV-V0913", "investments")["status"], "held")
        self.assertEqual(self.book(words, "SLT-INV-V0913")["status"], "succeeded")

    def test_wrong_channel_is_refused_at_hold_and_at_booking(self):
        r = self.hold(["My mortgage, and I'd rather come into a branch."], "SLT-MTG-P0814", "mortgage")
        self.assertEqual(r["reason"], "wrong_meeting_channel")
        words = ["My mortgage, by phone."]
        self.hold(words, "SLT-MTG-P0814", "mortgage")
        r = self.book(words + ["Actually, I'd rather come into a branch."], "SLT-MTG-P0814")
        self.assertEqual(r["reason"], "wrong_meeting_channel")

    def test_step_free_need_refuses_farrowdale(self):
        r = self.hold(["A mortgage adviser in person. I use a wheelchair."], "SLT-FRD-M0814", "mortgage")
        self.assertEqual(r["reason"], "wrong_meeting_channel")
        self.assertEqual(self.hold(["A mortgage adviser in person. I use a wheelchair."], "SLT-ASH-M0910",
                                   "mortgage")["status"], "held")

    def test_purpose_change_after_hold_fails_at_booking(self):
        self.hold(["I need a joint account at Kingsmere."], "SLT-KGM-0610", "everyday_banking")
        r = self.book(["I need a joint account at Kingsmere.", "Oh wait, it's about my mortgage."], "SLT-KGM-0610")
        self.assertEqual(r["reason"], "wrong_advisor_capability")

    def test_one_hold_at_a_time_and_release(self):
        words = ["My mortgage, by phone."]
        self.hold(words, "SLT-MTG-P0814", "mortgage")
        r = self.hold(words, "SLT-MTG-P0915", "mortgage")
        self.assertEqual((r["status"], r["reason"]), ("not_held", "another_hold_active"))
        self.assertEqual(na.release_hold(self.s, "SLT-MTG-P0814")["status"], "released")
        self.assertEqual(self.hold(words, "SLT-MTG-P0915", "mortgage")["status"], "held")
        self.assertEqual(na.release_hold(self.s, "SLT-MTG-P0814")["status"], "no_hold")

    def test_each_conversation_has_its_own_diary(self):
        a, b = na.service_for("conv-a"), na.service_for("conv-b")
        na.hold_slot(a, ELEANOR, ["My mortgage by phone."], "SLT-MTG-P0814", "mortgage")
        self.assertEqual(b.holds, {})


class CallbackAndMemoryTests(unittest.TestCase):
    def test_callback_goes_to_a_capable_team_and_reserves_nothing(self):
        s = na.SchedulingService()
        r = na.request_callback(s, ELEANOR, ["I want to see someone about my business account, in person."],
                                "business_banking", "Wednesday morning")
        self.assertEqual(r["status"], "requested")
        self.assertEqual(r["team"], "the Northgate business banking team")
        self.assertRegex(r["callback_reference"], r"^CB-\d{6}$")
        self.assertFalse(r["slot_reserved"])
        wrong = na.request_callback(s, ELEANOR, ["My mortgage."], "everyday_banking")
        self.assertEqual(wrong["detail"], "purpose_mismatch")

    def test_memory_values_fit_the_prompt_limit(self):
        s = na.SchedulingService()
        for slot_id, slot in s.data["slots"].items():
            purpose = s.data["teams"][slot["team"]]["capabilities"][0]
            values = na.memory_values(s, slot_id, purpose)
            with self.subTest(slot=slot_id):
                self.assertTrue(all(len(v) < na.MEMORY_VALUE_LIMIT for v in values.values()))
                self.assertTrue(values["held_team_label"][0].isupper())
        self.assertEqual(na.memory_values(s, "SLT-MTG-P0814", "mortgage")["held_slot_label"],
                         "by phone on Thursday 8 October at 2:30 pm")


if __name__ == "__main__":
    unittest.main()
