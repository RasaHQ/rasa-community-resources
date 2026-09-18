"""Product-level regressions: contextual repairs, receipts and observable quality."""
import json
from unittest import TestCase
from test_civico import FakeContext, TempStore, run
from skills.report_problem import tools as report
from scripts.conversation_quality import score


class TestProductExperience(TempStore):
    def draft(self):
        ctx = FakeContext()
        run(report.capture_report(problem="Street light not working", area="Vasundhara",
            landmark="outside Juniper Heights main gate", callback="9000000001", context=ctx))
        run(report.find_similar_open(ctx))
        run(report.prepare_report_summary(ctx))
        return ctx

    def test_other_gate_keeps_named_building_and_locality(self):
        ctx = self.draft()
        run(report.revise_report("exact_spot", "the other gate", ctx))
        self.assertEqual(ctx.memory.get("exact_spot"), "outside Juniper Heights other gate")
        self.assertEqual(ctx.memory.get("ward_label"), "Vasundhara")
        self.assertIn("Juniper Heights other gate", ctx.said[-1])
        self.assertIsNone(ctx.memory.get("complaint_id"))

    def test_complete_new_landmark_replaces_previous_spot(self):
        self.assertEqual(report._refine_spot("Juniper Heights main gate", "Juniper School gate"),
                         "Juniper School gate")

    def test_added_metro_landmark_keeps_building(self):
        ctx = FakeContext()
        run(report.capture_report(area="Vaishali", landmark="near Juniper Heights", context=ctx))
        run(report.capture_report(landmark="near the metro station, Vikas Marg", context=ctx))
        self.assertEqual(ctx.memory.get("exact_spot"),
                         "near Juniper Heights, near the metro station, Vikas Marg")

    def test_explicit_new_spot_does_not_keep_old_building(self):
        ctx = FakeContext()
        run(report.capture_report(area="Vaishali", landmark="Juniper Heights", context=ctx))
        run(report.capture_report(landmark="Juniper School", replace_landmark=True, context=ctx))
        self.assertEqual(ctx.memory.get("exact_spot"), "Juniper School")

    def test_new_locality_with_new_spot_does_not_merge_old_address(self):
        ctx = FakeContext()
        run(report.capture_report(area="Vaishali", landmark="Juniper Heights", context=ctx))
        run(report.capture_report(area="Vasundhara", landmark="Juniper School", replace_area=True, context=ctx))
        self.assertEqual(ctx.memory.get("exact_spot"), "Juniper School")

    def test_no_gate_number_is_invented(self):
        self.assertEqual(report._refine_spot("outside Juniper School", "back gate"),
                         "outside Juniper School, at the back gate")

    def test_pin_does_not_replace_required_landmark(self):
        ctx = FakeContext()
        result = run(report.capture_report(problem="Street light not working",
            area="201012", callback="9000000001", context=ctx)).llm_response
        self.assertIn("landmark", result["missing"])
        self.assertFalse(run(report.prepare_report_summary(ctx)).llm_response["ok"])

    def test_category_change_cannot_reuse_wrong_description(self):
        ctx = self.draft()
        run(report.revise_report("category", "garbage", ctx))
        self.assertIsNone(ctx.memory.get("description"))
        self.assertFalse(ctx.memory.get("details_verified"))
        self.assertEqual(ctx.memory.get("ward_label"), "Vasundhara")

    def test_callback_correction_refreshes_summary_without_reasking_incident(self):
        ctx = self.draft()
        run(report.revise_report("callback_number", "9000000002", ctx))
        self.assertEqual(ctx.memory.get("callback_number"), "9000000002")
        self.assertTrue(ctx.memory.get("details_verified"))
        self.assertEqual(ctx.memory.get("duplicate_decision"), "new")
        self.assertIsNone(ctx.memory.get("complaint_id"))
        self.assertIn("zero zero zero two", ctx.said[-1])

    def test_repeated_summary_tool_does_not_repeat_spoken_summary(self):
        ctx = self.draft()
        run(report.prepare_report_summary(ctx))
        self.assertEqual(len(ctx.said), 1)

    def test_receipt_explains_demo_assignment_and_lookup_not_notifications(self):
        ctx = self.draft()
        run(report.file_complaint(ctx))
        receipt = ctx.said[-1]
        self.assertIn("demo assignment", receipt)
        self.assertIn("Street Lighting", receipt)
        self.assertIn("callback number", receipt)
        self.assertNotIn("hear back", receipt)


class TestScorecard(TestCase):
    def test_metrics_and_no_caller_data_in_output(self):
        events = [
            {"event": "user", "text": "private 9000000000", "timestamp": 0},
            {"event": "bot", "text": "Which building? Which building?", "timestamp": 3},
            {"event": "user", "timestamp": 4},
            {"event": "bot", "text": '{"target_id":"report_problem__main"}', "timestamp": 6},
            {"event": "tool_executed", "tool_name": "file_complaint", "result": '{"status":"awaiting_confirmation"}'},
            {"event": "tool_executed", "tool_name": "prepare_report_summary", "result": '{"ok":true}'},
            {"event": "tool_executed", "tool_name": "revise_report", "result": '{"ok":true}'},
            {"event": "tool_executed", "tool_name": "file_complaint", "result": '{"ok":true,"complaint_id":"CIV1005"}'},
            {"event": "tool_executed", "tool_name": "file_complaint", "result": '{"ok":true,"complaint_id":"CIV1005"}'},
        ]
        result = score({"events": events})
        self.assertEqual(result["duplicate_questions_within_turn"], 1)
        self.assertEqual(result["internal_tool_text_messages"], 1)
        self.assertEqual(result["saved_reports"], 1)
        self.assertEqual(result["reports_saved_after_correction"], 1)
        self.assertEqual(result["median_time_to_first_bot_text_seconds"], 2.5)
        for private in ("9000000000", "CIV1005", "Which building"):
            self.assertNotIn(private, json.dumps(result))

    def test_failed_or_pending_write_is_not_success(self):
        result = score({"events": [{"event": "tool_executed", "tool_name": "file_complaint",
                                   "result": '{"ok":false}'}]})
        self.assertEqual(result["saved_reports"], 0)

    def test_initial_detail_capture_is_not_a_post_review_correction(self):
        result = score({"events": [{"event": "tool_executed", "tool_name": "revise_report",
                                   "result": '{"ok":true}'}]})
        self.assertEqual(result["accepted_post_review_corrections"], 0)

    def test_streaming_previews_do_not_count_as_duplicate_questions(self):
        result = score({"events": [{"event": "user"},
            {"event": "bot", "text": "Where?", "metadata": {"streaming": True}},
            {"event": "bot", "text": "Where?"}]})
        self.assertEqual(result["duplicate_questions_within_turn"], 0)
