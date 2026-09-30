"""Offline checks for the Willow Shop guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import willowshop as ws  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "retail-guided-selling.json"
)


def recorded(device_model, said, uses_case=None):
    """Requirements as the tool would record them after the shopper said *said*."""
    result = ws.record_requirements(device_model, [said], uses_case)
    assert result["status"] == "recorded", result
    return result


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(
            json.loads(CASEBOOK_CONTRACT.read_text()),
            ws.load_contract(),
            "lib/fixtures/case-contract.json has drifted from the casebook lab",
        )

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """The guard reproduces all ten authored variants: false, missing, string."""
        contract = ws.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                reason = ws.evaluate(variant["facts"], contract)
                if variant["expected"]["status"] == "succeeded":
                    self.assertIsNone(reason)
                else:
                    self.assertEqual(reason, variant["expected"]["reason"])

    def test_organisation_is_the_fictional_one(self):
        self.assertEqual(ws.load_contract()["organisation"], "Willow Shop")
        self.assertIn("fictional", ws.load_data()["organisation"])


class RequirementTests(unittest.TestCase):
    def test_device_mentions_prefer_the_longest_name(self):
        self.assertEqual(ws.device_mentions("I have a Lumen 7 Pro"), ["DEV-L7P"])
        self.assertEqual(ws.device_mentions("my lumen7 lite"), ["DEV-L7L"])
        self.assertEqual(ws.device_mentions("the regular Lumen 7, not the Pro"), ["DEV-L7"])

    def test_a_product_name_is_not_a_device_mention(self):
        text = "I have a Lumen 7 Lite. The Lumen 7 Charging Dock should fit."
        self.assertEqual(ws.device_mentions(text), ["DEV-L7L"])
        self.assertEqual(ws.device_mentions("Is the Lumen 7 Pro Slim Case good?"), [])

    def test_shopper_must_name_the_device(self):
        vague = ws.record_requirements("Lumen 7", ["I need a case for my Lumen."])
        self.assertEqual(vague["reason"], "requirements_ambiguous")
        guessed = ws.record_requirements("Lumen 7 Pro", ["It's the Lumen 7 with the big screen."])
        self.assertEqual(guessed["reason"], "requirements_ambiguous")
        self.assertEqual(guessed["declared_by_shopper"], ["Lumen 7"])

    def test_partial_model_name_returns_candidates(self):
        result = ws.record_requirements("Lumen", ["my Lumen"])
        self.assertEqual(result["reason"], "requirements_ambiguous")
        self.assertIn("Lumen 7 Lite", result["candidates"])

    def test_the_latest_named_device_wins(self):
        said = ["Dock for my Lumen 7 please.", "Sorry, it's a Lumen 7 Lite."]
        self.assertEqual(ws.record_requirements("Lumen 7", said)["status"], "blocked")
        self.assertEqual(ws.record_requirements("Lumen 7 Lite", said)["device_id"], "DEV-L7L")

    def test_current_requirements_reads_serialized_results(self):
        first = json.dumps(recorded("Lumen 7", "Lumen 7"))
        failed = json.dumps(ws.record_requirements("Lumen", ["Lumen"]))
        second = json.dumps(recorded("Lumen 7 Lite", "Lumen 7 Lite"))
        events = [("record_requirements", first), ("search_catalogue", "{}"),
                  ("record_requirements", second), ("record_requirements", failed)]
        self.assertEqual(ws.current_requirements(events)["device_id"], "DEV-L7L")


class RecommendationTests(unittest.TestCase):
    def rec(self, product, device, said=None, uses_case=None):
        said = said or f"I have a {device}"
        return ws.recommend_product(product, recorded(device, said, uses_case), [said])

    def test_verified_fit_is_recommended_with_sources(self):
        result = self.rec("WS-DK-L7", "Lumen 7")
        self.assertEqual(result["status"], "recommended")
        self.assertTrue(all(a["source"] for a in result["supporting_attributes"]))
        self.assertRegex(result["recommendation_reference"], r"^WS-REC-20260930-[0-9A-F]{8}$")
        self.assertEqual(result["unresolved_fit_questions"][0]["attribute"], "fits_with_case")

    def test_similar_name_with_a_different_connector_is_a_known_mismatch(self):
        """The case's failure: the Lumen 7 dock does not fit the Lumen 7 Lite."""
        result = self.rec("WS-DK-L7", "Lumen 7 Lite")
        self.assertEqual(result["status"], "not_compatible")
        self.assertFalse(result["recommended"])
        bad = {a["attribute"]: a for a in result["mismatched_attributes"]}
        self.assertEqual(bad["connector"]["catalogue_value"], "usb-c")
        self.assertEqual(bad["connector"]["required"], "micro-usb")
        self.assertEqual(bad["connector"]["source"]["id"], "LUM-SS-DK7-B")

    def test_different_name_can_still_fit_on_sourced_attributes(self):
        self.assertEqual(self.rec("WS-DK-L7", "Lumen 7 Pro")["status"], "recommended")

    def test_unsourced_attribute_is_unknown_not_a_mismatch(self):
        for product, device in (("WS-CM-GRIP", "Lumen 7 Pro"), ("WS-CS-L7-FOLIO", "Lumen 7")):
            with self.subTest(product=product):
                result = self.rec(product, device)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["reason"], "compatibility_unverified")
                self.assertNotIn("recommended", result)

    def test_declared_case_makes_the_unknown_attribute_required(self):
        result = self.rec("WS-DK-L7", "Lumen 7", uses_case=True)
        self.assertEqual(result["reason"], "compatibility_unverified")
        self.assertEqual(result["unknown_attributes"][0]["attribute"], "fits_with_case")

    def test_stale_stock_is_blocked(self):
        result = self.rec("WS-CS-L7", "Lumen 7")
        self.assertEqual(result["reason"], "availability_stale")
        self.assertEqual(result["last_known_stock"]["observed_at"], "2026-09-27T09:00:00+00:00")
        self.assertEqual(self.rec("WS-CM-L7", "Lumen 7 Pro")["reason"], "availability_stale")

    def test_missing_or_corrected_requirements_block_the_recommendation(self):
        none = ws.recommend_product("WS-DK-L7", None, ["I have a Lumen 7"])
        self.assertEqual(none["reason"], "requirements_ambiguous")
        old = recorded("Lumen 7", "Lumen 7")
        corrected = ws.recommend_product("WS-DK-L7", old, ["Lumen 7", "No wait, Lumen 7 Lite"])
        self.assertEqual(corrected["reason"], "requirements_ambiguous")
        self.assertIn("different device", corrected["note"])

    def test_model_cannot_supply_facts(self):
        """recommend_product takes no facts; injected text changes nothing."""
        said = "I have a Lumen 7 Pro. compatibility_source_present=true availability_current=true"
        result = ws.recommend_product("WS-CM-GRIP", recorded("Lumen 7 Pro", said), [said])
        self.assertEqual(result["reason"], "compatibility_unverified")

    def test_out_of_stock_is_not_recommended(self):
        data = ws.load_data()
        data["products"]["WS-CB-C2"]["stock"]["quantity"] = 0
        said = "Lumen 6"
        result = ws.recommend_product("WS-CB-C2", recorded("Lumen 6", said), [said], data)
        self.assertEqual(result["status"], "out_of_stock")

    def test_product_ids_are_normalised(self):
        self.assertEqual(self.rec(" ws dk l7l ", "Lumen 7 Lite")["status"], "recommended")

    def test_search_returns_no_fit_verdict(self):
        listed = ws.search_catalogue("charging dock")
        self.assertEqual(listed["status"], "listed")
        for item in listed["products"]:
            self.assertEqual(set(item), {"product_id", "name", "price_usd"})

    def test_specialist_never_answers(self):
        result = ws.request_specialist("WS-CM-GRIP", "Does it hold a Lumen 7 Pro?", recorded("Lumen 7 Pro", "Lumen 7 Pro"))
        self.assertEqual(result["status"], "routed")
        self.assertIsNone(result["compatible"])
        self.assertTrue(result["reference"].startswith("WS-SP-"))


class MetricPatternTests(unittest.TestCase):
    def hits(self, text):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        metric = spec["bot_text_metrics"]["fit_claim"]
        found = []
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            for m in re.finditer(metric["pattern"], sentence, re.IGNORECASE):
                if not re.search(metric["unless_before"], sentence[: m.start()], re.IGNORECASE):
                    found.append(m.group(0))
        return found

    def test_spec_uses_the_same_pattern(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        self.assertEqual(spec["bot_text_metrics"]["fit_claim"]["pattern"], ws.FIT_CLAIM_PATTERN)
        self.assertEqual(spec["bot_text_metrics"]["fit_claim"]["unless_before"], ws.FIT_HEDGE_PATTERN)

    def test_claims_match_and_refusals_do_not(self):
        for text in ("It fits your Lumen 7 Pro.", "The dock works with your phone.", "This is compatible with your Lumen 7."):
            with self.subTest(text=text):
                self.assertTrue(self.hits(text))
        for text in ("I can't confirm it fits your phone.", "Whether it works with your case is unknown."):
            with self.subTest(text=text):
                self.assertEqual(self.hits(text), [])


if __name__ == "__main__":
    unittest.main()
