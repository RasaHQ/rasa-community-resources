"""Offline checks for the Horizon Travel journey guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import journeys as hj  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "travel-booking.json"
)
INES = "HT-PAX-7204"


def prepared(service, booking, option):
    result, memory = hj.prepare_journey_change(service, INES, booking, option)
    return result, memory


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), hj.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = hj.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(hj.lab_outcome(variant["facts"], contract),
                                 (expected["status"], expected["reason"], expected["effects"]))

    def test_rule_phases(self):
        self.assertEqual([r["field"] for r in hj.rules("request")],
                         ["segment_identity_confirmed", "dependent_services_checked"])
        self.assertEqual([r["field"] for r in hj.rules("receipt")], ["change_receipt_reconciled"])


class OrganisationGuardTests(unittest.TestCase):
    def test_fixture_is_the_casebook_organisation(self):
        self.assertEqual(hj.ORGANISATION, "Horizon Travel")
        hj.assert_fictional(hj.load_data(), hj.load_contract())

    def test_unmarked_organisation_is_refused(self):
        data = hj.load_data()
        data["organisation"] = "Horizon Travel"
        with self.assertRaises(hj.FictionalOrganisationError):
            hj.assert_fictional(data, hj.load_contract())

    def test_any_other_organisation_is_refused_even_when_marked(self):
        data = hj.load_data()
        data["organisation"] = "Seabright Journeys (fictional)"
        with self.assertRaises(hj.FictionalOrganisationError):
            hj.assert_fictional(data, hj.load_contract())

    def test_unmarked_partners_are_refused(self):
        data = hj.load_data()
        data["partners"] = "Horizon Transfers, Horizon Park and Fly, and Sierra Walks"
        with self.assertRaises(hj.FictionalOrganisationError):
            hj.assert_fictional(data, hj.load_contract())

    def test_a_provider_outside_the_listed_partners_is_refused(self):
        data = hj.load_data()
        data["bookings"]["HZ3M9V"]["services"]["TO-1"]["provider"] = "Some Other Tours"
        with self.assertRaises(hj.FictionalOrganisationError):
            hj.assert_fictional(data, hj.load_contract())

    def test_traveller_contacts_must_be_reserved(self):
        for field, value in (("email", "ines.calloway@example.org"), ("mobile", "+1 303 555 2368")):
            data = hj.load_data()
            data["travellers"][INES][field] = value
            with self.subTest(field=field), self.assertRaises(hj.FictionalOrganisationError):
                hj.assert_fictional(data, hj.load_contract())

    def test_contract_must_be_the_synthetic_fixture(self):
        contract = hj.load_contract()
        contract["provenance"]["kind"] = "production-policy"
        with self.assertRaises(hj.FictionalOrganisationError):
            hj.assert_fictional(hj.load_data(), contract)


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.service = hj.JourneyService("test")
        self.lisbon = self.service.data["bookings"]["HZ4R8N"]
        self.dublin = self.service.data["bookings"]["HZ6P2L"]

    def test_booking_reference_spoken_or_typed(self):
        for words in ("H Z four R eight N", "hz4r8n", "HZ-4R8N", "booking H Z 4 R 8 N please", "aitch zee for are 8 en"):
            with self.subTest(words=words):
                self.assertEqual(self.service.find_booking(INES, words)[0], "HZ4R8N")

    def test_mangled_reference_falls_back_to_the_callers_words(self):
        heard = ["Booking h z four r eight and please move my Lisbon to Boston flight tomorrow."]
        self.assertEqual(self.service.find_booking(INES, "HZ4R8", heard)[:3:2], ("HZ4R8N", "caller_words"))
        self.assertEqual(self.service.find_booking(INES, "HZ4R8")[0], None)
        # Another traveller's reference in the caller's words is still not found, and never guessed past.
        self.assertEqual(self.service.find_booking(INES, "HZ8D1", ["booking H Z eight D one X"])[2], "not_found")

    def test_booking_by_trip_city_or_date(self):
        self.assertEqual(self.service.find_booking(INES, "my Lisbon trip")[0], "HZ4R8N")
        self.assertEqual(self.service.find_booking(INES, "Dublin")[0], "HZ6P2L")
        self.assertEqual(self.service.find_booking(INES, "tomorrow's flight")[0], "HZ4R8N")
        self.assertEqual(self.service.find_booking(INES, "tomorrow’s flight")[0], "HZ4R8N")

    def test_another_travellers_booking_is_not_found_or_named(self):
        ref, booking, how = self.service.find_booking(INES, "H Z eight D one X")
        self.assertEqual((ref, booking, how), (None, None, "not_found"))
        result = hj.look_up_trip(self.service, INES, "HZ8D1X")
        self.assertEqual(result["status"], "not_found")
        self.assertNotIn("Oyelaran", json.dumps(result))

    def test_segment_words(self):
        cases = {"Lisbon to Boston": ["S3"], "HZ 215": ["S3"], "H Z two one five": ["S3"],
                 "Boston to Denver": ["S4"], "Lisbon flight tomorrow": ["S3"], "HZ 438 October 24": ["S4"],
                 "the one that’s from Lisbon": ["S3"], "the one that's from Lisbon": ["S3"]}
        for words, ids in cases.items():
            with self.subTest(words=words):
                self.assertEqual(self.service.resolve_segment(self.lisbon, words), ("resolved", ids))

    def test_ambiguous_segment_is_not_guessed(self):
        for words in ("my Boston flight tomorrow", "the return flight"):
            with self.subTest(words=words):
                self.assertEqual(self.service.resolve_segment(self.lisbon, words), ("ambiguous", ["S3", "S4"]))
        result = hj.find_change_options(self.service, INES, "HZ4R8N", "my Boston flight tomorrow")
        self.assertEqual((result["status"], result["reason"]), ("needs_segment", "wrong_segment"))

    def test_flown_segment_is_not_changeable(self):
        result = hj.find_change_options(self.service, INES, "HZ4R8N", "Denver to Boston on the 16th")
        self.assertEqual((result["status"], result["reason"]), ("not_changeable", "segment_already_flown"))

    def test_return_leg_of_a_two_leg_trip(self):
        self.assertEqual(self.service.resolve_segment(self.dublin, "the return leg"), ("resolved", ["S2"]))
        self.assertEqual(self.service.resolve_segment(self.dublin, "flight home on the 13th"), ("resolved", ["S2"]))
        self.assertEqual(self.service.resolve_segment(self.dublin, "Boston to Dublin on November 6"),
                         ("resolved", ["S1"]))

    def test_dates(self):
        for words, day in (("2026-10-24", "2026-10-24"), ("October 24", "2026-10-24"), ("24 October", "2026-10-24"),
                           ("the 24th", "2026-10-24"), ("twenty-fourth", "2026-10-24"), ("tomorrow", "2026-10-24"),
                           ("November thirteenth", "2026-11-13"), ("HZ 219 at 3:30", None)):
            with self.subTest(words=words):
                self.assertEqual(hj.parse_date(words), day)


class ChangeTests(unittest.TestCase):
    def setUp(self):
        self.service = hj.JourneyService("test")

    def apply(self, booking, option):
        result, memory = prepared(self.service, booking, option)
        self.assertEqual(result["status"], "ready", result)
        return hj.apply_journey_change(self.service, INES, memory, booking), memory

    def test_same_day_change_moves_the_connection_and_every_linked_service(self):
        result, _ = self.apply("HZ4R8N", "HZ4R8N-S3-A")
        self.assertEqual((result["status"], result["reason"], result["effects"]),
                         ("succeeded", "verified_fixture_receipt", 1))
        states = {r["service"]: (r["state"], r["after"]) for r in result["linked_services"]}
        self.assertEqual(states["S4"], ("moved", "HZ 442 2026-10-24T20:10"))
        self.assertEqual(states["TR-1"], ("moved", "2026-10-24T12:45"))
        self.assertEqual(states["BG-1"], ("re_tagged", ["HZ 219 2026-10-24", "HZ 442 2026-10-24"]))
        self.assertEqual(states["PK-1"], ("still_valid", "2026-10-24T23:59"))
        self.assertTrue(all(r["points_at_new_times"] for r in result["linked_services"]))

    def test_next_day_change_is_partial_and_freezes_the_booking(self):
        result, memory = self.apply("HZ4R8N", "HZ4R8N-S3-B")
        self.assertEqual((result["status"], result["reason"], result["effects"]),
                         ("pending", "partial_journey_change", 1))
        self.assertEqual(result["unresolved"], ["PK-1"])
        self.assertEqual(result["service_states"],
                         {"S4": "moved", "TR-1": "moved", "BG-1": "re_tagged", "PK-1": "unresolved"})
        self.assertTrue(result["frozen"])
        self.assertRegex(result["desk_reference"], r"^TD-\d{6}$")
        # Frozen: no further change, no retry of the whole request.
        again = hj.apply_journey_change(self.service, INES, memory, "HZ4R8N")
        self.assertEqual((again["reason"], again["effects"]), ("journey_frozen", 0))
        self.assertEqual(hj.find_change_options(self.service, INES, "HZ4R8N", "Boston to Denver")["reason"],
                         "journey_frozen")
        self.assertEqual(prepared(self.service, "HZ4R8N", "HZ4R8N-S4-A")[0]["reason"], "journey_frozen")
        self.assertEqual(len(self.service.changes), 1)

    def test_unreadable_partner_blocks_with_no_change(self):
        result, _ = self.apply("HZ3M9V", "HZ3M9V-S1-A")
        self.assertEqual((result["status"], result["reason"], result["effects"]),
                         ("blocked", "connection_not_checked", 0))
        segment = self.service.data["bookings"]["HZ3M9V"]["segments"]["S1"]
        self.assertEqual(segment["departs"], "2026-10-30T18:50")
        self.assertEqual(self.service.changes, [])

    def test_changing_the_second_leg_checks_the_first(self):
        result, _ = self.apply("HZ4R8N", "HZ4R8N-S4-A")
        self.assertEqual(result["status"], "succeeded")
        states = {r["service"]: r["state"] for r in result["linked_services"]}
        self.assertEqual(states, {"S3": "still_valid", "BG-1": "re_tagged", "PK-1": "still_valid"})

    def test_draft_must_match_the_segment_as_it_is_now(self):
        _, memory = prepared(self.service, "HZ4R8N", "HZ4R8N-S3-A")
        self.service.data["bookings"]["HZ4R8N"]["segments"]["S3"]["departs"] = "2026-10-24T11:45"
        result = hj.apply_journey_change(self.service, INES, memory, "HZ4R8N")
        self.assertEqual((result["status"], result["reason"], result["effects"]), ("blocked", "wrong_segment", 0))

    def test_draft_for_another_booking_is_refused(self):
        _, memory = prepared(self.service, "HZ6P2L", "HZ6P2L-S1-A")
        result = hj.apply_journey_change(self.service, INES, memory, "HZ4R8N")
        self.assertEqual(result["reason"], "wrong_segment")

    def test_no_draft_is_refused(self):
        result = hj.apply_journey_change(self.service, INES, {}, "HZ4R8N")
        self.assertEqual((result["reason"], result["effects"]), ("wrong_segment", 0))

    def test_services_read_back_must_be_the_services_checked(self):
        _, memory = prepared(self.service, "HZ4R8N", "HZ4R8N-S3-A")
        memory = {**memory, "draft_services": "S4,TR-1"}
        result = hj.apply_journey_change(self.service, INES, memory, "HZ4R8N")
        self.assertEqual((result["reason"], result["effects"]), ("connection_not_checked", 0))

    def test_option_of_another_booking_is_refused_at_prepare(self):
        result, memory = prepared(self.service, "HZ4R8N", "HZ6P2L-S1-A")
        self.assertEqual((result["status"], result["reason"], memory), ("blocked", "wrong_segment", {}))

    def test_correction_to_the_return_leg_changes_only_the_return(self):
        _, outbound = prepared(self.service, "HZ6P2L", "HZ6P2L-S1-A")
        self.assertEqual(hj.discard_journey_change(outbound)["discarded_option"], "HZ6P2L-S1-A")
        result, _ = self.apply("HZ6P2L", "HZ6P2L-S2-A")
        self.assertEqual(result["status"], "succeeded")
        segments = self.service.data["bookings"]["HZ6P2L"]["segments"]
        self.assertEqual(segments["S1"]["departs"], "2026-11-06T19:40")
        self.assertEqual(segments["S2"]["departs"], "2026-11-14T12:30")

    def test_flight_status_is_not_a_booking_change(self):
        result = hj.check_flight_status(self.service, INES, "HZ 215", "tomorrow")
        self.assertEqual((result["status"], result["booking_changed"]), ("delayed", False))
        segments = self.service.data["bookings"]["HZ4R8N"]["segments"]
        self.assertEqual(segments["S4"]["flight"], "HZ 438")
        self.assertEqual(hj.check_flight_status(self.service, INES, "H Z four three eight", "")["status"], "on_time")


class MemoryAndReceiptTests(unittest.TestCase):
    def all_drafts(self):
        data = hj.load_data()
        for ref, booking in data["bookings"].items():
            for sid, options in booking["options"].items():
                for option in options:
                    service = hj.JourneyService("memory")
                    items = service.plan(service.data["bookings"][ref], sid, option)
                    yield ref, option, hj.memory_values(ref, service.data["bookings"][ref], sid, option, items)

    def test_every_memory_value_is_under_100_characters(self):
        for ref, option, values in self.all_drafts():
            for key, value in values.items():
                with self.subTest(option=option["id"], key=key):
                    self.assertLess(len(value), hj.MEMORY_VALUE_LIMIT)

    def test_memory_keys_match_the_skill_schema(self):
        schema = (PROJECT / "skills" / "change_travel_booking" / "memory.yml").read_text()
        self.assertEqual(sorted(re.findall(r"^    (\w+):$", schema, re.M)), sorted(hj.MEMORY_KEYS))

    def test_confirmation_question_reads_both_labels(self):
        text = (PROJECT / "skills" / "change_travel_booking" / "responses.yml").read_text()
        self.assertIn("{change_label}", text)
        self.assertIn("{services_label}", text)
        self.assertIn("Shall I", text)

    def test_receipts_name_every_service_and_the_reference(self):
        for option, status in (("HZ4R8N-S3-A", "succeeded"), ("HZ4R8N-S3-B", "pending")):
            service = hj.JourneyService("receipts")
            _, memory = prepared(service, "HZ4R8N", option)
            result = hj.apply_journey_change(service, INES, memory, "HZ4R8N")
            text = hj.customer_receipt("apply_journey_change", result)
            with self.subTest(option=option):
                self.assertEqual(result["status"], status)
                for short in ("Denver connection", "Lisbon hotel pickup", "checked bag", "Denver parking"):
                    self.assertIn(short, text)
                if status == "pending":
                    self.assertIn("was not changed", text)
                    self.assertIn(result["desk_reference_spoken"], text)
                else:
                    self.assertIn(result["change_reference_spoken"], text)
                # Spoken while the tool waits: keep it well inside tool_timeout.
                self.assertLess(len(text), 380)

    def test_no_receipt_for_a_wrong_segment_block(self):
        self.assertIsNone(hj.customer_receipt("apply_journey_change", {"status": "blocked", "reason": "wrong_segment"}))

    def test_spoken_labels(self):
        self.assertEqual(hj.spoken_code("HZ 219"), "H Z 2 1 9")
        self.assertEqual(hj.spoken_code("HZ4R8N"), "H Z 4 R 8 N")
        self.assertEqual(hj.spoken_reference("HC-482913"), "H C, 4 8 2, 9 1 3")
        self.assertEqual(hj.spoken_time("2026-10-24T15:30"), "3:30 PM")
        self.assertEqual(hj.spoken_time("2026-11-08T09:00"), "9 AM")


class ProjectShapeTests(unittest.TestCase):
    def test_no_flight_only_change_tool(self):
        source = (PROJECT / "skills" / "change_travel_booking" / "tools.py").read_text()
        tools = re.findall(r"async def (\w+)\(", source)
        self.assertEqual(sorted(t for t in tools if not t.startswith("_")),
                         sorted(["look_up_trip", "check_flight_status", "find_change_options",
                                 "prepare_journey_change", "apply_journey_change", "discard_journey_change"]))
        self.assertNotRegex(source, r"async def \w*(segment_only|flight_only|change_flight)\w*\(")

    def test_no_denial_utterance(self):
        skill = (PROJECT / "skills" / "change_travel_booking" / "skill.md").read_text()
        self.assertNotIn("utter_on_user_denial", skill)
        self.assertIn("requires_confirmation", skill)

    def test_voice_tool_timeout_covers_spoken_receipts(self):
        self.assertRegex((PROJECT / "agent.yml").read_text(), r"(?m)^tool_timeout: 30$")

    def test_voice_channel_uses_the_idle_reconnect_engine(self):
        text = (PROJECT / "integrations.yml").read_text()
        self.assertEqual(text.count("name: engines.rime_idle.RimeTTSReconnectOnIdle"), 2)


if __name__ == "__main__":
    unittest.main()
