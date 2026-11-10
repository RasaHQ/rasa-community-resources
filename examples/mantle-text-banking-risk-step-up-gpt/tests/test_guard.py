"""Offline checks for the Northgate step-up guard. No model, no network, no licence.

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

from lib import northgate as ng  # noqa: E402

CASEBOOK = PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook"
CASEBOOK_CONTRACT = CASEBOOK / "examples" / "banking-risk-step-up.json"
ME = ng.DEMO_CUSTOMER_ID
PRIOR_STALE_RISK = "NB-RA-3F1C0A27"  # Harbour Lettings, assessed before its details changed
PRIOR_EXPIRED = "NB-RA-B84E5D19"  # Mum, verified at 11:16, lapsed at 11:26


def fresh() -> ng.PaymentsService:
    return ng.PaymentsService()


def assess(s, dest, amount, source="current"):
    return ng.assess_transfer(s, ME, source, dest, amount)


def verify(s, ref, code):
    ng.start_step_up(s, ME, ref)
    return ng.submit_step_up_code(s, ME, ref, code)


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), ng.load_contract(),
                         "lib/fixtures/case-contract.json has drifted from the casebook lab")

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """The guard's evaluate reproduces all ten authored variants: false, missing, string."""
        contract = ng.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                reason = ng.evaluate(variant["facts"], contract)
                expected = variant["expected"]
                if expected["status"] == "succeeded":
                    self.assertIsNone(reason)
                else:
                    self.assertEqual(reason, expected["reason"])

    def test_casebook_lab_agrees(self):
        """The lab's own prove() still passes for this contract."""
        if not (CASEBOOK / "casebook.py").is_file():
            self.skipTest("casebook tutorial not present next to this example")
        import importlib.util
        import tempfile

        spec = importlib.util.spec_from_file_location("casebook", CASEBOOK / "casebook.py")
        casebook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(casebook)
        with tempfile.TemporaryDirectory() as tmp:
            proof = casebook.prove(casebook.load_case("banking-risk-step-up"), Path(tmp) / "ledger.sqlite")
        self.assertEqual(sorted(proof["mutationsKilled"]), sorted(r["field"] for r in ng.request_rules()))

    def test_the_organisation_is_the_fictional_one(self):
        self.assertEqual(ng.load_contract()["organisation"], "Northgate Bank")
        self.assertIn("fictional", ng.load_data()["note"].lower())


