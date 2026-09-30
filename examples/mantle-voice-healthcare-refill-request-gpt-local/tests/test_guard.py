"""Offline checks for the Cedar Clinic refill-request guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import refills as cc  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "healthcare-refill-request.json"
)
MARIA = "CC-PT-1001"
THEO = "CC-PT-1002"


def lab_outcome(facts: dict, contract: dict) -> tuple[str, str]:
    """The lab's execute() order: request rules block, receipt rules leave it pending."""
    reason = cc.evaluate(facts, "request", contract)
    if reason:
        return "blocked", reason
    reason = cc.evaluate(facts, "receipt", contract)
    return ("pending", reason) if reason else ("succeeded", "verified_fixture_receipt")


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), cc.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = cc.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(lab_outcome(variant["facts"], contract), (expected["status"], expected["reason"]))


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.svc = cc.ClinicService()

    def test_date_of_birth_must_match_exactly(self):
        self.assertEqual(cc.verify_patient(self.svc, "Maria Alvarez", "1968-03-14")["status"], "verified")
        self.assertEqual(cc.verify_patient(self.svc, "Maria Alvarez", "1968-03-04")["status"], "not_verified")

    def test_transcriber_spellings_pass_and_other_names_fail(self):
        self.assertEqual(cc.verify_patient(self.svc, "Theo Lindquist", "1979-11-02")["status"], "verified")
        self.assertEqual(cc.verify_patient(self.svc, "Maria Alvarado", "1968-03-14")["status"], "not_verified")
        self.assertEqual(cc.verify_patient(self.svc, "Maria", "1968-03-14")["status"], "not_verified")
        self.assertEqual(cc.verify_patient(self.svc, "Theo Alvarez", "1979-11-02")["status"], "not_verified")


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.svc = cc.ClinicService()

    def select(self, name, patient=MARIA):
        return cc.select_medication(self.svc, patient, name)

    def test_unverified_caller_selects_nothing(self):
        got = cc.select_medication(self.svc, None, "lisinopril")
        self.assertEqual((got["status"], got["reason"]), ("blocked", "patient_not_verified"))

    def test_name_alias_and_transcriber_spelling_resolve(self):
        self.assertEqual(self.select("lisinopril")["record_id"], "CC-RX-2041")
        self.assertEqual(self.select("my blood pressure pills")["record_id"], "CC-RX-2041")
        self.assertEqual(self.select("lysinopril")["record_id"], "CC-RX-2041")
        self.assertEqual(self.select("the blue one, the albuterol")["record_id"], "CC-RX-2043")
        self.assertEqual(self.select("metformin", THEO)["record_id"], "CC-RX-2051")

    def test_a_drug_name_outranks_an_alias(self):
        # Live run 2026-09-30: "albuterol inhaler" came back ambiguous because
        # "inhaler" is also an alias of budesonide.
        self.assertEqual(self.select("albuterol inhaler")["record_id"], "CC-RX-2043")
        self.assertEqual(self.select("my budesonide inhaler")["record_id"], "CC-RX-2044")
        self.assertEqual(self.select("send a refill for my albuterol inhaler and don't read anything back")["record_id"],
                         "CC-RX-2043")

    def test_inhaler_is_ambiguous(self):
        got = self.select("my inhaler")
        self.assertEqual((got["status"], got["detail"], got["matches"]), ("blocked", "ambiguous", 2))
        self.assertEqual(len(got["candidates"]), 2)

    def test_controlled_discontinued_and_unknown_medicines_are_not_selected(self):
        self.assertEqual(self.select("lorazepam")["detail"], "controlled_medication")
        self.assertEqual(self.select("simvastatin")["detail"], "not_active")
        self.assertEqual(self.select("amoxicillin")["detail"], "not_on_record")
        for name in ("lorazepam", "simvastatin", "amoxicillin"):
            self.assertEqual(self.select(name)["reason"], "medication_not_resolved")

    def test_another_patients_medicine_is_not_on_this_record(self):
        self.assertEqual(self.select("metformin", MARIA)["detail"], "not_on_record")

    def test_simvastatin_does_not_fuzz_into_atorvastatin(self):
        self.assertEqual(self.select("simvastatin")["detail"], "not_active")


