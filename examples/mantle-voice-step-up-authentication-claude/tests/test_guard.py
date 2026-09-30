"""Offline checks for the Orchard Works step-up guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import access as ow  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "step-up-authentication.json"
)
TARA, DANIEL, OWEN, RACHEL, GRACE = "OW-EMP-1042", "OW-EMP-1107", "OW-EMP-0310", "OW-EMP-1215", "OW-EMP-1330"


def lab_outcome(facts: dict, contract: dict) -> tuple[str, str]:
    """The lab's execute() order: request rules block, receipt rules leave it pending."""
    reason = ow.evaluate(facts, "request", contract)
    if reason:
        return "blocked", reason
    reason = ow.evaluate(facts, "receipt", contract)
    return ("pending", reason) if reason else ("succeeded", "verified_fixture_receipt")


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), ow.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = ow.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(lab_outcome(variant["facts"], contract), (expected["status"], expected["reason"]))


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_contracts_fictional_organisation(self):
        self.assertEqual(ow.ORGANISATION, ow.load_contract()["organisation"])
        ow.assert_fictional(ow.load_data(), ow.load_contract())

    def test_unmarked_or_foreign_organisation_is_refused(self):
        contract = ow.load_contract()
        for change in ({"organisation": "Orchard Works"}, {"note": "Directory export."},
                       {"organisation": "Some Other Company (fictional)"}, {"case_slug": "retail-return"}):
            with self.subTest(change=change):
                with self.assertRaises(ow.FictionalOrganisationError):
                    ow.assert_fictional({**ow.load_data(), **change}, contract)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.svc = ow.IdentityService("test")

    def verified(self, name="Tara Brennan", action="unlock_account"):
        prepared = ow.prepare_access_request(self.svc, name, action)
        sent = ow.start_verification(self.svc, prepared["request_ref"], prepared["request_ref"])
        return prepared, sent

    def test_a_name_match_authorizes_nothing(self):
        prepared = ow.prepare_access_request(self.svc, "owen  MERCER", "reset my password")
        self.assertEqual((prepared["status"], prepared["employee_ref"], prepared["action"]),
                         ("prepared", OWEN, "reset_password"))
        self.assertFalse(prepared["name_match_authorizes"])
        self.assertEqual(self.svc.changes, [])

    def test_unknown_name_and_unclear_action(self):
        self.assertEqual(ow.prepare_access_request(self.svc, "Tara Brenan", "unlock_account")["status"], "not_found")
        self.assertEqual(ow.prepare_access_request(self.svc, "Tara Brennan", "fix it")["status"], "unsupported_action")

    def test_verification_needs_the_request_the_engine_confirmed(self):
        first = ow.prepare_access_request(self.svc, "Tara Brennan", "reset_password")
        second = ow.prepare_access_request(self.svc, "Tara Brennan", "unlock_account")
        refused = ow.start_verification(self.svc, first["request_ref"], second["request_ref"])
        self.assertEqual((refused["status"], refused["reason"]), ("blocked", "not_the_confirmed_request"))

    def test_approved_challenge_changes_exactly_one_thing_once(self):
        prepared, sent = self.verified()
        self.assertEqual(ow.check_verification(self.svc, sent["challenge_ref"])["status"], "approved")
        done = ow.change_access(self.svc, sent["challenge_ref"], TARA, "unlock_account")
        self.assertEqual((done["status"], done["reason"], done["effects"]), ("succeeded", "verified_fixture_receipt", 1))
        self.assertEqual(done["scope"], {"employee_ref": TARA, "action": "unlock_account"})
        self.assertTrue(done["access_before"]["account_locked"])
        self.assertFalse(done["access_after"]["account_locked"])
        self.assertFalse(done["access_after"]["password_reset_pending"])
        self.assertEqual(done["executed_without_all_bindings"], 0)
        self.assertRegex(done["authorization_ref"], r"^OW-AUTH-\d{6}$")
        again = ow.change_access(self.svc, sent["challenge_ref"], TARA, "unlock_account")
        self.assertEqual((again["status"], again["reason"], again["challenge_state"]),
                         ("blocked", "challenge_not_verified", "consumed"))
        self.assertEqual(len(self.svc.changes), 1)

    def test_change_before_the_approval_is_read_is_refused(self):
        _, sent = self.verified()
        early = ow.change_access(self.svc, sent["challenge_ref"], TARA, "unlock_account")
        self.assertEqual((early["status"], early["reason"]), ("blocked", "challenge_not_verified"))

    def test_one_persons_approval_never_changes_another_persons_access(self):
        _, sent = self.verified()
        ow.check_verification(self.svc, sent["challenge_ref"])
        other = ow.change_access(self.svc, sent["challenge_ref"], DANIEL, "unlock_account")
        self.assertEqual((other["status"], other["reason"], other["effects"]), ("blocked", "different_subject", 0))
        self.assertTrue(self.svc.access(DANIEL)["account_locked"])

    def test_a_challenge_for_one_change_does_not_authorize_another(self):
        _, sent = self.verified(action="unlock_account")
        ow.check_verification(self.svc, sent["challenge_ref"])
        wrong = ow.change_access(self.svc, sent["challenge_ref"], TARA, "reset_password")
        self.assertEqual((wrong["status"], wrong["reason"]), ("blocked", "wrong_action_scope"))
        self.assertFalse(self.svc.access(TARA)["password_reset_pending"])

    def test_denied_and_timed_out_challenges_are_dead(self):
        for name, state in (("Owen Mercer", "denied"), ("Rachel Collins", "timed_out")):
            with self.subTest(name=name):
                prepared, sent = self.verified(name=name)
                checked = ow.check_verification(self.svc, sent["challenge_ref"])
                self.assertEqual((checked["status"], checked["challenge_invalidated"]), (state, True))
                self.assertEqual(ow.check_verification(self.svc, sent["challenge_ref"])["status"], state)
                refused = ow.change_access(self.svc, sent["challenge_ref"], prepared["employee_ref"], "unlock_account")
                self.assertEqual(refused["reason"], "challenge_not_verified")
                routed = ow.route_identity_desk(self.svc, "not verified", prepared["employee_ref"], sent["challenge_ref"])
                self.assertEqual((routed["status"], routed["challenge_invalidated"], routed["access_unchanged"]),
                                 ("routed", True, True))
        self.assertEqual(self.svc.changes, [])

    def test_late_approval_waits_then_approves(self):
        _, sent = self.verified(name="Grace Porter")
        self.assertEqual(ow.check_verification(self.svc, sent["challenge_ref"])["status"], "waiting")
        self.assertEqual(ow.check_verification(self.svc, sent["challenge_ref"])["status"], "approved")
        self.assertEqual(ow.change_access(self.svc, sent["challenge_ref"], GRACE, "unlock_account")["status"],
                         "succeeded")

    def test_cancel_stops_the_challenge_and_keeps_access(self):
        _, sent = self.verified(name="Daniel Frost")
        before = self.svc.access(DANIEL)
        cancelled = ow.cancel_verification(self.svc, sent["challenge_ref"])
        self.assertEqual((cancelled["status"], cancelled["access_unchanged"]), ("cancelled", True))
        self.assertEqual(ow.check_verification(self.svc, sent["challenge_ref"])["status"], "cancelled")
        self.assertEqual(ow.change_access(self.svc, sent["challenge_ref"], DANIEL, "unlock_account")["reason"],
                         "challenge_not_verified")
        self.assertEqual(self.svc.access(DANIEL), before)

    def test_routing_invalidates_an_open_challenge(self):
        prepared, sent = self.verified(name="Tara Brennan")
        ow.route_identity_desk(self.svc, "caller asked for the desk", TARA, sent["challenge_ref"])
        self.assertEqual(ow.check_verification(self.svc, sent["challenge_ref"])["status"], "invalidated")

    def test_no_result_carries_a_secret(self):
        """The receipt rule: an authorization reference, never a password, code or answer."""
        _, sent = self.verified(action="reset_password")
        results = [sent, ow.check_verification(self.svc, sent["challenge_ref"])]
        results.append(ow.change_access(self.svc, sent["challenge_ref"], TARA, "reset_password"))
        text = json.dumps(results).lower()
        for word in ("temporary password", "passcode", "one-time code", "otp", "security answer"):
            self.assertNotIn(word, text)
        self.assertNotRegex(text, r"\bcode\"?\s*:\s*\"?\d{4,}")

    def test_each_conversation_has_its_own_directory(self):
        a, b = ow.service_for("conv-a"), ow.service_for("conv-b")
        a.apply(TARA, "unlock_account")
        self.assertTrue(b.access(TARA)["account_locked"])


if __name__ == "__main__":
    unittest.main()
