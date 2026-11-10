"""Offline checks for the Northgate block-card guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import northgate as ng  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "banking-block-card.json"
)
NADIA = "NB-CUST-7310"
MARCUS_CARD = "NB-CARD-0201"


def lab_outcome(facts: dict, contract: dict) -> tuple[str, str]:
    """The lab's execute() order: request rules block, receipt rules leave it pending."""
    reason = ng.evaluate(facts, "request", contract)
    if reason:
        return "blocked", reason
    reason = ng.evaluate(facts, "receipt", contract)
    return ("pending", reason) if reason else ("succeeded", "verified_fixture_receipt")


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), ng.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = ng.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(lab_outcome(variant["facts"], contract), (expected["status"], expected["reason"]))


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.svc = ng.CardService()

    def select(self, ending, kind=None, customer=NADIA):
        return ng.select_card(self.svc, customer, ending, kind)

    def test_verification_is_exact_on_name_and_date(self):
        self.assertEqual(ng.verify_caller(self.svc, "nadia  okafor", "1986-03-14")["status"], "verified")
        self.assertEqual(ng.verify_caller(self.svc, "Nadia Okafor", "1986-03-15")["status"], "not_verified")
        self.assertEqual(ng.verify_caller(self.svc, "Nadia Okafur", "1986-03-14")["status"], "not_verified")

    def test_unverified_session_owns_no_card(self):
        result = self.select("4417", customer=None)
        self.assertEqual((result["status"], result["reason"]), ("blocked", "card_not_owned"))
        self.assertFalse(result["caller_verified"])

    def test_someone_elses_card_and_a_missing_card_look_the_same(self):
        other, missing = self.select("3356"), self.select("9999")
        self.assertEqual(other["reason"], "card_not_owned")
        strip = lambda r: {k: v for k, v in r.items() if k != "card_last_four"}  # noqa: E731
        self.assertEqual(strip(other), strip(missing))

    def test_shared_ending_is_ambiguous_until_the_kind_is_given(self):
        self.assertEqual(self.select("5502")["reason"], "ambiguous_card_selection")
        self.assertEqual(self.select("5502", "credit")["card_ref"], "NB-CARD-0104")
        self.assertEqual(self.select(" 5 5 0 2 ", "Debit")["card_ref"], "NB-CARD-0103")

    def test_block_changes_only_the_selected_card(self):
        ref = self.select("4417")["card_ref"]
        result = ng.block_card(self.svc, NADIA, ref, ref, "conv-1")
        self.assertEqual((result["status"], result["reason"], result["effects"]),
                         ("succeeded", "verified_fixture_receipt", 1))
        self.assertEqual(result["unselected_cards_changed"], 0)
        self.assertEqual(result["cards_after"][ref], "blocked")
        self.assertEqual(sum(s == "blocked" for s in result["cards_after"].values()), 1)
        self.assertFalse(result["replacement_ordered"])
        self.assertEqual(self.svc.cards[MARCUS_CARD]["state"], "active")

    def test_block_of_a_card_other_than_the_confirmed_one_is_refused(self):
        selected = self.select("4417")["card_ref"]
        result = ng.block_card(self.svc, NADIA, selected, "NB-CARD-0102", "conv-1")
        self.assertEqual((result["status"], result["reason"], result["effects"]),
                         ("blocked", "ambiguous_card_selection", 0))
        self.assertEqual(self.svc.cards["NB-CARD-0102"]["state"], "active")

    def test_block_without_a_selection_or_verification_is_refused(self):
        self.assertEqual(ng.block_card(self.svc, NADIA, None, "NB-CARD-0101", "c")["reason"],
                         "ambiguous_card_selection")
        self.assertEqual(ng.block_card(self.svc, None, "NB-CARD-0101", "NB-CARD-0101", "c")["reason"],
                         "card_not_owned")
        self.assertEqual(ng.block_card(self.svc, NADIA, MARCUS_CARD, MARCUS_CARD, "c")["reason"],
                         "card_not_owned")
        self.assertTrue(all(c["state"] == "active" for c in self.svc.cards.values()))

    def test_unreadable_block_is_pending_and_refuses_a_replacement(self):
        ref = self.select("6158")["card_ref"]
        result = ng.block_card(self.svc, NADIA, ref, ref, "conv-2")
        self.assertEqual((result["status"], result["reason"], result["effects"]), ("pending", "block_not_verified", 1))
        self.assertEqual(ng.check_card_status(self.svc, NADIA, ref)["status"], "unknown")
        self.assertEqual(ng.order_replacement_card(self.svc, NADIA, ref)["status"], "refused")
        self.assertEqual(ng.route_urgent_support(self.svc, NADIA, ref, "not confirmed")["status"], "routed")

    def test_second_block_is_a_replay_without_a_new_effect(self):
        ref = self.select("8023")["card_ref"]
        ng.block_card(self.svc, NADIA, ref, ref, "c")
        again = ng.block_card(self.svc, NADIA, ref, ref, "c")
        self.assertEqual((again["status"], again["effects"], again["replay"]), ("succeeded", 0, True))

    def test_replacement_only_after_a_confirmed_block(self):
        ref = self.select("4417")["card_ref"]
        self.assertEqual(ng.order_replacement_card(self.svc, NADIA, ref)["status"], "refused")
        ng.block_card(self.svc, NADIA, ref, ref, "c")
        self.assertEqual(ng.order_replacement_card(self.svc, NADIA, ref)["status"], "ordered")

    def test_each_conversation_gets_its_own_card_service(self):
        a, b = ng.service_for("conv-a"), ng.service_for("conv-b")
        a.set_blocked("NB-CARD-0101")
        self.assertEqual(b.cards["NB-CARD-0101"]["state"], "active")
        self.assertIs(ng.service_for("conv-a"), a)


