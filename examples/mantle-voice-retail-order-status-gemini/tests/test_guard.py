"""Offline checks for the Willow Shop order-status guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import orders as ws  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "retail-order-status.json"
)
DANA = "WS-CUST-5521"
RAFAEL = "WS-CUST-6034"


def lab_outcome(facts: dict, contract: dict) -> tuple[str, str]:
    """The lab's execute() order: every rule here is a request rule."""
    reason = ws.evaluate(facts, contract)
    return ("blocked", reason) if reason else ("succeeded", "verified_fixture_receipt")


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), ws.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = ws.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(lab_outcome(variant["facts"], contract), (expected["status"], expected["reason"]))

    def test_all_three_rules_are_request_rules(self):
        self.assertEqual(
            [r["field"] for r in ws.request_rules()],
            ["order_subject_resolved", "carrier_event_current", "milestone_type_explicit"],
        )


class OrganisationGuardTests(unittest.TestCase):
    def test_fixture_is_the_fictional_one(self):
        data = ws.load_data()
        self.assertEqual(ws.ORGANISATION, "Willow Shop")
        self.assertIn("(fictional", data["organisation"])
        self.assertIn("(fictional", data["carrier"])
        ws.assert_fictional(data)

    def test_unmarked_organisation_is_refused(self):
        data = ws.load_data()
        data["organisation"] = "Willow Shop"
        with self.assertRaises(ws.FictionalOrganisationError):
            ws.assert_fictional(data)

    def test_real_carrier_is_refused_even_when_marked(self):
        data = ws.load_data()
        data["carrier"] = "FedEx (fictional branch)"
        with self.assertRaises(ws.FictionalOrganisationError):
            ws.assert_fictional(data)

    def test_note_must_say_fictional(self):
        data = ws.load_data()
        data["note"] = "Sample data."
        with self.assertRaises(ws.FictionalOrganisationError):
            ws.assert_fictional(data)


class NormaliseTests(unittest.TestCase):
    def test_order_numbers_as_spoken_or_typed(self):
        for said in ("WS-10482", "ws 10482", "10482", "one zero four eight two", "one oh four eight two",
                     "W S one zero four eight two", "1 0 4 8 2"):
            with self.subTest(said=said):
                self.assertEqual(ws.normalise_order(said), "WS-10482")

    def test_wrong_length_is_not_padded(self):
        self.assertEqual(ws.normalise_order("1048"), "1048")
        self.assertNotIn(ws.normalise_order("104822"), ws.load_data()["orders"])

    def test_parcel_numbers(self):
        self.assertIsNone(ws.normalise_parcel(None))
        self.assertEqual(ws.normalise_parcel(2), 2)
        self.assertEqual(ws.normalise_parcel("second"), 2)
        self.assertEqual(ws.normalise_parcel("parcel two"), 2)
        self.assertEqual(ws.normalise_parcel("the chair"), 0)
        self.assertEqual(ws.normalise_parcel(True), 0)


