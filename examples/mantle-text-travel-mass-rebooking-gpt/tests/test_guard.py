"""Offline checks for the Horizon Travel rebooking guard. No model, no network, no licence.

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

from lib import rebooking as rb  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "travel-mass-rebooking.json"
)
ME = rb.SESSION_PASSENGER_ID
CASE = "HT-DC-40117"
OTHER_CASE = "HT-DC-40290"
ONE = ["My flight to Lisbon was cancelled. Please rebook me."]
TWO = ONE + ["Yes, send it."]


def fresh() -> rb.RebookingService:
    return rb.RebookingService()


def held(svc: rb.RebookingService, option: str, msgs=ONE, conv: str = "t", accessible: bool = False) -> dict:
    result = rb.hold_option(svc, ME, CASE, option, list(msgs), conv, accessible)
    assert result["status"] == "held", result
    return result


def commit(svc: rb.RebookingService, hold_id: str, msgs=TWO, confirmed: str | None = None, conv: str = "t") -> dict:
    return rb.commit_rebooking(svc, ME, confirmed if confirmed is not None else hold_id, hold_id, list(msgs), conv)


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(
            json.loads(CASEBOOK_CONTRACT.read_text()),
            rb.load_contract(),
            "lib/fixtures/case-contract.json has drifted from the casebook lab",
        )

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """All ten authored variants: request rules block, the receipt rule leaves it pending."""
        contract = rb.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                request = rb.evaluate(variant["facts"], "request", contract)
                receipt = rb.evaluate(variant["facts"], "receipt", contract)
                if request:
                    status, reason = "blocked", request
                elif receipt:
                    status, reason = "pending", receipt
                else:
                    status, reason = "succeeded", "verified_fixture_receipt"
                self.assertEqual((status, reason), (variant["expected"]["status"], variant["expected"]["reason"]))

    def test_string_true_is_not_true(self):
        facts = {"itinerary_constraints_met": True, "capacity_hold_valid": "true"}
        self.assertEqual(rb.evaluate(facts, "request"), "hold_expired")


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_casebooks_fictional_company(self):
        rb.assert_fictional(rb.load_data(), rb.load_contract())
        self.assertEqual(rb.ORGANISATION, rb.load_contract()["organisation"])

    def test_any_other_organisation_is_refused_even_when_marked_fictional(self):
        data = rb.load_data()
        data["organisation"] = "Skyward Lines (fictional airline)"
        with self.assertRaises(rb.FictionalOrganisationError):
            rb.assert_fictional(data, rb.load_contract())

    def test_a_nested_carrier_must_be_the_same_company(self):
        data = rb.load_data()
        data["options"]["RB-1306"]["carrier"] = "Skyward Lines (fictional airline)"
        with self.assertRaises(rb.FictionalOrganisationError):
            rb.assert_fictional(data, rb.load_contract())
        data["options"]["RB-1306"]["carrier"] = "Horizon Travel (fictional travel company)"
        rb.assert_fictional(data, rb.load_contract())

    def test_the_allowed_name_must_still_be_marked_fictional(self):
        data = rb.load_data()
        data["organisation"] = "Horizon Travel"
        with self.assertRaises(rb.FictionalOrganisationError):
            rb.assert_fictional(data, rb.load_contract())

    def test_the_note_must_say_fictional(self):
        data = rb.load_data()
        data["note"] = "Sample data."
        with self.assertRaises(rb.FictionalOrganisationError):
            rb.assert_fictional(data, rb.load_contract())


class MemoryTests(unittest.TestCase):
    def test_every_memory_value_fits_the_prompt_limit(self):
        """Mantle cuts a memory value at 100 characters in the prompt; every value a tool writes fits."""
        data = rb.load_data()
        profile = rb.passenger_profile(fresh())
        for value in (profile["passenger_id"], profile["first_name"], profile["disruption_case"]):
            self.assertLessEqual(len(value), rb.MEMORY_VALUE_LIMIT)
        for option_id, accessible in itertools.product(data["options"], (False, True)):
            svc = fresh()
            svc.options[option_id]["gone_before_hold"] = False
            case = svc.cases[CASE]
            case["constraints"]["arrive_by"] = "2026-12-31T00:00:00+00:00"
            svc.options[option_id]["connection"] = (svc.options[option_id].get("connection") or None)
            if svc.options[option_id]["connection"]:
                svc.options[option_id]["connection"]["step_free"] = True
            result = rb.hold_option(svc, ME, CASE, option_id, ONE, "t", accessible)
            self.assertEqual(result["status"], "held", (option_id, result))
            for key, value in rb.held_memory(result).items():
                with self.subTest(option=option_id, accessible=accessible, key=key):
                    self.assertLessEqual(len(value), rb.MEMORY_VALUE_LIMIT, value)

    def test_an_over_long_value_is_refused_not_cut(self):
        result = held(fresh(), "RB-1303")
        result["flight"] = "x" * (rb.MEMORY_VALUE_LIMIT + 1)
        with self.assertRaises(ValueError):
            rb.held_memory(result)


class OfferAndHoldTests(unittest.TestCase):
    def test_search_offers_are_not_holds(self):
        svc = fresh()
        result = rb.search_options(svc, ME, CASE, ONE)
        self.assertEqual(result["status"], "found")
        ids = [o["option_id"] for o in result["options"]]
        self.assertEqual(set(ids), set(svc.options))
        self.assertEqual(svc.options["RB-1303"]["seats"], 3, "a search reserves nothing")
        late = next(o for o in result["options"] if o["option_id"] == "RB-1304")
        self.assertFalse(late["meets_constraints"])
        self.assertIn("arrives after", late["unmet"][0])

    def test_last_seat_shown_in_search_is_gone_at_hold(self):
        svc = fresh()
        shown = next(o for o in rb.search_options(svc, ME, CASE, ONE)["options"] if o["option_id"] == "RB-1301")
        self.assertEqual(shown["seats_shown"], 1)
        result = rb.hold_option(svc, ME, CASE, "RB-1301", ONE, "t")
        self.assertEqual((result["status"], result["reason"], result["effects"]), ("unavailable", "capacity_gone", 0))
        self.assertIsNone(svc.active_hold(CASE, svc.now(1)))

    def test_hold_reserves_one_seat_until_a_stated_time(self):
        svc = fresh()
        result = held(svc, "RB-1303")
        self.assertEqual(svc.options["RB-1303"]["seats"], 2)
        self.assertEqual(result["held_until"], "19:26 Boston time, 12 Nov")
        self.assertIs(result["facts"]["capacity_hold_valid"], True)

    def test_late_arrival_is_unusable_and_cannot_be_held(self):
        svc = fresh()
        result = rb.hold_option(svc, ME, CASE, "RB-1304", ONE, "t")
        self.assertEqual((result["status"], result["reason"]), ("blocked", "unusable_itinerary"))
        self.assertEqual(svc.options["RB-1304"]["seats"], 9)

    def test_accessible_need_blocks_the_stair_connection(self):
        for msgs, flag in ((ONE, True), (["I use a wheelchair, so no stairs please."], False)):
            with self.subTest(flag=flag):
                svc = fresh()
                result = rb.hold_option(svc, ME, CASE, "RB-1302", msgs, "t", flag)
                self.assertEqual(result["reason"], "unusable_itinerary")
                self.assertIn("not step-free", result["unmet"][0])
                self.assertIn(rb.ACCESSIBLE, svc.cases[CASE]["requirements"])

    def test_requirement_is_never_removed_in_chat(self):
        svc = fresh()
        rb.search_options(svc, ME, CASE, ONE, accessible_connection=True)
        result = rb.hold_option(svc, ME, CASE, "RB-1302", ONE, "t", accessible_connection=False)
        self.assertEqual(result["reason"], "unusable_itinerary")

    def test_accessible_hold_lists_wheelchair_assistance_as_open(self):
        result = held(fresh(), "RB-1303", accessible=True)
        self.assertEqual(result["open_services"], ["wheelchair assistance at JFK"])

    def test_one_hold_at_a_time_and_switch_releases(self):
        svc = fresh()
        first = held(svc, "RB-1302")
        second = rb.hold_option(svc, ME, CASE, "RB-1303", ONE, "t")
        self.assertEqual(second["reason"], "active_hold_exists")
        released = rb.release_hold(svc, ME, first["hold_id"], 1)
        self.assertEqual(released["status"], "released")
        self.assertEqual(svc.options["RB-1302"]["seats"], 4)
        held(svc, "RB-1303")

    def test_other_passengers_case_looks_unknown(self):
        svc = fresh()
        other = rb.hold_option(svc, ME, OTHER_CASE, "RB-1303", ONE, "t")
        unknown = rb.hold_option(svc, ME, "HT-DC-00000", "RB-1303", ONE, "t")
        strip = lambda r: {k: v for k, v in r.items() if k != "case_reference"}  # noqa: E731
        self.assertEqual(other["status"], "not_found")
        self.assertEqual(strip(other), strip(unknown))
        self.assertEqual(rb.disruption_case(svc, ME, OTHER_CASE, 1)["status"], "not_found")
        self.assertEqual(rb.recovery_desk(svc, ME, OTHER_CASE, "x", 1)["status"], "not_found")


class CommitTests(unittest.TestCase):
    def test_success_is_committed_and_read_back(self):
        svc = fresh()
        hold = held(svc, "RB-1303")
        result = commit(svc, hold["hold_id"])
        self.assertEqual((result["status"], result["reason"], result["effects"]), ("succeeded", "verified_fixture_receipt", 1))
        self.assertRegex(result["replacement_reference"], r"^HT-RB-[0-9A-F]{5}$")
        self.assertIs(result["facts"]["replacement_commit_verified"], True)
        self.assertEqual(svc.cases[CASE]["status"], "rebooked")

    def test_short_hold_expires_during_confirmation(self):
        svc = fresh()
        hold = held(svc, "RB-1305")
        self.assertEqual(hold["held_until"], "19:11 Boston time, 12 Nov")
        result = commit(svc, hold["hold_id"])
        self.assertEqual((result["status"], result["reason"], result["effects"]), ("blocked", "hold_expired", 0))
        self.assertEqual(result["hold_state"], "expired")
        self.assertEqual(result["case_status"], "open", "the disruption case stays open")
        self.assertEqual(svc.options["RB-1305"]["seats"], 2, "the expired seat went back")
        again = commit(svc, hold["hold_id"], msgs=TWO + ["Just use that hold."])
        self.assertEqual(again["reason"], "hold_expired", "an expired hold is never reused")
        receipt = rb.customer_receipt("commit_rebooking", result)
        self.assertIn("expired at 19:11", receipt)
        self.assertIn("stays open", receipt)

    def test_app_hold_from_this_morning_is_expired(self):
        svc = fresh()
        result = rb.resume_hold(svc, ME, "HT-RH-7710", ONE)
        self.assertEqual((result["status"], result["reason"]), ("blocked", "hold_expired"))
        blocked = commit(svc, "HT-RH-7710")
        self.assertEqual(blocked["reason"], "hold_expired")
        self.assertEqual(blocked["effects"], 0)

    def test_unconfirmed_or_unknown_hold_is_blocked(self):
        svc = fresh()
        hold = held(svc, "RB-1303")
        self.assertEqual(commit(svc, hold["hold_id"], confirmed="")["reason"], "hold_expired")
        self.assertEqual(commit(svc, hold["hold_id"], confirmed="HT-RH-00000")["reason"], "hold_expired")
        self.assertEqual(commit(svc, "HT-RH-00000")["reason"], "hold_expired")
        self.assertEqual(svc.cases[CASE]["status"], "open")

    def test_need_stated_at_confirmation_blocks_and_releases(self):
        svc = fresh()
        hold = held(svc, "RB-1302")
        result = commit(svc, hold["hold_id"], msgs=ONE + ["Yes, but I'll need a wheelchair at the change."])
        self.assertEqual((result["status"], result["reason"]), ("blocked", "unusable_itinerary"))
        self.assertTrue(result["hold_released"])
        self.assertEqual(svc.options["RB-1302"]["seats"], 4)

    def test_booking_service_not_accepting_is_pending_with_an_expiring_hold(self):
        svc = fresh()
        hold = held(svc, "RB-1306")
        result = commit(svc, hold["hold_id"])
        self.assertEqual((result["status"], result["reason"], result["effects"]), ("pending", "replacement_uncommitted", 1))
        self.assertIsNone(result["replacement_reference"])
        self.assertEqual(result["held_until"], hold["held_until"])
        self.assertIn("booking service acceptance and ticket reissue", result["unresolved_services"])
        self.assertEqual(svc.cases[CASE]["status"], "open")
        receipt = rb.customer_receipt("commit_rebooking", result)
        self.assertTrue(receipt.startswith("Not confirmed yet"))
        self.assertIn(hold["held_until"], receipt)
        status = rb.rebooking_status(svc, ME, result["commit_reference"], 3)
        self.assertEqual(status["status"], "still_pending")
        desk = rb.recovery_desk(svc, ME, CASE, "booking service has not accepted", 3)
        self.assertEqual((desk["status"], desk["pending_commit"]), ("routed", result["commit_reference"]))
        self.assertEqual(rb.recovery_desk(svc, ME, CASE, "again", 3)["desk_reference"], desk["desk_reference"])

    def test_repeat_commit_replays_and_never_commits_twice(self):
        for option in ("RB-1303", "RB-1306"):
            with self.subTest(option=option):
                svc = fresh()
                hold = held(svc, option)
                first = commit(svc, hold["hold_id"])
                again = commit(svc, hold["hold_id"], msgs=TWO + ["Confirm it again to be safe."])
                self.assertEqual((again["effects"], again["replay"]), (0, True))
                self.assertEqual(again["commit_reference"], first["commit_reference"])
                self.assertIsNone(rb.customer_receipt("commit_rebooking", again))
                self.assertEqual(len(svc.commits), 1)

    def test_rebooked_case_takes_no_second_hold(self):
        svc = fresh()
        commit(svc, held(svc, "RB-1303")["hold_id"])
        result = rb.hold_option(svc, ME, CASE, "RB-1306", TWO, "t")
        self.assertEqual(result["reason"], "already_rebooked")

    def test_each_conversation_gets_its_own_service(self):
        a = rb.service_for("conv-a")
        commit(a, held(a, "RB-1303", conv="conv-a")["hold_id"], conv="conv-a")
        self.assertEqual(rb.service_for("conv-b").cases[CASE]["status"], "open")


class ConversationTests(unittest.TestCase):
    def test_passenger_messages_skip_intents_and_bot_turns(self):
        class UserUttered:  # noqa: D401 - a stand-in with the class name Rasa uses
            def __init__(self, text):
                self.text = text

        class BotUttered(UserUttered):
            pass

        events = [UserUttered("/session_start"), BotUttered("Hello"), UserUttered("Rebook me"), UserUttered("Yes")]
        self.assertEqual(rb.passenger_messages(events), ["Rebook me", "Yes"])

    def test_clock_moves_per_passenger_message(self):
        svc = fresh()
        self.assertEqual(rb.clock_label(svc.now(1)), "19:06 Boston time, 12 Nov")
        self.assertEqual(rb.clock_label(svc.now(3)), "19:18 Boston time, 12 Nov")


class ReceiptPatternTests(unittest.TestCase):
    SPEC = PROJECT / "case-build" / "conversations.json"

    def test_spec_metric_is_the_library_pattern(self):
        spec = json.loads(self.SPEC.read_text())
        metric = spec["bot_text_metrics"]["confirmed_claim"]
        self.assertEqual(metric["pattern"], rb.CONFIRMED_CLAIM_PATTERN)
        self.assertEqual(metric["unless_before"], rb.CONFIRMED_HEDGE_PATTERN)

    def test_pattern_counts_claims_and_not_hedges(self):
        claim = re.compile(rb.CONFIRMED_CLAIM_PATTERN, re.IGNORECASE)
        hedge = re.compile(rb.CONFIRMED_HEDGE_PATTERN, re.IGNORECASE)

        def counted(sentence: str) -> bool:
            m = claim.search(sentence)
            return bool(m) and not hedge.search(sentence[: m.start()])

        self.assertTrue(counted("You're rebooked on HZ 402."))
        self.assertTrue(counted("Your new flight is confirmed."))
        self.assertFalse(counted("It is only confirmed after the booking service accepts it."))
        self.assertFalse(counted("You are not rebooked yet."))


class SpecTests(unittest.TestCase):
    SPEC = PROJECT / "case-build" / "conversations.json"

    def test_spec_names_only_real_tools_and_fixture_ids(self):
        spec = json.loads(self.SPEC.read_text())
        tools = {
            "search_recovery_options", "hold_recovery_option", "resume_hold", "release_hold", "commit_rebooking",
            "get_disruption_case", "check_rebooking_status", "request_recovery_desk",
        }
        data = rb.load_data()
        known = set(data["options"]) | set(data["cases"]) | set(data["holds"])
        for conv in spec["conversations"]:
            for check in conv["checks"]:
                for nested in [check, *check.get("checks", []), *check.get("steps", [])]:
                    if nested.get("tool") not in (None, "*"):
                        self.assertIn(nested["tool"], tools, conv["id"])
            text = json.dumps(conv)
            for ident in re.findall(r"\b(?:RB-\d{4}|HT-DC-\d{5}|HT-RH-\d{4})\b", text):
                self.assertIn(ident, known, f"{conv['id']}: {ident}")


if __name__ == "__main__":
    unittest.main()
