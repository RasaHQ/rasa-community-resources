"""Saved-record characterisation and missing-evidence controls; no voice calls."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "confirmation_audio_audit", PROJECT / "case-build/audit_confirmation_audio.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConfirmationAudioAuditTests(unittest.TestCase):
    def setUp(self):
        saved = json.loads((PROJECT / "case-build/results/2026-09-29-custom-vocab/results.json").read_text())
        self.report = {"conversations": [copy.deepcopy(next(
            item for item in saved["conversations"]
            if item["id"] == "normal-date-said-numerically"
        ))]}

    def finding(self):
        return MODULE.audit(self.report)["confirmations"][0]["finding"]

    def test_two_saved_successes_have_corroborated_missing_confirmation_audio(self):
        saved = json.loads((PROJECT / "case-build/results/2026-09-29-custom-vocab/results.json").read_text())
        rows = MODULE.audit(saved)["confirmations"]
        missing = [row for row in rows if row["finding"] == "missing_audio_corroborated"]
        self.assertEqual(
            [(row["case"], row["confirmation_turn"]) for row in missing],
            [("normal-date-said-numerically", 1), ("recovery-ambiguous-then-amount", 2)],
        )
        self.assertTrue(all(row["original_checks_passed"] for row in missing))
        self.assertTrue(MODULE.audit(saved)["review_required"])

    def test_absent_server_event_is_unverified_not_corroborated(self):
        self.report["conversations"][0]["log_event_details"] = {}
        self.assertEqual(self.finding(), "delivery_unverified")

    def test_another_conversations_event_is_not_evidence_for_this_question(self):
        self.report["conversations"][0]["log_event_details"]["voice_channel.audio_missing"][0]["conversation_id"] = "another-call"
        self.assertEqual(self.finding(), "delivery_unverified")

    def test_another_utterances_event_is_not_evidence_for_this_question(self):
        self.report["conversations"][0]["log_event_details"]["voice_channel.audio_missing"][0]["text"] = "Another reply"
        self.assertEqual(self.finding(), "delivery_unverified")

    def test_missing_client_fields_are_not_assumed_to_be_zero_audio(self):
        self.report["conversations"][0]["turns"][0]["extra"] = {}
        self.assertEqual(self.finding(), "conflicting_or_incomplete_evidence")

    def test_repeated_question_cannot_be_bound_to_one_turn_by_text_alone(self):
        conversation = self.report["conversations"][0]
        conversation["turns"].append(copy.deepcopy(conversation["turns"][0]))
        self.assertEqual(self.finding(), "conflicting_or_incomplete_evidence")

    def test_interrupted_turn_is_not_a_no_barge_in_failure(self):
        self.report["conversations"][0]["turns"][0]["extra"]["interrupts"] = 1
        self.assertEqual(self.finding(), "conflicting_or_incomplete_evidence")

    def test_missing_conversation_identity_cannot_bind_an_event(self):
        conversation = self.report["conversations"][0]
        conversation.pop("conversation_id")
        conversation["log_event_details"]["voice_channel.audio_missing"][0].pop("conversation_id")
        self.assertEqual(self.finding(), "delivery_unverified")

    def test_positive_audio_with_missing_audio_event_requires_review(self):
        observation = self.report["conversations"][0]["turns"][0]["extra"]
        observation.update(bot_audio_s=2, eos_to_first_audio_ms=100)
        self.assertEqual(self.finding(), "conflicting_or_incomplete_evidence")

    def test_positive_turn_audio_is_reported_as_presence_not_hearing(self):
        conversation = self.report["conversations"][0]
        conversation["log_event_details"] = {}
        conversation["turns"][0]["extra"].update(bot_audio_s=2, eos_to_first_audio_ms=100)
        self.assertEqual(self.finding(), "audio_recorded_in_turn")

    def test_no_recognised_question_cannot_clear_review(self):
        self.assertTrue(MODULE.audit({"conversations": []})["review_required"])


if __name__ == "__main__":
    unittest.main()