class RiskAssessmentTests(unittest.TestCase):
    def test_required_levels_follow_the_fixture_policy(self):
        cases = [
            ("savings", 200, 1, "low"),
            ("Mum", 150, 1, "standard"),
            ("Mum", 1500, 2, "elevated"),
            ("Harbour Lettings", 950, 2, "high"),
            ("Ferris Builders", 600, 2, "high"),
            ("Harbour Lettings", 3000, 3, "severe"),
        ]
        for dest, amount, level, tier in cases:
            with self.subTest(dest=dest, amount=amount):
                result = assess(fresh(), dest, amount)
                self.assertEqual(result["status"], "assessed")
                self.assertEqual(result["required_level"], level)
                self.assertEqual(result["risk_tier"], tier)

    def test_memory_lines_copied_verbatim_resolve(self):
        """The first live run: GPT-5.5 passed "everyday current account (NB-ACC-3101)"."""
        result = assess(fresh(), "Mum (NB-PAY-01)", "£1,500", source="everyday current account (NB-ACC-3101)")
        self.assertEqual(result["status"], "assessed")
        self.assertEqual((result["from_account"], result["destination_id"]), ("NB-ACC-3101", "NB-PAY-01"))
        own = assess(fresh(), "instant savings account (NB-ACC-3102)", 200,
                     source="everyday current account (NB-ACC-3101)")
        self.assertEqual(own["destination_id"], "NB-ACC-3102")
        self.assertEqual(assess(fresh(), "Dan (NB-PAY-11)", 50)["reason"], "unknown_destination")

    def test_changed_payee_names_the_change(self):
        result = assess(fresh(), "my landlord", "£950")
        self.assertEqual(result["destination_id"], "NB-PAY-02")
        self.assertIn("changed at 13:10", result["risk_reasons"][0])

    def test_daily_total_to_one_payee_counts(self):
        s = fresh()
        first = assess(s, "Mum", 800)
        self.assertEqual(first["required_level"], 1)
        self.assertEqual(ng.submit_transfer(s, ME, first["assessment_ref"], "current", "Mum", 800)["status"], "succeeded")
        self.assertEqual(assess(s, "Mum", 300)["required_level"], 2)

    def test_a_new_assessment_supersedes_every_open_one(self):
        s = fresh()
        first = assess(s, "Ferris Builders", 700)
        self.assertEqual(sorted(first["superseded_assessments"]), sorted([PRIOR_STALE_RISK, PRIOR_EXPIRED]))
        second = assess(s, "Harbour Lettings", 700)
        self.assertEqual(second["superseded_assessments"], [first["assessment_ref"]])

    def test_input_problems_are_rejected_without_effects(self):
        s = fresh()
        self.assertEqual(assess(s, "Dan", 50)["reason"], "unknown_destination")  # someone else's payee
        self.assertEqual(assess(s, "NB-PAY-11", 50)["reason"], "unknown_destination")
        self.assertEqual(assess(s, "Mum", 50, source="NB-ACC-4401")["reason"], "unknown_source_account")
        self.assertEqual(assess(s, "Mum", 9000)["reason"], "insufficient_funds")
        self.assertEqual(assess(s, "Mum", "-5")["reason"], "invalid_amount")
        self.assertEqual(s.transfers, [])


