"""Offline checks for the HarborCover roadside guard. No model, no network, no licence.

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

from lib import roadside as hc  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "insurance-roadside.json"
)
MARIA, JAMES, PRIYA, KEVIN = "HC-AU-440218", "HC-AU-517306", "HC-AU-362941", "HC-AU-608175"
MARIA_EV, JAMES_PICKUP, PRIYA_VAN, PRIYA_HATCH, KEVIN_EV = (
    "VEH-4402-1", "VEH-5173-1", "VEH-3629-1", "VEH-3629-2", "VEH-6081-1")


class UserUttered:
    def __init__(self, text):
        self.text, self.metadata = text, {}


class BotUttered:
    def __init__(self, text, utter_action=None):
        self.text = text
        self.metadata = {"utter_action": utter_action} if utter_action else {}


def lab_outcome(facts: dict, contract: dict) -> tuple[str, str]:
    """The lab's execute() order: request rules block, receipt rules leave it pending."""
    reason = hc.evaluate(facts, "request", contract)
    if reason:
        return "blocked", reason
    reason = hc.evaluate(facts, "receipt", contract)
    return ("pending", reason) if reason else ("succeeded", "verified_fixture_receipt")


def question_for(service: hc.RoadsideService, draft: hc.Draft) -> str:
    """The engine's question as responses.yml renders it from memory."""
    template = (PROJECT / "skills" / "roadside_dispatch" / "responses.yml").read_text()
    text = " ".join(template.split("- text: >", 1)[1].split())
    for key, value in hc.memory_values(service, draft).items():
        text = text.replace("{" + key + "}", value)
    return text


def confirmed(service, draft, answer="Yes."):
    return hc.conversation_from_events([UserUttered("/session_start"), UserUttered("My car broke down."),
                                        BotUttered(question_for(service, draft), hc.CONFIRM_UTTER),
                                        UserUttered(answer)])


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), hc.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = hc.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(lab_outcome(variant["facts"], contract), (expected["status"], expected["reason"]))

    def test_question_carries_the_contract_question(self):
        self.assertIn(hc.load_contract()["question"],
                      " ".join((PROJECT / "skills/roadside_dispatch/responses.yml").read_text().split()))


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_contracts_fictional_organisation(self):
        self.assertEqual(hc.ORGANISATION, hc.load_contract()["organisation"])
        hc.assert_fictional(hc.load_data(), hc.load_contract())

    def test_anything_off_the_allowlist_is_refused(self):
        contract, data = hc.load_contract(), hc.load_data()
        renamed = json.loads(json.dumps(data))
        renamed["providers"]["PRV-RT"]["name"] = "Some Real Tow Company"
        unmarked = json.loads(json.dumps(data))
        unmarked["providers"]["PRV-EF"]["fictional"] = False
        for bad in ({**data, "organisation": "HarborCover"}, {**data, "organisation": "Other Insurer (fictional)"},
                    {**data, "note": "Policy export."}, {**data, "case_slug": "insurance-file-claim"},
                    renamed, unmarked):
            with self.assertRaises(hc.FictionalOrganisationError):
                hc.assert_fictional(bad, contract)

    def test_memory_values_fit_mantles_limit(self):
        svc = hc.RoadsideService("mem")
        for policy, p in svc.policies.items():
            for vehicle_ref in p["vehicles"]:
                for place in svc.places:
                    for service in hc.SERVICES:
                        draft = hc.Draft("HC-RD-123456", 9, policy, vehicle_ref, service, place, "x", "x")
                        for value in hc.memory_values(svc, draft).values():
                            self.assertLessEqual(len(value), hc.MEMORY_VALUE_LIMIT, value)