class TrackOrderTests(unittest.TestCase):
    def track(self, number, parcel=None, customer=DANA):
        return ws.track_order(customer, number, parcel)

    def test_delivered_order_names_the_carrier_scan_and_time(self):
        r = self.track("10482")
        self.assertEqual(r["status"], "answered")
        self.assertEqual(r["milestone"], "delivered")
        self.assertTrue(r["delivered"])
        self.assertEqual(r["milestone_source"], "Larkspur Parcel carrier scan")
        self.assertEqual(r["event_at_spoken"], "Monday, September 28 at 2:12 PM")
        self.assertTrue(r["status_reference"].startswith("WS-ST-20260930-"))
        self.assertIsNone(r["estimate"])

    def test_label_is_never_a_delivery(self):
        r = self.track("10517")
        self.assertEqual(r["status"], "answered")
        self.assertEqual(r["milestone"], "label_created")
        self.assertEqual(r["milestone_source"], "Willow Shop warehouse")
        self.assertFalse(r["delivered"])
        self.assertFalse(r["carrier_has_parcel"])
        self.assertIn("has not been delivered", r["not_collected"])
        self.assertEqual(r["estimate"]["kind"], "checkout_estimate")
        self.assertIn("not a carrier event", r["estimate"]["meaning"])

    def test_split_order_needs_a_parcel(self):
        r = self.track("10539")
        self.assertEqual((r["status"], r["reason"], r["detail"]), ("blocked", "wrong_order", "parcel_not_selected"))
        self.assertEqual([p["items"] for p in r["parcels"]], [["desk chair"], ["cushion set"]])
        self.assertNotIn("milestone", r)

    def test_each_parcel_has_its_own_status(self):
        first, second = self.track("10539", 1), self.track("10539", "second")
        self.assertEqual((first["milestone"], first["delivered"]), ("delivered", True))
        self.assertEqual((second["milestone"], second["delivered"]), ("in_transit", False))
        self.assertNotEqual(first["status_reference"], second["status_reference"])
        self.assertIn("parcel 2 of 2 only", second["scope"])
        self.assertEqual(second["estimate"]["kind"], "carrier_estimate")

    def test_missing_parcel_is_the_subject_rule(self):
        r = self.track("10482", 2)
        self.assertEqual((r["reason"], r["detail"]), ("wrong_order", "no_such_parcel"))

    def test_someone_elses_order_looks_like_an_unknown_one(self):
        theirs, unknown = self.track("10493"), self.track("19999")
        self.assertEqual(theirs["reason"], "wrong_order")
        strip = lambda r: {k: v for k, v in r.items() if k != "order_number"}  # noqa: E731
        self.assertEqual(strip(theirs), strip(unknown))
        self.assertEqual(self.track("10493", customer=RAFAEL)["status"], "answered")

    def test_stale_carrier_feed_gives_the_last_event_and_no_prediction(self):
        r = self.track("10560")
        self.assertEqual((r["status"], r["reason"]), ("blocked", "stale_carrier_event"))
        self.assertEqual(r["last_observed"]["milestone"], "in_transit")
        self.assertEqual(r["observation_age_hours"], 65.7)
        self.assertIsNone(r["arrival_prediction"])
        self.assertNotIn("estimate", r)

    def test_unlabelled_shipped_record_is_blocked_and_not_repeated(self):
        r = self.track("10571")
        self.assertEqual((r["status"], r["reason"]), ("blocked", "label_as_delivery"))
        self.assertNotIn("SHIPPED", json.dumps(r))
        self.assertIsNone(r["milestone"])

    def test_a_label_from_a_carrier_or_a_delivery_from_the_warehouse_is_not_explicit(self):
        self.assertFalse(ws.milestone_explicit({"milestone": "delivered", "source": "warehouse"}))
        self.assertFalse(ws.milestone_explicit({"milestone": "label_created", "source": "carrier"}))
        self.assertFalse(ws.milestone_explicit({"milestone": "shipped", "source": "carrier"}))
        self.assertTrue(ws.milestone_explicit({"milestone": "in_transit", "source": "carrier"}))

    def test_facts_are_exactly_true_or_the_rule_fails(self):
        data = ws.load_data()
        data["orders"]["WS-10482"]["parcels"][0]["carrier_observed_at"] = None
        self.assertEqual(ws.track_order(DANA, "10482", data=data)["reason"], "stale_carrier_event")


class DeliveryHelpTests(unittest.TestCase):
    def test_stale_parcel_routes_with_last_event_and_no_prediction(self):
        r = ws.delivery_help(DANA, "10560")
        self.assertEqual(r["status"], "routed")
        self.assertTrue(r["reference"].startswith("WS-DH-"))
        self.assertEqual(r["last_observed"]["milestone"], "in_transit")
        self.assertIsNone(r["arrival_prediction"])

    def test_unlabelled_record_routes_without_an_event(self):
        r = ws.delivery_help(DANA, "10571")
        self.assertEqual(r["status"], "routed")
        self.assertIsNone(r["last_observed"])

    def test_help_needs_the_customer_own_single_parcel(self):
        self.assertEqual(ws.delivery_help(DANA, "10493")["reason"], "wrong_order")
        self.assertEqual(ws.delivery_help(DANA, "10539")["detail"], "parcel_not_selected")
        self.assertEqual(ws.delivery_help(DANA, "10539", 2)["status"], "routed")


class SessionTests(unittest.TestCase):
    def test_profile_and_order_list_carry_no_status(self):
        profile = ws.session_profile()
        self.assertEqual(profile["order_numbers"], ["WS-10482", "WS-10517", "WS-10539", "WS-10560", "WS-10571"])
        # Mantle cuts memory values to 100 characters in the prompt.
        self.assertLess(len(", ".join(profile["order_numbers"])), 100)
        listed = json.dumps(ws.list_orders(DANA))
        for word in ("delivered", "in_transit", "label_created", "WS-10493"):
            self.assertNotIn(word, listed)


if __name__ == "__main__":
    unittest.main()