class GuardTests(unittest.TestCase):
    def test_level_1_transfer_uses_the_session(self):
        s = fresh()
        a = assess(s, "savings", 200)
        result = ng.submit_transfer(s, ME, a["assessment_ref"], "current", "savings", 200)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["verification_level"], 1)
        self.assertEqual(result["verification_ref"], "NB-SES-5126-1335")
        self.assertTrue(result["decision_reference"].startswith("NB-DEC-"))
        self.assertEqual(result["required_level"], 1)

    def test_the_session_alone_cannot_send_a_changed_payee_transfer(self):
        """The case's failure: a session verified for a balance enquiry sends a changed-address transfer."""
        s = fresh()
        self.assertEqual(ng.get_balance(s, ME, "current")["status"], "answered")
        a = assess(s, "Harbour Lettings", 950)
        result = ng.submit_transfer(s, ME, a["assessment_ref"], "current", "Harbour Lettings", 950)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "insufficient_verification")
        self.assertEqual(result["effects"], 0)
        self.assertEqual(s.accounts["NB-ACC-3101"]["balance"], 3240.15)

    def test_step_up_then_send(self):
        s = fresh()
        a = assess(s, "Harbour Lettings", 950)
        sent = ng.start_step_up(s, ME, a["assessment_ref"])
        self.assertEqual(sent["status"], "challenge_sent")
        self.assertNotIn("482915", json.dumps(sent))
        self.assertEqual(ng.submit_step_up_code(s, ME, a["assessment_ref"], "482 915")["status"], "verified")
        result = ng.submit_transfer(s, ME, a["assessment_ref"], "current", "Harbour Lettings", 950)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["verification_level"], 2)
        self.assertEqual(result["evidence"]["verification"]["bound_to"], a["assessment_ref"])
        self.assertEqual(result["foreign_authorization_effects"], 0)

    def test_resend_keeps_the_same_code(self):
        s = fresh()
        a = assess(s, "Ferris Builders", 600)
        ng.start_step_up(s, ME, a["assessment_ref"])
        self.assertTrue(ng.start_step_up(s, ME, a["assessment_ref"])["resent"])
        self.assertEqual(ng.submit_step_up_code(s, ME, a["assessment_ref"], "482915")["status"], "verified")

    def test_replay_sends_nothing_new(self):
        s = fresh()
        a = assess(s, "Mum", 150)
        first = ng.submit_transfer(s, ME, a["assessment_ref"], "current", "Mum", 150)
        again = ng.submit_transfer(s, ME, a["assessment_ref"], "current", "Mum", 150)
        self.assertEqual(again["decision_reference"], first["decision_reference"])
        self.assertTrue(again["replay"])
        self.assertEqual(again["effects"], 0)
        self.assertEqual(len(s.transfers), 1)

    def test_changed_details_on_submit_is_an_old_assessment(self):
        s = fresh()
        a = assess(s, "Harbour Lettings", 900)
        verify(s, a["assessment_ref"], "482915")
        for dest, amount in (("Harbour Lettings", 2400), ("Ferris Builders", 900), ("Mum", 900)):
            with self.subTest(dest=dest, amount=amount):
                result = ng.submit_transfer(s, ME, a["assessment_ref"], "current", dest, amount)
                self.assertEqual(result["reason"], "old_risk_assessment")

    def test_prior_assessment_before_a_payee_change_is_old(self):
        result = ng.submit_transfer(fresh(), ME, PRIOR_STALE_RISK, "current", "Harbour Lettings", 1800)
        self.assertEqual(result["reason"], "old_risk_assessment")
        self.assertIn("after the assessment", result["evidence"]["risk_change_after_assessment"])

    def test_prior_verification_has_expired(self):
        result = ng.submit_transfer(fresh(), ME, PRIOR_EXPIRED, "current", "Mum", 1500)
        self.assertEqual(result["reason"], "expired_authority")
        self.assertEqual(result["evidence"]["verification"]["ref"], "NB-VER-91C7F30B")

    def test_prior_assessment_can_be_verified_again_while_current(self):
        s = fresh()
        self.assertEqual(verify(s, PRIOR_EXPIRED, "482915")["status"], "verified")
        self.assertEqual(ng.submit_transfer(s, ME, PRIOR_EXPIRED, "current", "Mum", 1500)["status"], "succeeded")

    def test_a_code_verified_for_one_transfer_does_not_authorise_another(self):
        s = fresh()
        mum = assess(s, "Mum", 1500)
        verify(s, mum["assessment_ref"], "482915")
        self.assertEqual(ng.submit_transfer(s, ME, mum["assessment_ref"], "current", "Mum", 1500)["status"], "succeeded")
        harbour = assess(s, "Harbour Lettings", 800)
        result = ng.submit_transfer(s, ME, harbour["assessment_ref"], "current", "Harbour Lettings", 800)
        self.assertEqual(result["reason"], "insufficient_verification")
        self.assertEqual(result["verification_level_held"], 1)

    def test_changing_destination_voids_the_code_and_verification(self):
        s = fresh()
        ferris = assess(s, "Ferris Builders", 700)
        verify(s, ferris["assessment_ref"], "482915")
        harbour = assess(s, "Harbour Lettings", 700)
        self.assertEqual(len(harbour["invalidated_verifications"]), 1)
        self.assertEqual(ng.submit_transfer(s, ME, ferris["assessment_ref"], "current", "Ferris Builders", 700)["reason"],
                         "old_risk_assessment")
        self.assertEqual(ng.submit_transfer(s, ME, harbour["assessment_ref"], "current", "Harbour Lettings", 700)["reason"],
                         "insufficient_verification")

    def test_the_old_code_does_not_verify_the_new_transfer(self):
        s = fresh()
        ferris = assess(s, "Ferris Builders", 700)
        ng.start_step_up(s, ME, ferris["assessment_ref"])
        harbour = assess(s, "Harbour Lettings", 700)
        self.assertEqual(ng.submit_step_up_code(s, ME, ferris["assessment_ref"], "482915")["reason"], "assessment_superseded")
        self.assertEqual(ng.submit_step_up_code(s, ME, harbour["assessment_ref"], "482915")["reason"],
                         "no_challenge_for_this_transfer")
        ng.start_step_up(s, ME, harbour["assessment_ref"])
        self.assertEqual(ng.submit_step_up_code(s, ME, harbour["assessment_ref"], "482915")["status"], "incorrect")
        self.assertEqual(ng.submit_step_up_code(s, ME, harbour["assessment_ref"], "736204")["status"], "verified")

    def test_three_wrong_codes_lock_and_suspend(self):
        s = fresh()
        a = assess(s, "Harbour Lettings", 950)
        ng.start_step_up(s, ME, a["assessment_ref"])
        statuses = [ng.submit_step_up_code(s, ME, a["assessment_ref"], c)["status"] for c in ("111111", "222222", "333333")]
        self.assertEqual(statuses, ["incorrect", "incorrect", "locked"])
        self.assertEqual(ng.submit_step_up_code(s, ME, a["assessment_ref"], "482915")["status"], "locked")
        routed = ng.suspend_transfer_and_route(s, ME, a["assessment_ref"], "code locked")
        self.assertEqual(routed["status"], "suspended")
        self.assertEqual(ng.get_balance(s, ME, "savings")["status"], "answered")

    def test_level_3_cannot_step_up_in_chat(self):
        s = fresh()
        a = assess(s, "Harbour Lettings", 3000)
        self.assertEqual(ng.start_step_up(s, ME, a["assessment_ref"])["status"], "refused")
        self.assertEqual(ng.submit_transfer(s, ME, a["assessment_ref"], "current", "Harbour Lettings", 3000)["reason"],
                         "insufficient_verification")
        self.assertTrue(ng.suspend_transfer_and_route(s, ME, a["assessment_ref"], "level 3")["reference"].startswith("NB-IRT-"))

    def test_the_model_cannot_supply_facts(self):
        """No tool takes a fact, a level or a customer id."""
        import inspect

        for fn in (ng.assess_transfer, ng.start_step_up, ng.submit_step_up_code,
                   ng.submit_transfer, ng.suspend_transfer_and_route, ng.get_balance):
            params = set(inspect.signature(fn).parameters) - {"service", "customer_id"}
            self.assertFalse(params & {"facts", "level", "required_level", "risk_evaluated_for_action",
                                       "verification_matches_risk", "authority_not_expired"}, fn.__name__)

    def test_other_customers_assessments_are_unknown(self):
        s = fresh()
        a = ng.assess_transfer(s, "NB-CUST-8840", "current", "Dan", 50)
        self.assertEqual(ng.submit_transfer(s, ME, a["assessment_ref"], "current", "Dan", 50)["reason"], "old_risk_assessment")