class ParsingTests(unittest.TestCase):
    def setUp(self):
        self.svc = hc.RoadsideService("parse")

    def test_policy_digits_however_said(self):
        for said in ("HC-AU-440218", "440218", "four four oh two one eight", "4 4 0 2 1 8"):
            self.assertEqual(hc.policy_digits(said), "440218", said)

    def test_places_from_the_callers_words(self):
        cases = {
            "Route twelve northbound, just past exit fourteen, on my way home": "R12-N-EXIT14",
            "exit 16 on Route 12": "R12-N-EXIT16",
            "mile marker thirty-seven, southbound": "R12-S-MM37",
            "the Kestrel Plaza parking lot": "KESTREL-PLAZA",
            "2,150 Harbor Road": "HARBOR-MARKET",
            "the ferry terminal lot": "FERRY-LOT",
        }
        for words, place in cases.items():
            self.assertEqual(self.svc.resolve_place(words, JAMES), ([place], "caller_described"), words)

    def test_the_policy_address_only_when_the_caller_says_the_car_is_there(self):
        self.assertEqual(self.svc.resolve_place("in my driveway", JAMES),
                         (["HOME-BIRCH"], "policy_address_named_by_caller"))
        self.assertEqual(self.svc.resolve_place("somewhere on Route 12, heading home", JAMES)[0], [])
        # Another policyholder's home is never a match.
        self.assertEqual(self.svc.resolve_place("9 Linden Way", JAMES)[0], [])


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.svc = hc.RoadsideService("test")

    def draft(self, policy=JAMES, vehicle=JAMES_PICKUP, service="tow", location="exit 14", preferred=None):
        result, draft = hc.start_dispatch_draft(self.svc, policy, vehicle, service, location, preferred)
        self.assertIsNotNone(draft, result)
        return result, draft

    def dispatch(self, draft, conversation=None, memory=None):
        memory = memory if memory is not None else hc.memory_values(self.svc, draft)
        return hc.request_dispatch(self.svc, draft.draft_id, memory, conversation or confirmed(self.svc, draft))

    def test_find_policy_needs_the_digits_and_the_surname(self):
        self.assertEqual(hc.find_policy(self.svc, "four four oh two one eight", "Delgado")["status"], "found")
        self.assertEqual(hc.find_policy(self.svc, "440218", "Whitfield")["status"], "not_found")
        found = hc.find_policy(self.svc, "HC-AU-362941", "raman")
        self.assertEqual([v["vehicle_ref"] for v in found["vehicles"]], [PRIYA_VAN, PRIYA_HATCH])
        self.assertNotIn("Quarry", json.dumps(found))  # the registered address is never offered as a place

    def test_confirmed_place_and_suitable_provider_dispatch_once(self):
        _, draft = self.draft()
        done = self.dispatch(draft)
        self.assertEqual((done["status"], done["provider"], done["location_ref"]),
                         ("succeeded", "Ridgeline Towing", "R12-N-EXIT14"))
        self.assertEqual(done["arrival_estimate"]["minutes"], 25)
        self.assertEqual(done["dispatched_to_unconfirmed_location"], 0)
        self.assertRegex(done["assistance_ref"], r"^HC-RSA-\d{6}$")
        again = self.dispatch(draft)
        self.assertTrue(again["replay"])
        self.assertEqual(len(self.svc.dispatches), 1)

    def test_unanswered_or_stale_question_sends_nothing(self):
        _, draft = self.draft()
        asked = hc.conversation_from_events([BotUttered(question_for(self.svc, draft), hc.CONFIRM_UTTER)])
        self.assertEqual(self.dispatch(draft, asked)["reason"], "wrong_incident_location")
        stale_conversation = confirmed(self.svc, draft)
        stale_memory = hc.memory_values(self.svc, draft)
        hc.update_dispatch_draft(self.svc, draft.draft_id, location="exit 16")
        blocked = hc.request_dispatch(self.svc, draft.draft_id, stale_memory, stale_conversation)
        self.assertEqual((blocked["status"], blocked["reason"], blocked["effects"]),
                         ("blocked", "wrong_incident_location", 0))
        # Memory updated but the caller was asked about exit 14, not exit 16.
        self.assertEqual(hc.request_dispatch(self.svc, draft.draft_id, hc.memory_values(self.svc, draft),
                                             stale_conversation)["reason"], "wrong_incident_location")
        self.assertEqual(self.svc.dispatches, [])
        done = self.dispatch(draft)
        self.assertEqual((done["status"], done["location_ref"]), ("succeeded", "R12-N-EXIT16"))

    def test_no_question_at_all_sends_nothing(self):
        _, draft = self.draft()
        blocked = self.dispatch(draft, hc.Conversation())
        self.assertEqual(blocked["reason"], "wrong_incident_location")

    def test_electric_car_never_gets_a_wheel_lift(self):
        result, draft = self.draft(KEVIN, KEVIN_EV, "tow", "exit 16", preferred="Ridgeline Towing")
        self.assertEqual(result["preferred_provider"]["used"], False)
        self.assertIn("flatbed", result["preferred_provider"]["why_not"])
        self.assertEqual(result["provider_if_sent_now"], "Easton Flatbed Services")
        done = self.dispatch(draft)
        self.assertEqual(done["provider"], "Easton Flatbed Services")

    def test_suitable_preferred_provider_is_used(self):
        result, draft = self.draft(JAMES, JAMES_PICKUP, "tow", "exit 14", preferred="Easton Flatbed")
        self.assertTrue(result["preferred_provider"]["used"])
        self.assertEqual(self.dispatch(draft)["provider"], "Easton Flatbed Services")

    def test_heavy_van_with_no_heavy_tow_nearby_is_blocked_and_routed(self):
        result, draft = self.draft(PRIYA, PRIYA_VAN, "tow", "Kestrel Plaza")
        self.assertTrue(result["no_suitable_provider_nearby"])
        blocked = self.dispatch(draft)
        self.assertEqual((blocked["status"], blocked["reason"], blocked["effects"]),
                         ("blocked", "unsuitable_provider", 0))
        routed = hc.route_dispatch_desk(self.svc, "no heavy tow", draft.draft_id)
        self.assertEqual((routed["status"], routed["dispatched"]), ("routed", False))
        self.assertEqual(self.svc.dispatches, [])

    def test_decline_keeps_the_reference_and_tries_the_next_provider(self):
        _, draft = self.draft(MARIA, MARIA_EV, "tow", "Kestrel Plaza")
        first = self.dispatch(draft)
        self.assertEqual((first["status"], first["reason"], first["provider_acceptance"]),
                         ("pending", "provider_not_accepted", "declined"))
        self.assertIsNone(first["arrival_estimate"])
        second = hc.request_next_provider(self.svc, first["assistance_ref"])
        self.assertEqual((second["status"], second["provider"], second["assistance_ref"]),
                         ("succeeded", "Easton Flatbed Services", first["assistance_ref"]))
        self.assertEqual([d["provider_ref"] for d in self.svc.dispatches], ["PRV-HH", "PRV-EF"])

    def test_no_acceptance_yet_is_pending_with_no_time(self):
        _, draft = self.draft(KEVIN, KEVIN_EV, "flat tire", "at my house")
        first = self.dispatch(draft)
        self.assertEqual((first["status"], first["provider_acceptance"], first["arrival_estimate"]),
                         ("pending", "awaiting_provider", None))
        later = hc.check_dispatch(self.svc, first["assistance_ref"])
        self.assertEqual((later["status"], later["arrival_estimate"]["minutes"]), ("succeeded", 20))

    def test_accepted_without_an_estimate_gives_none(self):
        _, draft = self.draft(PRIYA, PRIYA_HATCH, "lockout", "ferry terminal")
        done = self.dispatch(draft)
        self.assertEqual((done["status"], done["provider"], done["arrival_estimate"]),
                         ("succeeded", "Coastline Roadside", None))
        self.assertIn("have not given an arrival time", hc.customer_receipt("request_dispatch", done))

    def test_correction_after_dispatch_is_refused(self):
        _, draft = self.draft()
        self.dispatch(draft)
        self.assertEqual(hc.update_dispatch_draft(self.svc, draft.draft_id, location="exit 16")[0]["status"],
                         "already_dispatched")

    def test_each_conversation_has_its_own_desk(self):
        a, b = hc.service_for("conv-a"), hc.service_for("conv-b")
        hc.start_dispatch_draft(a, JAMES, JAMES_PICKUP, "tow", "exit 14")
        self.assertEqual(b.drafts, {})