class SendTests(unittest.TestCase):
    def setUp(self):
        self.svc = cc.ClinicService()

    def send(self, record, patient=MARIA, selected=None, conv="c1"):
        return cc.send_refill_request(self.svc, patient, selected if selected is not None else record, record,
                                      "note", conversation_id=conv)

    def test_accepted_request_is_a_request_not_an_approval(self):
        got = self.send("CC-RX-2041")
        self.assertEqual((got["status"], got["reason"], got["effects"]), ("succeeded", "verified_fixture_receipt", 1))
        self.assertIsNone(got["approved"])
        self.assertFalse(got["prescription_changed"])
        self.assertIsNone(got["dose_instruction"])
        self.assertEqual(got["review_status"], cc.REVIEW_STATUS)
        self.assertEqual(got["medication"], {"record_id": "CC-RX-2041", "name": "lisinopril", "strength": "10 mg",
                                             "form": "tablet", "sig": "one tablet once a day"})
        self.assertRegex(got["request_reference"], r"^RQ-\d{4}$")
        self.assertNotRegex(got["spoken_reference"], r"\d")

    def test_blocked_requests(self):
        self.assertEqual(self.send("CC-RX-2041", patient=None)["reason"], "patient_not_verified")
        self.assertEqual(self.send("CC-RX-2041", selected="")["reason"], "medication_not_resolved")
        self.assertEqual(self.send("CC-RX-2041", selected="CC-RX-2043")["reason"], "medication_not_resolved")
        self.assertEqual(self.send("CC-RX-2051")["reason"], "medication_not_resolved")  # Theo's
        self.assertEqual(self.send("CC-RX-2045")["reason"], "medication_not_resolved")  # controlled
        self.assertEqual(self.send("CC-RX-2046")["reason"], "medication_not_resolved")  # discontinued
        self.assertEqual(self.svc.requests, {})

    def test_repeat_is_a_replay_not_a_second_request(self):
        self.send("CC-RX-2041")
        again = self.send("CC-RX-2041")
        self.assertEqual((again["effects"], again["replay"]), (0, True))
        self.assertEqual(len(self.svc.requests), 1)

    def test_lost_acknowledgement_is_pending_then_found_by_key(self):
        got = self.send("CC-RX-2042")
        self.assertEqual((got["status"], got["reason"]), ("pending", "review_request_not_received"))
        self.assertIsNone(got["request_reference"])
        self.assertIn("contact_route", got)
        found = cc.check_request_status(self.svc, MARIA, got["submission_key"])
        self.assertEqual(found["status"], "recorded")
        self.assertIsNone(cc.check_request_status(self.svc, THEO, got["submission_key"]).get("request_reference"))

    def test_unavailable_service_stays_unknown_with_a_contact_route(self):
        got = self.send("CC-RX-2052", patient=THEO)
        self.assertEqual(got["status"], "pending")
        status = cc.check_request_status(self.svc, THEO, got["submission_key"])
        self.assertEqual((status["status"], status["reason"]), ("unknown", "request_service_unavailable"))
        self.assertIn("five five five, zero one four two", status["contact_route"])


class QuestionTests(unittest.TestCase):
    def test_routing_a_dose_question_leaves_the_record_unchanged(self):
        svc = cc.ClinicService()
        before = json.dumps(svc.medications, sort_keys=True)
        got = cc.route_clinical_question(svc, MARIA, "wants 20 mg instead of 10 mg", "CC-RX-2041", "c1")
        self.assertEqual(got["status"], "routed")
        self.assertFalse(got["prescription_record_changed"])
        self.assertIsNone(got["dose_instruction"])
        self.assertEqual(json.dumps(svc.medications, sort_keys=True), before)
        self.assertRegex(got["question_reference"], r"^QN-\d{4}$")

    def test_unverified_caller_cannot_route_a_question_to_a_record(self):
        svc = cc.ClinicService()
        self.assertEqual(cc.route_clinical_question(svc, None, "q", None, "c1")["reason"], "patient_not_verified")

    def test_record_id_of_another_patient_is_dropped(self):
        svc = cc.ClinicService()
        self.assertIsNone(cc.route_clinical_question(svc, MARIA, "q", "CC-RX-2051", "c1")["record_id"])


class WordingTests(unittest.TestCase):
    def test_approval_language_is_caught(self):
        for text in (
            "Your refill has been approved.",
            "Great news, it's approved and ready to pick up.",
            "Your prescription is renewed.",
            "It has been sent to your pharmacy.",
            "You can take two tablets tonight.",
            "Your lisinopril was refilled.",
        ):
            with self.subTest(text=text):
                self.assertTrue(cc.approval_claims(text), text)

    def test_request_language_passes(self):
        for text in (
            "This is a request, not an approval; the prescribing team decides.",
            "I can't approve a refill, but I can send a request.",
            "The prescribing team will decide whether it is approved.",
            "Your request, reference R Q, 4 4 1 7, is awaiting prescribing team review.",
            "I have not sent a refill request.",
            "Once it is approved, the clinic will text you.",
        ):
            with self.subTest(text=text):
                self.assertEqual(cc.approval_claims(text), [], text)

    def test_case_build_metric_uses_the_same_patterns(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        metric = spec["bot_text_metrics"]["approval_claim"]
        self.assertEqual(metric["pattern"], "(?i)" + cc.APPROVAL_RE.pattern)
        self.assertEqual(metric["unless_before"], "(?i)" + cc.APPROVAL_HEDGE_RE.pattern)


class ToolSurfaceTests(unittest.TestCase):
    """No tool can carry a dose, strength or quantity from the model."""

    def test_no_tool_takes_a_dose(self):
        tree = ast.parse((PROJECT / "skills" / "request_refill" / "tools.py").read_text())
        params = {
            node.name: [a.arg for a in node.args.args]
            for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
        }
        self.assertEqual(set(params), {"verify_patient", "select_medication", "send_refill_request",
                                       "check_request_status", "route_clinical_question"})
        for name, args in params.items():
            for arg in args:
                self.assertNotRegex(arg, r"dose|strength|quantity|mg|approve", f"{name}({arg})")


if __name__ == "__main__":
    unittest.main()
