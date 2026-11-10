"""Service-binding exercise controls; no native dispatcher or model calls."""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exercises.changed_offer import replay  # noqa: E402


class ChangedOfferExercise(unittest.TestCase):
    def test_refreshing_values_does_not_refresh_the_displayed_question(self):
        report = replay()
        stale, refreshed, fresh = report["stages"]
        self.assertEqual((stale["status"], stale["reason"]), ("blocked", "unapproved_terms"))
        self.assertEqual((refreshed["status"], refreshed["reason"]), ("blocked", "acceptance_missing"))
        self.assertTrue(refreshed["facts"]["offer_authorized"])
        self.assertTrue(refreshed["facts"]["offer_revision_current"])
        self.assertFalse(refreshed["facts"]["customer_acceptance_recorded"])
        self.assertEqual(refreshed["question"], stale["question"])
        self.assertEqual(refreshed["savedOfferTag"], fresh["savedOfferTag"])
        self.assertEqual(refreshed["savedTerms"], fresh["savedTerms"])
        self.assertNotEqual(refreshed["question"], fresh["question"])

    def test_only_fresh_question_records_the_service_owned_revised_terms(self):
        report = replay()
        stale, refreshed, fresh = report["stages"]
        for row in (stale, refreshed):
            self.assertEqual((row["effects"], row["plansBefore"], row["plansAfter"]), (0, 0, 0))
            self.assertIsNone(row["recordedTerms"])
        self.assertEqual((fresh["status"], fresh["effects"], fresh["plansAfter"]), ("succeeded", 1, 1))
        self.assertTrue(all(fresh["facts"].values()))
        self.assertEqual(report["originalOffer"]["instalment_usd"], "214.00")
        self.assertEqual(report["revisedOffer"]["instalment_usd"], "200.00")
        self.assertEqual(fresh["recordedTerms"]["instalment_usd"], "200.00")
        self.assertEqual(fresh["recordedTerms"]["total_usd"], "600.00")

    def test_replay_starts_from_a_fresh_fixture_each_time(self):
        self.assertEqual(replay(), replay())


if __name__ == "__main__":
    unittest.main()
