import copy
import itertools
import unittest

from offer_identity import OFFERS, field_cache, selected_offer
from renewal_terms import BASE, resolve


class OfferIdentityTests(unittest.TestCase):
    def test_every_patch_valid_against_same_base_but_hybrid_never_issued(self):
        issued = [resolve(BASE, patch) for patch in OFFERS.values()]
        for events in itertools.permutations(OFFERS.items()):
            hybrid = field_cache(events)
            self.assertEqual(hybrid, {"deductible": 100, "limit": 20000})
            self.assertNotIn(hybrid, issued)

    def test_selected_offer_survives_other_alternative_in_both_orders(self):
        for events in itertools.permutations(OFFERS.items()):
            receipt = selected_offer(events, "low-deductible")
            self.assertEqual(receipt["terms"], {"deductible": 100, "limit": 10000})
            self.assertEqual(receipt["offer_id"], "low-deductible")

    def test_selecting_second_alternative_retains_its_whole_terms(self):
        receipt = selected_offer(list(OFFERS.items()), "higher-limit")
        self.assertEqual(receipt["terms"], {"deductible": 500, "limit": 20000})

    def test_unreceived_selection_is_unresolved_not_filled_from_other_offer(self):
        self.assertEqual(selected_offer(list(OFFERS.items()), "missing"),
                         {"status": "unresolved", "offer_id": "missing"})

    def test_idempotent_repeated_offer_is_allowed_but_redefined_identity_refused(self):
        events = list(OFFERS.items())
        self.assertEqual(selected_offer(events + events, "low-deductible"),
                         selected_offer(events, "low-deductible"))
        changed = copy.deepcopy(OFFERS["low-deductible"])
        changed["terms"]["deductible"]["value"] = 200
        with self.assertRaises(ValueError):
            selected_offer(events + [("low-deductible", changed)], "low-deductible")

    def test_stale_base_still_fails_in_both_adapters(self):
        changed = copy.deepcopy(OFFERS["low-deductible"])
        changed["base_revision"] = "r0"
        for adapter in [lambda e: field_cache(e), lambda e: selected_offer(e, "x")]:
            with self.assertRaises(ValueError):
                adapter([("x", changed)])


if __name__ == "__main__":
    unittest.main()