class ReceiptTests(unittest.TestCase):
    """The tool's own message: reference and provider answer, refusals and desk routes."""

    def setUp(self):
        self.svc = hc.RoadsideService("receipt")

    def test_every_outcome_the_caller_must_hear_has_a_message_with_its_reference(self):
        _, draft = hc.start_dispatch_draft(self.svc, MARIA, MARIA_EV, "tow", "Kestrel Plaza")
        declined = hc.request_dispatch(self.svc, draft.draft_id, hc.memory_values(self.svc, draft),
                                       confirmed(self.svc, draft))
        text = hc.customer_receipt("request_dispatch", declined)
        self.assertIn("declined", text)
        self.assertIn(declined["assistance_ref_spoken"], text)
        self.assertIn("Nobody is on the way", text)
        accepted = hc.request_next_provider(self.svc, declined["assistance_ref"])
        text = hc.customer_receipt("request_next_provider", accepted)
        self.assertIn("45 minutes", text)
        self.assertIn(accepted["assistance_ref_spoken"], text)
        routed = hc.route_dispatch_desk(self.svc, "caller asked", assistance_ref=accepted["assistance_ref"])
        self.assertIn(routed["desk_ref_spoken"], hc.customer_receipt("route_dispatch_desk", routed))
        refused, _ = hc.start_dispatch_draft(self.svc, KEVIN, KEVIN_EV, "tow", "exit 16", "Ridgeline")
        self.assertTrue(hc.customer_receipt("start_dispatch_draft", refused).startswith("I can't send Ridgeline"))

    def test_replays_and_drafts_send_nothing(self):
        result, draft = hc.start_dispatch_draft(self.svc, JAMES, JAMES_PICKUP, "tow", "exit 14")
        self.assertIsNone(hc.customer_receipt("start_dispatch_draft", result))
        memory, conversation = hc.memory_values(self.svc, draft), confirmed(self.svc, draft)
        hc.request_dispatch(self.svc, draft.draft_id, memory, conversation)
        replay = hc.request_dispatch(self.svc, draft.draft_id, memory, conversation)
        self.assertIsNone(hc.customer_receipt("request_dispatch", replay))

    def test_spoken_reference_has_every_digit(self):
        self.assertEqual(hc.spoken("HC-RSA-482173"), "four eight two, one seven three")
        digits = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
                  "seven": "7", "eight": "8", "nine": "9"}
        self.assertEqual("".join(digits[w] for w in re.findall(r"[a-z]+", hc.spoken("HC-RDD-906154"))), "906154")


if __name__ == "__main__":
    unittest.main()
