import unittest
from claim_crew.handoff import ClaimSession
from claim_crew.native_fixture import create_fixture


class HandoffControls(unittest.TestCase):
    def test_missing_selection_does_not_create_crew(self):
        def forbidden(_):
            raise AssertionError("Not selected")

        self.assertEqual(
            ClaimSession(forbidden).checklist("What documents?")["status"],
            "needs_claim_type",
        )

    def test_unknown_selection_stays_unbound(self):
        session = ClaimSession(create_fixture)
        self.assertEqual(session.select("mortgage")["status"], "unknown_claim_type")
        self.assertIsNone(session.claim_type)

    def test_invalid_question_does_not_create_crew(self):
        def forbidden(_):
            raise AssertionError("Invalid question")

        session = ClaimSession(forbidden)
        session.select("vehicle")
        self.assertEqual(session.checklist("")["status"], "invalid_question")

    def test_actual_crew_reaches_checked_checklist(self):
        session = ClaimSession(create_fixture)
        session.select("vehicle")
        result = session.checklist("What documents?")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["source"]["source_id"], "HC-V-101")

    def test_two_sessions_do_not_share_selected_claim_type(self):
        one = ClaimSession(create_fixture)
        two = ClaimSession(create_fixture)
        one.select("vehicle")
        two.select("travel")
        self.assertEqual(
            one.checklist("What documents?")["source"]["source_id"], "HC-V-101"
        )
        self.assertEqual(
            two.checklist("What documents?")["source"]["source_id"], "HC-T-201"
        )

    def test_selection_change_is_refused(self):
        session = ClaimSession(create_fixture)
        session.select("vehicle")
        self.assertEqual(session.select("travel")["status"], "claim_type_changed")
        self.assertEqual(session.claim_type, "vehicle")

    def test_finished_failed_crew_is_incomplete(self):
        session = ClaimSession(lambda kind: create_fixture(kind, unavailable=True))
        session.select("vehicle")
        self.assertEqual(session.checklist("What documents?")["status"], "incomplete")
