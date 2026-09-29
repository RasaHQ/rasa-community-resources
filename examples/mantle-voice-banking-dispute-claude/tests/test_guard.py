"""Offline checks for the Northgate dispute guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import disputes as nd  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "banking-dispute.json"
)
PRIYA = "NB-CUST-4820"
ARJUN = "NB-CUST-4821"


def lab_outcome(facts: dict, contract: dict) -> tuple[str, str]:
    """The lab's execute() order: request rules block, receipt rules leave it pending."""
    reason = nd.evaluate(facts, "request", contract)
    if reason:
        return "blocked", reason
    reason = nd.evaluate(facts, "receipt", contract)
    return ("pending", reason) if reason else ("succeeded", "verified_fixture_receipt")


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), nd.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = nd.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(lab_outcome(variant["facts"], contract), (expected["status"], expected["reason"]))


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.svc = nd.LedgerService()

    def select(self, customer=PRIYA, **kw):
        return nd.select_transaction(self.svc, customer, **kw)

    def test_verification_is_exact_on_name_and_date(self):
        self.assertEqual(nd.verify_caller(self.svc, "priya  raghunathan", "1991-08-17")["status"], "verified")
        self.assertEqual(nd.verify_caller(self.svc, "Priya Raghunathan", "1991-08-18")["status"], "not_verified")
        self.assertEqual(nd.verify_caller(self.svc, "Priya Ragunathan", "1991-08-17")["status"], "not_verified")

    def test_unique_description_selects_one_transaction(self):
        got = self.select(merchant="brightmart", amount="2,499")
        self.assertEqual((got["status"], got["transaction_ref"]), ("selected", "NB-TXN-3101"))
        self.assertIn("2,499 rupees from Brightmart Online on 22 September", got["transaction_label"])
        self.assertIn("7 3 1 9", got["transaction_label"])

    def test_brand_names_split_or_joined_by_speech_to_text_still_match(self):
        self.assertEqual(self.select(merchant="Bright Mart online", amount="2499")["transaction_ref"], "NB-TXN-3101")
        self.assertEqual(self.select(merchant="Bright Mart")["transaction_ref"], "NB-TXN-3101")
        self.assertEqual(self.select(merchant="Lake View Fuel", amount="1850")["transaction_ref"], "NB-TXN-3102")
        self.assertEqual(self.select(merchant="Mart")["matches"], 0)

    def test_two_lakeview_charges_are_ambiguous_until_amount_or_date(self):
        both = self.select(merchant="Lakeview Fuel")
        self.assertEqual((both["status"], both["reason"], both["matches"]), ("blocked", "transaction_ambiguous", 2))
        self.assertEqual(len(both["candidates"]), 2)
        self.assertEqual(self.select(merchant="Lakeview", amount="3200")["transaction_ref"], "NB-TXN-3103")
        self.assertEqual(self.select(merchant="lakeview fuel", transaction_date="2026-09-19")["transaction_ref"],
                         "NB-TXN-3102")

    def test_someone_elses_charge_and_a_missing_charge_look_the_same(self):
        other = self.select(merchant="Brightmart Online", amount="5999")
        missing = self.select(merchant="Zenith Electronics", amount="9000")
        strip = lambda r: {k: v for k, v in r.items() if k != "described"}  # noqa: E731
        self.assertEqual(strip(other), strip(missing))
        self.assertEqual(other["candidates"], [])
        self.assertEqual(self.select(customer=ARJUN, merchant="Brightmart", amount="5999")["transaction_ref"],
                         "NB-TXN-3201")

    def test_unverified_or_empty_description_selects_nothing(self):
        self.assertFalse(self.select(customer=None, merchant="Brightmart")["caller_verified"])
        self.assertEqual(self.select(card_last_four="7319")["reason"], "transaction_ambiguous")


