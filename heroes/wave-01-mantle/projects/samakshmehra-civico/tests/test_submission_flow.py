"""Regression checks for report correction, joining and later follow-up."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from test_civico import FakeContext, TempStore, run
from lib import store
from skills.report_problem import tools as report
from skills.check_status import tools as status


class TestSubmissionFlow(TempStore):
    def ready(self, **changes):
        values = dict(category="drainage", department="Drainage", sla_days="5",
                      ward_id="W12", ward_label="Vaishali", ward_officer="A. Sharma",
                      ward_confirmed=True, exact_spot="Outside the corner shop",
                      description="Drain water spills onto the footpath",
                      callback_number="9000000000", details_verified=True,
                      duplicate_decision="attach", similar_id="CIV1004")
        values.update(changes)
        return FakeContext(**values)

    def test_join_is_idempotent_preserves_details_and_can_be_tracked(self):
        original = store.get_complaint("CIV1004")
        ctx = self.ready()
        for _ in range(2):
            self.assertTrue(run(report.attach_to_existing(ctx)).llm_response["ok"])
        with store.connect() as conn:
            rows = conn.execute("SELECT * FROM supporting_reports").fetchall()
            count = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["description"], ctx.memory.get("description"))
        self.assertEqual(count, 4)
        current = store.get_complaint("CIV1004")
        self.assertEqual(current["resolution_note"], original["resolution_note"])
        self.assertEqual(current["target_on"], original["target_on"])
        tracked = run(status.list_my_complaints("9000000000", FakeContext())).llm_response
        self.assertEqual(tracked["complaint_id"], "CIV1004")

    def test_join_cannot_skip_confirmation_or_required_details(self):
        for field in ("details_verified", "callback_number", "exact_spot", "description"):
            ctx = self.ready(**{field: None})
            self.assertFalse(run(report.attach_to_existing(ctx)).llm_response["ok"])
        with store.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM supporting_reports").fetchone()[0], 0)

    def test_closed_or_changed_duplicate_is_not_joined(self):
        with store.connect() as conn:
            conn.execute("UPDATE complaints SET status='resolved' WHERE complaint_id='CIV1004'")
        self.assertFalse(run(report.attach_to_existing(self.ready())).llm_response["ok"])

    def test_category_correction_requires_new_duplicate_check_and_review(self):
        ctx = self.ready()
        run(report.revise_report("category", "garbage", ctx))
        self.assertEqual(ctx.memory.get("department"), "Sanitation")
        self.assertFalse(ctx.memory.get("details_verified"))
        self.assertIsNone(ctx.memory.get("similar_id"))
        self.assertIsNone(ctx.memory.get("duplicate_decision"))
        self.assertFalse(run(report.file_complaint(ctx)).llm_response["ok"])

    def test_area_correction_clears_old_ward_and_exact_spot(self):
        ctx = self.ready()
        run(report.revise_report("area", "Indirapuram", ctx))
        self.assertFalse(ctx.memory.get("ward_confirmed"))
        self.assertIsNone(ctx.memory.get("ward_id"))
        self.assertIsNone(ctx.memory.get("exact_spot"))
        run(report.confirm_ward("yes", ctx))
        self.assertEqual(ctx.memory.get("ward_id"), "W14")
        self.assertFalse(ctx.memory.get("details_verified"))

    def test_detail_corrections_cannot_set_summary_approval(self):
        ctx = self.ready()
        result = run(report.revise_report("exact_spot", "Park gate", ctx)).llm_response
        self.assertTrue(result["ok"])
        self.assertEqual(ctx.memory.get("exact_spot"), "Park gate")
        self.assertIsNone(ctx.memory.get("details_verified"))
        result = run(report.revise_report("details_verified", "True", ctx)).llm_response
        self.assertFalse(result["ok"])

    def test_negative_confirmation_does_not_select_first_option(self):
        self.assertEqual(report._pick("no not the first one", 2), -1)
        self.assertEqual(report._pick("that is not right", 1), -1)

    def test_general_queue_is_not_treated_as_one_neighbourhood(self):
        ctx = self.ready(ward_id="GEN")
        with patch.object(store, "open_similar") as lookup:
            result = run(report.find_similar_open(ctx)).llm_response
        self.assertEqual(result["found"], 0)
        lookup.assert_not_called()

    def test_filing_rechecks_confirmation_route_and_duplicate_reentry(self):
        ctx = self.ready(duplicate_decision="new", department="Invented", sla_days="999")
        first = run(report.file_complaint(ctx)).llm_response
        second = run(report.file_complaint(ctx)).llm_response
        self.assertEqual(first["complaint_id"], second["complaint_id"])
        row = store.get_complaint(first["complaint_id"])
        self.assertEqual(row["department"], "Drainage")
        self.assertEqual(row["sla_days"], 5)

    def test_selection_uses_the_number_searched_and_only_offered_items(self):
        ctx = FakeContext(caller_phone="9812345678")
        result = run(status.list_my_complaints("9876543210", ctx)).llm_response
        chosen = run(status.choose_complaint("second", ctx)).llm_response
        self.assertEqual(chosen["complaint_id"], result["options"][1]["complaint_id"])
        self.assertFalse(run(status.choose_complaint("4", ctx)).llm_response["ok"])

    def test_concurrent_filings_have_unique_references(self):
        store.get_complaint("CIV1001")  # Seed before concurrent requests.
        def file_one(index):
            return store.insert_complaint(phone=str(index), category="garbage",
                ward_id="W12", locality="Vaishali", exact_spot="Gate", description="Bins",
                department="Sanitation", sla_days=2)["complaint_id"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            refs = list(pool.map(file_one, range(8)))
        self.assertEqual(len(set(refs)), 8)