class WriteOnceMemory:
    """Mantle's project memory rule, as observed live: a set field cannot be overwritten."""

    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        if key.startswith("project.") and self.values.get(key) not in (None,):
            raise ValueError(f"Project memory field '{key}' is already set and cannot be overwritten.")
        self.values[key] = value


class FakeContext:
    def __init__(self):
        self.memory = WriteOnceMemory()


class ToolTests(unittest.TestCase):
    """skills/block_card/tools.py against a write-once memory (skipped without rasa)."""

    @classmethod
    def setUpClass(cls):
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("block_card_tools", PROJECT / "skills/block_card/tools.py")
            cls.tools = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.tools)
        except ImportError as exc:
            raise unittest.SkipTest(f"rasa not installed: {exc}")

    def run_tool(self, coro):
        import asyncio

        return json.loads(json.dumps(asyncio.run(coro).llm_response))

    def test_failed_then_corrected_verification_succeeds(self):
        ctx = FakeContext()
        first = self.run_tool(self.tools.verify_caller("Nadia Okafor", "1986-03-15", context=ctx))
        self.assertEqual(first["status"], "not_verified")
        second = self.run_tool(self.tools.verify_caller("Nadia Okafor", "1986-03-14", context=ctx))
        self.assertEqual(second["status"], "verified")
        self.assertEqual(ctx.memory.get("project.verified_customer_id"), NADIA)
        self.assertNotIn("customer_id", second)

    def test_a_verified_call_cannot_switch_customer(self):
        ctx = FakeContext()
        self.run_tool(self.tools.verify_caller("Nadia Okafor", "1986-03-14", context=ctx))
        other = self.run_tool(self.tools.verify_caller("Marcus Okafor", "1984-11-02", context=ctx))
        self.assertEqual(other["reason"], "already_verified_as_another_customer")
        self.assertEqual(ctx.memory.get("project.verified_customer_id"), NADIA)


if __name__ == "__main__":
    unittest.main()
