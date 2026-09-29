"""Offline checks for the HarborCover guard. No model, no network, no licence.

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

from lib import harborcover as hc  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent
    / "tutorials"
    / "rasa-ai-team-casebook"
    / "examples"
    / "insurance-policy-status.json"
)
ME = hc.DEMO_CUSTOMER_ID


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(
            json.loads(CASEBOOK_CONTRACT.read_text()),
            hc.load_contract(),
            "lib/fixtures/case-contract.json has drifted from the casebook lab",
        )

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """The guard reproduces all ten authored variants: false, missing, string."""
        contract = hc.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                reason = hc.evaluate(variant["facts"], contract)
                expected = variant["expected"]
                if expected["status"] == "succeeded":
                    self.assertIsNone(reason)
                else:
                    self.assertEqual(reason, expected["reason"])

    def test_string_true_is_not_true(self):
        facts = {
            "policy_subject_matched": True,
            "status_timestamp_current": "true",
            "decision_type_labeled": True,
        }
        self.assertEqual(hc.evaluate(facts), "stale_claim_status")


class StatusServiceTests(unittest.TestCase):
    def test_policy_status_is_never_a_coverage_decision(self):
        for number in ("HC-HO-440120", "HC-AU-118832", "HC-RN-330071"):
            with self.subTest(policy=number):
                result = hc.policy_status(ME, number)
                self.assertEqual(result["status"], "answered")
                self.assertEqual(result["decision_type"], "policy_status")
                self.assertIsNone(result["coverage_decision"])
                self.assertIn("not a coverage decision", result["not_a_coverage_decision"])

    def test_lapsed_policy_reports_lapsed(self):
        self.assertEqual(hc.policy_status(ME, "HC-RN-330071")["state"], "lapsed")

    def test_other_customers_and_unknown_numbers_are_indistinguishable(self):
        other = hc.policy_status(ME, "HC-HO-559034")
        unknown = hc.policy_status(ME, "HC-HO-999999")
        for result in (other, unknown):
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason"], "wrong_policy_subject")
            self.assertNotIn("state", result)
        self.assertEqual(
            {k: v for k, v in other.items() if k != "policy_number"},
            {k: v for k, v in unknown.items() if k != "policy_number"},
        )
        claim = hc.claim_status(ME, "CLM-24-0990")
        self.assertEqual(claim["reason"], "wrong_policy_subject")
        self.assertNotIn("stage", claim)

    def test_claim_outcomes_follow_the_three_rules(self):
        expected = {
            "CLM-24-0871": ("answered", None, "claim_progress"),
            "CLM-24-0913": ("answered", None, "coverage_decision"),
            "CLM-24-0952": ("blocked", "stale_claim_status", None),
            "CLM-24-0977": ("blocked", "status_as_coverage", None),
            "CLM-24-0990": ("blocked", "wrong_policy_subject", None),
        }
        for number, (status, reason, decision_type) in expected.items():
            with self.subTest(claim=number):
                result = hc.claim_status(ME, number)
                self.assertEqual(result["status"], status)
                self.assertEqual(result.get("reason"), reason)
                self.assertEqual(result.get("decision_type"), decision_type)

    def test_only_a_recorded_decision_carries_coverage_and_it_is_scoped(self):
        decided = hc.claim_status(ME, "CLM-24-0913")
        self.assertEqual(decided["coverage_decision"]["reference"], "HC-DEC-50412")
        self.assertIn("CLM-24-0913 only", decided["scope_note"])
        progress = hc.claim_status(ME, "CLM-24-0871")
        self.assertIsNone(progress["coverage_decision"])

    def test_stale_status_keeps_the_last_known_timestamp(self):
        stale = hc.claim_status(ME, "CLM-24-0952")
        self.assertEqual(stale["last_known"]["stage"], "under_review")
        self.assertEqual(stale["last_known"]["observed_at"], "2026-09-20T08:00:00+00:00")

    def test_numbers_are_normalised_before_lookup(self):
        self.assertEqual(hc.claim_status(ME, " clm 24 0871 ")["status"], "answered")

    def test_status_reference_is_dated_and_stable(self):
        first = hc.claim_status(ME, "CLM-24-0871")["status_reference"]
        self.assertRegex(first, r"^HC-ST-20260929-[0-9A-F]{8}$")
        self.assertEqual(first, hc.claim_status(ME, "CLM-24-0871")["status_reference"])


class RoutingTests(unittest.TestCase):
    def test_coverage_question_never_decides(self):
        for number in ("HC-HO-440120", "HC-AU-118832", "HC-RN-330071"):
            with self.subTest(policy=number):
                result = hc.coverage_question(ME, number, "burst pipe in the kitchen")
                self.assertEqual(result["status"], "routed")
                self.assertIsNone(result["decision"])
                self.assertTrue(result["reference"].startswith("HC-CQ-"))

    def test_coverage_question_on_someone_elses_policy_is_blocked(self):
        result = hc.coverage_question(ME, "HC-HO-559034", "fence")
        self.assertEqual(result["reason"], "wrong_policy_subject")

    def test_case_team_callback_is_scoped_to_the_caller(self):
        self.assertEqual(hc.case_team_callback(ME, "CLM-24-0952")["status"], "routed")
        self.assertEqual(hc.case_team_callback(ME, "CLM-24-0990")["status"], "blocked")


class OutputGuardPatternTests(unittest.TestCase):
    PROMISES = (
        "Good news, you're covered for that.",
        "Since the policy is active, the damage will be covered.",
        "That should be covered under your policy.",
        "We'll pay for the plumber.",
        "Your flood is probably covered.",
    )
    SAFE = (
        "An active policy is not a coverage decision.",
        "No coverage decision has been made yet.",
        "Only the claims service can decide whether this loss is covered.",
        "The claim is at the awaiting_evidence stage.",
    )

    def test_promises_match(self):
        for text in self.PROMISES:
            with self.subTest(text=text):
                self.assertTrue(hc.coverage_promises(text), text)

    def test_status_and_refusals_do_not_match(self):
        for text in self.SAFE:
            with self.subTest(text=text):
                self.assertEqual(hc.coverage_promises(text), [], text)

    def test_harness_metric_uses_the_same_pattern(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        metric = spec["bot_text_metrics"]["coverage_promise"]
        self.assertEqual(metric["pattern"], hc.COVERAGE_PROMISE_PATTERN)
        self.assertEqual(metric["unless_before"], hc.COVERAGE_HEDGE_PATTERN)
        re.compile(metric["pattern"])


class OutputHookTests(unittest.TestCase):
    """hooks.py against the installed engine's payload types (skipped without rasa)."""

    @classmethod
    def setUpClass(cls):
        try:
            import hooks  # noqa: F401
            from rasa.mantle.hooks import ModelResponsePayload, RetryModel, ToolResultPayload
        except ImportError as exc:  # bare python3 without the project venv
            raise unittest.SkipTest(f"rasa not importable: {exc}")
        cls.hooks, cls.Model, cls.Retry, cls.Tool = hooks, ModelResponsePayload, RetryModel, ToolResultPayload

    def run_hook(self, coro):
        import asyncio

        return asyncio.run(coro)

    def respond(self, sender, text):
        return self.run_hook(self.hooks.block_coverage_promises(self.Model(sender_id=sender, text=text)))

    def test_promise_without_decision_retries_then_refers(self):
        sender = "no-decision"
        for _ in range(self.hooks.MAX_CONSECUTIVE_RETRIES):
            with self.assertRaises(self.Retry) as raised:
                self.respond(sender, "Your policy is active, so you're covered.")
            self.assertIn("No tool result", raised.exception.feedback)
        replaced = self.respond(sender, "You're covered.")
        self.assertEqual(replaced.text, self.hooks.NO_DECISION_TEXT)

    def test_uncited_decision_falls_back_to_the_recorded_decision_not_a_denial(self):
        sender = "decided"
        # The engine passes the result as serialized JSON text, as dispatched.
        value = json.dumps(hc.claim_status(ME, "CLM-24-0913"))
        self.run_hook(self.hooks.remember_coverage_decisions(
            self.Tool(sender_id=sender, tool_name="get_claim_status", arguments={}, value=value)))
        for _ in range(self.hooks.MAX_CONSECUTIVE_RETRIES):
            with self.assertRaises(self.Retry) as raised:
                self.respond(sender, "Good news: the claim is covered.")
            self.assertIn("HC-DEC-50412", raised.exception.feedback)
        replaced = self.respond(sender, "The claim is covered.")
        self.assertIn("CLM-24-0913", replaced.text)
        self.assertIn("HC-DEC-50412", replaced.text)
        self.assertNotIn("no decision", replaced.text.lower())

    def test_cited_decision_passes_untouched(self):
        sender = "cited"
        value = json.dumps(hc.claim_status(ME, "CLM-24-0913"))
        self.run_hook(self.hooks.remember_coverage_decisions(
            self.Tool(sender_id=sender, tool_name="get_claim_status", arguments={}, value=value)))
        text = "Claim CLM-24-0913 is covered subject to the deductible."
        self.assertEqual(self.respond(sender, text).text, text)


if __name__ == "__main__":
    unittest.main()
