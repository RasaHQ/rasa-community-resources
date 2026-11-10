"""Offline checks for the Horizon Rewards guard. No model, no network, no licence.

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

from lib import horizon as hz  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "travel-redemption.json"
)
ME = hz.DEMO_MEMBER_ID
MINE = "HR-204417"


def fresh() -> hz.RewardsService:
    return hz.RewardsService()


def held(svc: hz.RewardsService, option: str, conv: str = "t") -> dict:
    result = hz.hold_reward(svc, ME, MINE, option, conv)
    assert result["status"] == "held", result
    return result


def redeem(svc: hz.RewardsService, hold_id: str, confirmed: str | None = None, conv: str = "t") -> dict:
    return hz.redeem_reward(svc, ME, MINE, confirmed if confirmed is not None else hold_id, hold_id, conv)


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(
            json.loads(CASEBOOK_CONTRACT.read_text()),
            hz.load_contract(),
            "lib/fixtures/case-contract.json has drifted from the casebook lab",
        )

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """All ten authored variants: request rules block, the receipt rule leaves it pending."""
        contract = hz.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                request = hz.evaluate(variant["facts"], "request", contract)
                receipt = hz.evaluate(variant["facts"], "receipt", contract)
                expected = variant["expected"]
                if request:
                    status, reason = "blocked", request
                elif receipt:
                    status, reason = "pending", receipt
                else:
                    status, reason = "succeeded", "verified_fixture_receipt"
                self.assertEqual((status, reason), (expected["status"], expected["reason"]))

    def test_string_true_is_not_true(self):
        facts = {"member_account_verified": True, "reward_inventory_held": "true"}
        self.assertEqual(hz.evaluate(facts, "request"), "reward_hold_missing")


class AccountTests(unittest.TestCase):
    def test_other_members_and_unknown_accounts_are_indistinguishable(self):
        svc = fresh()
        other = hz.hold_reward(svc, ME, "HR-377120", "RW-LIS-1014", "t")
        unknown = hz.hold_reward(svc, ME, "HR-999999", "RW-LIS-1014", "t")
        for result in (other, unknown):
            self.assertEqual((result["status"], result["reason"]), ("blocked", "wrong_rewards_account"))
            self.assertNotIn("points_balance", result)
        strip = lambda r: {k: v for k, v in r.items() if k != "rewards_account"}  # noqa: E731
        self.assertEqual(strip(other), strip(unknown))
        self.assertIsNone(svc.active_hold("HR-377120"))
        self.assertEqual(hz.points_balance(svc, ME, "HR-377120")["reason"], "wrong_rewards_account")

    def test_own_unverified_account_is_refused_with_its_own_next_step(self):
        result = hz.hold_reward(fresh(), ME, "HR-204418", "RW-OPO-3302", "t")
        self.assertEqual(result["reason"], "wrong_rewards_account")
        self.assertIn("identity check is not complete", result["next_step"])

    def test_account_numbers_are_normalised(self):
        for spoken in ("hr 204417", "HR204417", "204417", " HR-204417 "):
            self.assertEqual(hz.normalise_account(spoken), MINE)
        self.assertEqual(hz.points_balance(fresh(), ME, "204417")["status"], "answered")

    def test_balance_lists_the_open_mismatch(self):
        balance = hz.points_balance(fresh(), ME, MINE)
        self.assertEqual(balance["points_balance"], 86400)
        self.assertEqual([m["redemption_reference"] for m in balance["open_mismatches"]], ["HT-RD-58213"])


class HoldTests(unittest.TestCase):
    def test_hold_reserves_points_and_inventory_together(self):
        svc = fresh()
        result = held(svc, "RW-LIS-1014")
        self.assertEqual(result["points"], 42000)
        self.assertEqual(result["points_available_after_hold"], 86400 - 42000)
        self.assertEqual(svc.options["RW-LIS-1014"]["inventory"], 1)
        self.assertEqual(svc.accounts[MINE]["points_balance"], 86400, "a hold moves no points")

    def test_seat_gone_before_hold_holds_nothing(self):
        svc = fresh()
        result = hz.hold_reward(svc, ME, MINE, "RW-LIS-1019", "t")
        self.assertEqual((result["status"], result["reason"]), ("unavailable", "reward_inventory_gone"))
        self.assertIsNone(svc.active_hold(MINE))

    def test_insufficient_points_holds_nothing(self):
        result = hz.hold_reward(fresh(), ME, MINE, "RW-LIS-1016", "t")
        self.assertEqual(result["reason"], "insufficient_points")
        self.assertEqual(result["points_available"], 86400)

    def test_one_hold_at_a_time(self):
        svc = fresh()
        first = held(svc, "RW-LIS-1014")
        second = hz.hold_reward(svc, ME, MINE, "RW-LIS-1015", "t")
        self.assertEqual(second["reason"], "active_hold_exists")
        self.assertEqual(second["active_hold"]["hold_id"], first["hold_id"])

    def test_switch_releases_then_recalculates(self):
        svc = fresh()
        first = held(svc, "RW-LIS-1014")
        released = hz.release_hold(svc, ME, first["hold_id"])
        self.assertEqual((released["status"], released["points_released"]), ("released", 42000))
        self.assertEqual(svc.options["RW-LIS-1014"]["inventory"], 2)
        second = held(svc, "RW-LIS-1015")
        self.assertEqual(second["points"], 64000)
        stale = redeem(svc, first["hold_id"], confirmed=second["hold_id"])
        self.assertEqual((stale["status"], stale["reason"]), ("blocked", "reward_hold_missing"))
        self.assertEqual(svc.accounts[MINE]["points_balance"], 86400)

    def test_mismatched_reward_cannot_be_held_again(self):
        result = hz.hold_reward(fresh(), ME, MINE, "RW-MAD-0931", "t")
        self.assertEqual((result["status"], result["reason"]), ("blocked", "points_booking_mismatch"))
        self.assertEqual(result["open_redemption_reference"], "HT-RD-58213")


class RedeemTests(unittest.TestCase):
    def test_success_debits_once_and_books(self):
        svc = fresh()
        hold = held(svc, "RW-LIS-1014")
        result = redeem(svc, hold["hold_id"])
        self.assertEqual((result["status"], result["reason"]), ("succeeded", "verified_fixture_receipt"))
        self.assertEqual(result["points"]["amount"], 42000)
        self.assertEqual(result["booking"]["state"], "ticketed")
        self.assertRegex(result["booking"]["booking_reference"], r"^HZ[0-9A-F]{5}$")
        self.assertEqual((result["effects"], result["unmatched_points_booking"]), (1, 0))
        self.assertEqual(svc.accounts[MINE]["points_balance"], 86400 - 42000)

    def test_hotel_is_confirmed(self):
        svc = fresh()
        result = redeem(svc, held(svc, "RW-HTL-2207")["hold_id"])
        self.assertEqual((result["status"], result["booking"]["state"]), ("succeeded", "confirmed"))

    def test_partner_failure_is_pending_with_both_states(self):
        svc = fresh()
        hold = held(svc, "RW-OPO-3302")
        result = redeem(svc, hold["hold_id"])
        self.assertEqual((result["status"], result["reason"]), ("pending", "points_booking_mismatch"))
        self.assertEqual(result["points"]["state"], "debited")
        self.assertEqual(result["booking"]["state"], "not_ticketed")
        self.assertIsNone(result["booking"]["booking_reference"])
        self.assertEqual(result["reversal"]["state"], "unresolved")
        self.assertEqual((result["effects"], result["unmatched_points_booking"]), (1, 1))
        self.assertIs(result["facts"]["redemption_commit_reconciled"], False)

    def test_retry_after_mismatch_never_debits_twice(self):
        svc = fresh()
        hold = held(svc, "RW-OPO-3302")
        first = redeem(svc, hold["hold_id"])
        again = redeem(svc, hold["hold_id"])
        self.assertTrue(again["replay"])
        self.assertEqual(again["effects"], 0)
        self.assertEqual(again["redemption_reference"], first["redemption_reference"])
        self.assertEqual(svc.accounts[MINE]["points_balance"], 86400 - 9500)
        rehold = hz.hold_reward(svc, ME, MINE, "RW-OPO-3302", "t")
        self.assertEqual(rehold["reason"], "points_booking_mismatch")

    def test_no_hold_or_unconfirmed_hold_is_blocked(self):
        svc = fresh()
        for hold_id, confirmed in (("HT-H-00000", "HT-H-00000"), ("HT-H-7710", "HT-H-7710")):
            with self.subTest(hold=hold_id):
                result = redeem(svc, hold_id, confirmed=confirmed)
                self.assertEqual((result["status"], result["reason"]), ("blocked", "reward_hold_missing"))
        hold = held(svc, "RW-LIS-1014")
        unconfirmed = redeem(svc, hold["hold_id"], confirmed="")
        self.assertEqual(unconfirmed["reason"], "reward_hold_missing")
        self.assertEqual(svc.accounts[MINE]["points_balance"], 86400)

    def test_redemption_references_are_scoped_to_the_member(self):
        svc = fresh()
        other = hz.redemption_status(svc, ME, "HT-RD-60990")
        unknown = hz.redemption_status(svc, ME, "HT-RD-00000")
        self.assertEqual(other["status"], "not_found")
        self.assertEqual(
            {k: v for k, v in other.items() if k != "redemption_reference"},
            {k: v for k, v in unknown.items() if k != "redemption_reference"},
        )
        self.assertEqual(hz.rewards_desk_review(svc, ME, "HT-RD-60990")["status"], "not_found")

    def test_desk_review_is_idempotent_and_only_for_mismatches(self):
        svc = fresh()
        first = hz.rewards_desk_review(svc, ME, "HT-RD-58213", "no ticket")
        again = hz.rewards_desk_review(svc, ME, "HT-RD-58213")
        self.assertEqual(first["status"], "routed")
        self.assertEqual(first["desk_case"], again["desk_case"])
        self.assertTrue(again["replay"])
        self.assertEqual(hz.rewards_desk_review(svc, ME, "HT-RD-57002")["status"], "not_needed")
        self.assertEqual(hz.redemption_status(svc, ME, "HT-RD-58213")["reversal"]["state"], "requested")

    def test_each_conversation_gets_its_own_service(self):
        a = hz.service_for("conv-a")
        redeem(a, held(a, "RW-LIS-1014", "conv-a")["hold_id"], conv="conv-a")
        self.assertEqual(hz.service_for("conv-b").accounts[MINE]["points_balance"], 86400)


class SpecTests(unittest.TestCase):
    SPEC = PROJECT / "case-build" / "conversations.json"

    def test_spec_names_only_real_tools_and_fixture_ids(self):
        spec = json.loads(self.SPEC.read_text())
        tools = {
            "search_reward_options", "hold_reward", "release_hold", "redeem_reward",
            "get_points_balance", "get_redemption_status", "request_rewards_desk_review",
        }
        data = hz.load_data()
        known = set(data["options"]) | set(data["accounts"]) | set(data["holds"]) | set(data["redemptions"])
        for conv in spec["conversations"]:
            for check in conv["checks"]:
                for nested in [check, *check.get("checks", []), *check.get("steps", [])]:
                    if nested.get("tool") not in (None, "*"):
                        self.assertIn(nested["tool"], tools, conv["id"])
            text = json.dumps(conv)
            for ident in re.findall(r"\b(?:RW|HR|HT-H|HT-RD)-[A-Z0-9-]+\b", text):
                if not ident.startswith("HR-LEDGER"):
                    self.assertIn(ident, known, f"{conv['id']}: {ident}")


if __name__ == "__main__":
    unittest.main()
