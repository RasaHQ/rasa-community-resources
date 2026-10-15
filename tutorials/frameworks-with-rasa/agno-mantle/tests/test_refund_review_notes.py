"""Check draft notes against independent order records, without model calls."""
import unittest
from dataclasses import replace

from shop_adviser.refund_policy import ReturnRecord
from review_return_policy import review_sheet, validate_review_note


class ReviewNotes(unittest.TestCase):
    def setUp(self):
        self.order = ReturnRecord("WS-REVIEW-LATE", "customer-a", 1299, 31,
                                  "sealed", "inspection-01")
        self.note = {"inspection_recorded": True, "next_step": "review_exception",
                     "receiving_role": "returns-reviewer", "delivery": "draft_not_sent"}

    def test_reference_without_condition_still_requires_inspection(self):
        record = replace(self.order, condition=None)
        note = {**self.note, "inspection_recorded": False, "next_step": "obtain_inspection"}
        self.assertEqual(validate_review_note(note, record), note)
        with self.assertRaisesRegex(ValueError, "source record"):
            validate_review_note(self.note, record)

    def test_changing_both_note_fields_cannot_invent_an_inspection(self):
        record = replace(self.order, condition=None, inspection_ref=None)
        with self.assertRaisesRegex(ValueError, "source record"):
            validate_review_note(self.note, record)

    def test_required_inspection_cannot_be_skipped(self):
        record = replace(self.order, inspection_ref=None)
        with self.assertRaisesRegex(ValueError, "next step"):
            validate_review_note({**self.note, "inspection_recorded": False}, record)

    def test_worksheet_retains_seven_cases_and_rejects_all_three_mutations(self):
        sheet = review_sheet()
        self.assertEqual(len(sheet["cases"]), 7)
        self.assertEqual([n["next_step"] for n in sheet["proposed_review_notes"]],
                         ["review_exception", "obtain_inspection"])
        for key in ("incomplete_note_control", "wrong_next_step_control", "false_inspection_control"):
            self.assertEqual(sheet[key]["result"], "rejected")


if __name__ == "__main__":
    unittest.main()
