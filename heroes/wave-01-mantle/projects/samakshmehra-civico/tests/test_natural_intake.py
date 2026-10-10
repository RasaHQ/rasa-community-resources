"""Regressions inspired by the September 10 location-first voice transcript."""
from test_civico import FakeContext, TempStore, run
from lib import store
from skills.report_problem import tools as report


class TestNaturalIntake(TempStore):
    def test_location_before_problem_is_saved_without_ward_question(self):
        ctx = FakeContext()
        result = run(report.capture_report(area="Vashali Ghaziabad",
            landmark="near Juniper Heights", context=ctx)).llm_response
        self.assertEqual(ctx.memory.get("ward_id"), "W12")
        self.assertEqual(result["missing"], ["problem", "callback"])
        result = run(report.capture_report(problem="The light bulb is not working",
                                          context=ctx)).llm_response
        self.assertEqual(ctx.memory.get("category"), "streetlight")
        self.assertEqual(ctx.memory.get("description"), "The light bulb is not working")
        self.assertEqual(result["missing"], ["callback"])
        self.assertEqual(ctx.said, [])

    def test_complete_sentence_captures_all_details_in_one_call(self):
        ctx = FakeContext()
        result = run(report.capture_report(problem="Garbage bags left for three days",
            area="Indirapuram", landmark="outside the school gate",
            callback="9000000000", context=ctx)).llm_response
        self.assertEqual(result["missing"], [])
        self.assertIsNone(ctx.memory.get("details_verified"))
        self.assertFalse(run(report.file_complaint(ctx)).llm_response["ok"])

    def test_new_road_detail_does_not_replace_problem(self):
        ctx = FakeContext()
        run(report.capture_report(problem="Streetlight not working", area="Vaishali",
            landmark="near Juniper Heights", context=ctx))
        run(report.capture_report(landmark="near Juniper Heights, metro station, Vikas Marg",
                                  context=ctx))
        self.assertEqual(ctx.memory.get("description"), "Streetlight not working")
        self.assertIn("Vikas Marg", ctx.memory.get("exact_spot"))

    def test_ambiguous_pin_does_not_silently_choose_a_locality(self):
        ctx = FakeContext()
        run(report.capture_report(area="201002", context=ctx))
        self.assertFalse(ctx.memory.get("ward_confirmed"))

    def test_short_callback_is_rejected_without_losing_location(self):
        ctx = FakeContext()
        result = run(report.capture_report(area="Vaishali", landmark="metro station",
            callback="900000000", context=ctx)).llm_response
        self.assertFalse(result["ok"])
        self.assertIsNone(ctx.memory.get("callback_number"))
        self.assertEqual(ctx.memory.get("exact_spot"), "metro station")

    def test_summary_is_readiness_not_a_database_write(self):
        ctx = FakeContext()
        run(report.capture_report(problem="Street light not working", area="Vaishali",
            landmark="Juniper Heights", callback="9000000000", context=ctx))
        run(report.find_similar_open(ctx))
        result = run(report.prepare_report_summary(ctx)).llm_response
        self.assertTrue(result["ok"])
        self.assertEqual(len(ctx.said), 1)
        self.assertIn("Juniper Heights", ctx.said[0])
        self.assertNotIn("?", ctx.said[0])
        self.assertIsNone(ctx.memory.get("complaint_id"))
        with store.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0], 4)
        run(report.capture_report(landmark="metro station, Vikas Marg", context=ctx))
        self.assertTrue(ctx.memory.get("details_verified"))  # refreshed read-back, not consent
        self.assertEqual(ctx.memory.get("duplicate_decision"), "new")
        self.assertIn("metro station, Vikas Marg", ctx.said[-1])
        self.assertEqual(len(ctx.said), 2)  # original and corrected summary, not extra questions
        self.assertIsNone(ctx.memory.get("complaint_id"))

    def test_incomplete_summary_does_not_mark_readiness_or_speak(self):
        ctx = FakeContext()
        self.assertFalse(run(report.prepare_report_summary(ctx)).llm_response["ok"])
        self.assertIsNone(ctx.memory.get("details_verified"))
        self.assertEqual(ctx.said, [])

    def test_resending_same_facts_does_not_invalidate_review(self):
        ctx = FakeContext()
        args = dict(problem="Street light not working", area="Vaishali",
                    landmark="Juniper Heights", callback="9000000000", context=ctx)
        run(report.capture_report(**args))
        run(report.find_similar_open(ctx))
        run(report.prepare_report_summary(ctx))
        run(report.capture_report(**args))
        self.assertTrue(ctx.memory.get("details_verified"))

    def test_redundant_ward_selection_does_not_restart_intake(self):
        ctx = FakeContext()
        run(report.capture_report(area="Vasundhara", context=ctx))
        result = run(report.confirm_ward("Vasundhara, ward 13", ctx)).llm_response
        self.assertTrue(result["ok"])
        self.assertTrue(result["already_selected"])

    def test_ambiguous_choice_accepts_locality_name(self):
        ctx = FakeContext()
        run(report.capture_report(area="201002", context=ctx))
        result = run(report.confirm_ward("Kavi Nagar", ctx)).llm_response
        self.assertTrue(result["ok"])
        self.assertEqual(ctx.memory.get("ward_id"), "W01")

    def test_road_misclassified_as_area_preserves_known_locality(self):
        ctx = FakeContext()
        run(report.capture_report(area="Vaishali", landmark="Juniper Heights", context=ctx))
        run(report.capture_report(area="Vikas Marg", landmark="near the metro station", context=ctx))
        self.assertEqual(ctx.memory.get("ward_label"), "Vaishali")
        for detail in ("Juniper Heights", "metro station", "Vikas Marg"):
            self.assertIn(detail, ctx.memory.get("exact_spot"))

    def test_explicit_move_does_not_keep_old_locality(self):
        ctx = FakeContext()
        run(report.capture_report(area="Vaishali", landmark="Juniper Heights", context=ctx))
        run(report.capture_report(area="Unknown Road", replace_area=True, context=ctx))
        self.assertFalse(ctx.memory.get("ward_confirmed"))

    def test_my_society_is_not_an_identifiable_landmark(self):
        ctx = FakeContext()
        result = run(report.capture_report(landmark="nearby my society", context=ctx)).llm_response
        self.assertIsNone(ctx.memory.get("exact_spot"))
        self.assertIn("society or building called", result["hint"])