class FilingTests(unittest.TestCase):
    def setUp(self):
        self.svc = nd.LedgerService()

    def file(self, ref, selected=None, statement="I did not make this purchase.", customer=PRIYA, conv="c1"):
        return nd.file_dispute(self.svc, customer, ref if selected is None else selected, ref, statement, conv)

    def test_confirmed_filing_is_a_receipt_without_any_refund(self):
        got = self.file("NB-TXN-3101")
        self.assertEqual((got["status"], got["reason"], got["effects"]), ("succeeded", "verified_fixture_receipt", 1))
        self.assertTrue(got["dispute_reference"].startswith("NB-DSP-"))
        self.assertIsNone(got["reimbursement_decision"])
        self.assertIsNone(got["provisional_credit"])
        self.assertFalse(got["card_blocked"])
        self.assertIn("No refund or credit has been decided", got["next_review_step"])
        self.assertEqual(got["customer_statement"], "I did not make this purchase.")

    def test_filing_a_transaction_other_than_the_selected_one_is_refused(self):
        got = self.file("NB-TXN-3107", selected="NB-TXN-3101")
        self.assertEqual((got["status"], got["reason"], got["effects"]), ("blocked", "transaction_ambiguous", 0))
        self.assertEqual(self.svc.cases, {})

    def test_no_selection_someone_elses_or_unverified_is_refused(self):
        self.assertEqual(nd.file_dispute(self.svc, PRIYA, None, "NB-TXN-3101", "x", "c")["reason"],
                         "transaction_ambiguous")
        self.assertEqual(self.file("NB-TXN-3201")["reason"], "transaction_ambiguous")
        self.assertEqual(self.file("NB-TXN-3101", customer=None)["reason"], "transaction_ambiguous")
        self.assertEqual(self.svc.cases, {})

    def test_an_empty_statement_is_not_confirmed(self):
        got = self.file("NB-TXN-3101", statement="   ")
        self.assertEqual((got["status"], got["reason"]), ("blocked", "statement_not_confirmed"))

    def test_a_retry_is_a_replay_not_a_second_case(self):
        first = self.file("NB-TXN-3101")
        again = self.file("NB-TXN-3101")
        self.assertEqual((again["effects"], again["replay"]), (0, True))
        self.assertEqual(again["dispute_reference"], first["dispute_reference"])
        self.assertEqual(len(self.svc.cases), 1)

    def test_lost_acknowledgement_is_pending_then_found_by_submission_key(self):
        got = self.file("NB-TXN-3105")
        self.assertEqual((got["status"], got["reason"], got["effects"]), ("pending", "case_not_recorded", 1))
        self.assertIsNone(got["dispute_reference"])
        found = nd.check_dispute_status(self.svc, PRIYA, got["submission_key"])
        self.assertEqual(found["status"], "recorded")
        self.assertTrue(found["dispute_reference"].startswith("NB-DSP-"))
        self.assertIsNone(found["reimbursement_decision"])

    def test_unavailable_case_service_is_pending_and_routed(self):
        got = self.file("NB-TXN-3106")
        self.assertEqual(got["status"], "pending")
        status = nd.check_dispute_status(self.svc, PRIYA, got["submission_key"])
        self.assertEqual((status["status"], status["reason"]), ("unknown", "case_service_unavailable"))
        routed = nd.route_disputes_desk(self.svc, PRIYA, got["submission_key"], "not confirmed")
        self.assertEqual((routed["status"], routed["dispute_status"]), ("routed", "pending"))
        self.assertEqual(nd.route_disputes_desk(self.svc, ARJUN, got["submission_key"], "x")["status"], "refused")

    def test_card_block_is_separate_from_the_dispute(self):
        dispute = self.file("NB-TXN-3101")
        block = nd.request_card_block(self.svc, PRIYA, "7319", "c1")
        self.assertEqual((block["status"], block["dispute_changed"]), ("succeeded", False))
        self.assertTrue(block["reference"].startswith("NB-BLK-"))
        self.assertNotEqual(block["reference"], dispute["dispute_reference"])
        self.assertEqual(nd.request_card_block(self.svc, PRIYA, "5530", "c1")["reason"], "card_not_owned")
        self.assertEqual(self.svc.cards["NB-CARD-4811"]["state"], "active")

    def test_each_conversation_gets_its_own_service(self):
        a, b = nd.service_for("conv-a"), nd.service_for("conv-b")
        nd.file_dispute(a, PRIYA, "NB-TXN-3101", "NB-TXN-3101", "not me", "conv-a")
        self.assertEqual(b.cases, {})
        self.assertIs(nd.service_for("conv-a"), a)


class WriteOnceMemory:
    """Mantle's project memory rule: a set project field cannot be overwritten."""

    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        if key.startswith("project.") and self.values.get(key) is not None:
            raise ValueError(f"Project memory field '{key}' is already set and cannot be overwritten.")
        self.values[key] = value


class FakeContext:
    def __init__(self):
        self.memory = WriteOnceMemory()


class ToolTests(unittest.TestCase):
    """skills/open_dispute/tools.py against a write-once memory (skipped without rasa)."""

    @classmethod
    def setUpClass(cls):
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("open_dispute_tools", PROJECT / "skills/open_dispute/tools.py")
            cls.tools = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.tools)
        except ImportError as exc:
            raise unittest.SkipTest(f"rasa not installed: {exc}")

    def run_tool(self, coro):
        import asyncio

        return json.loads(json.dumps(asyncio.run(coro).llm_response))

    def test_failed_then_corrected_verification_succeeds(self):
        ctx = FakeContext()
        self.assertEqual(self.run_tool(self.tools.verify_caller("Priya Raghunathan", "1991-08-18", context=ctx))["status"],
                         "not_verified")
        second = self.run_tool(self.tools.verify_caller("Priya Raghunathan", "1991-08-17", context=ctx))
        self.assertEqual(second["status"], "verified")
        self.assertNotIn("customer_id", second)

    def test_a_correction_replaces_the_selection(self):
        ctx = FakeContext()
        self.run_tool(self.tools.verify_caller("Priya Raghunathan", "1991-08-17", context=ctx))
        self.run_tool(self.tools.select_transaction(merchant="Cinnabar Streaming", context=ctx))
        self.assertEqual(ctx.memory.get("selected_transaction_ref"), "NB-TXN-3107")
        self.run_tool(self.tools.select_transaction(merchant="Lakeview Fuel", context=ctx))
        self.assertEqual(ctx.memory.get("selected_transaction_ref"), "")
        refused = self.run_tool(self.tools.file_dispute("NB-TXN-3107", "not mine", context=ctx))
        self.assertEqual(refused["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