class MetricPatternTests(unittest.TestCase):
    def test_claims_and_non_claims(self):
        for text in ("I have sent £950 to Harbour Lettings.", "Done: £150 has been sent to Mum.",
                     "The transfer is complete.", "Your payment went through."):
            with self.subTest(text=text):
                self.assertTrue(ng.sent_claims(text))
        for text in ("Nothing has been sent.", "I have not sent anything.",
                     "Once verified, the transfer is complete.", "The transfer was not sent.",
                     "A one-time code has been sent to your registered phone ending 0917."):
            with self.subTest(text=text):
                self.assertEqual(ng.sent_claims(text), [])

    def test_harness_metric_uses_the_same_pattern(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        metric = spec["bot_text_metrics"]["sent_claim"]
        self.assertEqual(metric["pattern"], ng.SENT_CLAIM_PATTERN)
        self.assertEqual(metric["unless_before"], ng.SENT_CLAIM_HEDGE_PATTERN)
        re.compile(metric["pattern"])


class ToolSurfaceTests(unittest.TestCase):
    """The Mantle tool modules against the installed engine (skipped without rasa)."""

    @classmethod
    def setUpClass(cls):
        try:
            import rasa.mantle.tools.decorator  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest(f"rasa not importable: {exc}")

    def test_transfer_tools_import_and_default_to_the_demo_customer(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("transfer_tools", PROJECT / "skills" / "transfer_money" / "tools.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.session_customer_id(None), ME)
        self.assertEqual(module._conversation_id(), "offline")

if __name__ == "__main__":
    unittest.main()
