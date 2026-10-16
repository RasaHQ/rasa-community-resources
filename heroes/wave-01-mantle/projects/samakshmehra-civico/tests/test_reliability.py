"""Regressions for cold starts, lookup corrections and deterministic routing."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
from threading import Event
from unittest import TestCase
from unittest.mock import patch

from test_civico import FakeContext, FakeMemory, TempStore, run
from lib import directory, store
from lib.choices import pick
from skills.check_status import tools as status
from skills.report_problem import tools as report
from skills.who_handles_this import tools as routing
from tools import civic


class TestSpokenSelection(TempStore):
    def test_fourth_option_is_not_mistaken_for_first(self):
        store.insert_complaint(phone="0000000501", category="garbage", ward_id="W12",
            locality="Maplewick", exact_spot="School gate", description="Uncollected bins",
            department="Sanitation", sla_days=2)
        context = FakeContext()
        listed = run(status.list_my_complaints("0000000501", context)).llm_response
        self.assertEqual(len(listed["options"]), 4)
        for choice in ("the fourth one", "four", "4th", "number 4", "4."):
            with self.subTest(choice=choice):
                chosen = run(status.choose_complaint(choice, context)).llm_response
                self.assertEqual(chosen.get("complaint_id"),
                                 listed["options"][3]["complaint_id"])

    def test_out_of_range_and_malformed_choices_are_rejected(self):
        for choice in ("the fourth one", "four", "4th", "4", "--2", "-1", "number -1",
                       "minus one", "negative 1", "0",
                       "the fifth one", "second or third", "no not the first one"):
            with self.subTest(choice=choice):
                self.assertEqual(pick(choice, 3), -1)

    def test_unambiguous_first_and_single_option_agreement_still_work(self):
        for choice in ("one", "option one", "the first one", "1", "1st"):
            with self.subTest(choice=choice):
                self.assertEqual(pick(choice, 4), 0)
        self.assertEqual(pick("Yes that is the one", 1), 0)
        self.assertEqual(pick("yes", 4), -1)


class TestLookupCorrections(TempStore):
    def selected(self):
        context = FakeContext(raise_answer="yes", escalated=True)
        run(civic.look_up_complaint("CIV1002", context))
        return context

    def assert_no_selection(self, context):
        for name in ("complaint_id", "is_overdue", "escalation_level", "escalated",
                     "raise_answer"):
            self.assertIsNone(context.memory.get(name), name)

    def test_failed_reference_clears_previous_selection_and_escalation(self):
        context = self.selected()
        failed = run(civic.look_up_complaint("CIV9999", context)).llm_response
        self.assertFalse(failed["ok"])
        self.assert_no_selection(context)
        self.assertEqual(run(civic.escalate_complaint("", context)).llm_response["error"],
                         "no_complaint")

    def test_invalid_phone_clears_previous_options(self):
        context = FakeContext()
        run(status.list_my_complaints("0000000501", context))
        run(status.choose_complaint("second", context))
        self.assertFalse(run(status.list_my_complaints("123", context)).llm_response["ok"])
        self.assert_no_selection(context)
        self.assertFalse(run(status.choose_complaint("second", context)).llm_response["ok"])

    def test_empty_phone_result_clears_previous_selection(self):
        context = self.selected()
        result = run(status.list_my_complaints("0000000999", context)).llm_response
        self.assertEqual(result["found"], 0)
        self.assert_no_selection(context)

    def test_new_option_list_requires_a_new_selection(self):
        context = self.selected()
        listed = run(status.list_my_complaints("0000000501", context)).llm_response
        self.assertGreater(listed["found"], 1)
        self.assert_no_selection(context)
        result = run(status.choose_complaint("second", context)).llm_response
        self.assertEqual(result["complaint_id"], listed["options"][1]["complaint_id"])

    def test_invalid_choice_clears_selection_but_allows_retry(self):
        context = FakeContext()
        run(status.list_my_complaints("0000000501", context))
        run(status.choose_complaint("first", context))
        self.assertFalse(run(status.choose_complaint("9", context)).llm_response["ok"])
        self.assert_no_selection(context)
        self.assertTrue(run(status.choose_complaint("second", context)).llm_response["ok"])

    def test_reference_lookup_invalidates_an_older_phone_list(self):
        context = FakeContext()
        run(status.list_my_complaints("0000000501", context))
        run(civic.look_up_complaint("CIV9999", context))
        self.assertFalse(run(status.choose_complaint("first", context)).llm_response["ok"])

    def test_shared_lookup_writes_only_declared_escalation_fields(self):
        allowed = {"complaint_id", "is_overdue", "escalation_level", "escalated"}

        class ScopedMemory(FakeMemory):
            def set(self, name, value):
                if name not in allowed:
                    raise AssertionError(f"Undeclared escalation field: {name}")
                super().set(name, value)

        context = FakeContext()
        context.memory = ScopedMemory()
        self.assertTrue(run(civic.look_up_complaint("CIV1002", context)).llm_response["ok"])
        run(civic.look_up_complaint("CIV9999", context))
        self.assertIsNone(context.memory.get("complaint_id"))


class TestFallbackLocation(TempStore):
    def test_second_unknown_area_keeps_the_supplied_landmark(self):
        context = FakeContext()
        run(report.capture_report(problem="Garbage bags", area="outside our lane",
            landmark="Ferry terminal gate", callback="0000000009", context=context))
        run(report.capture_report(area="I don't know", context=context))
        self.assertEqual(context.memory.get("ward_id"), directory.general_cell()["ward_id"])
        self.assertEqual(context.memory.get("exact_spot"), "Ferry terminal gate")
        run(report.find_similar_open(context))
        self.assertTrue(run(report.prepare_report_summary(context)).llm_response["ok"])
        self.assertIn("Ferry terminal gate", context.said[-1])

    def test_explicit_move_still_discards_the_previous_landmark(self):
        context = FakeContext()
        run(report.capture_report(area="Maplewick", landmark="Juniper Heights", context=context))
        run(report.capture_report(area="outside our lane", replace_area=True, context=context))
        self.assertIsNone(context.memory.get("exact_spot"))

    def test_resolving_an_unknown_area_keeps_the_incident_landmark(self):
        context = FakeContext()
        run(report.capture_report(area="outside our lane", landmark="Juniper School", context=context))
        run(report.capture_report(area="Brookmere", context=context))
        self.assertEqual(context.memory.get("ward_label"), "Brookmere")
        self.assertEqual(context.memory.get("exact_spot"), "Juniper School")


class TestRoutingClarification(TempStore):
    def test_ambiguous_pin_asks_instead_of_guessing_the_officer(self):
        context = FakeContext()
        answer = run(routing.who_handles("garbage", "000107", context)).llm_response
        self.assertTrue(answer.get("needs_clarification"))
        self.assertGreater(len(answer["options"]), 1)
        self.assertNotIn("officer", answer)
        self.assertFalse(context.memory.get("answered"))
        self.assertIn("?", context.said[-1])
        self.assertNotIn("Demo Officer", context.said[-1])

    def test_named_locality_resolves_the_pin_ambiguity(self):
        context = FakeContext()
        run(routing.who_handles("garbage", "000107", context))
        answer = run(routing.who_handles("garbage", "Lantern Hollow", context)).llm_response
        self.assertEqual(answer["officer"], "Demo Officer 01")
        self.assertTrue(context.memory.get("answered"))


class TestStoreInitialization(TempStore):
    def test_cold_start_serializes_seeding_and_a_new_report(self):
        entered, release, writer_started = Event(), Event(), Event()
        original_seed = store._seed

        def delayed_seed(connection):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("Seed coordination timed out")
            original_seed(connection)

        def file_report():
            writer_started.set()
            return store.insert_complaint(phone="0000000009", category="garbage",
                ward_id="W12", locality="Maplewick", exact_spot="School gate",
                description="New report", department="Sanitation", sla_days=2)

        with ThreadPoolExecutor(max_workers=2) as pool:
            with patch.object(store, "_seed", delayed_seed):
                first = pool.submit(store.citizen_by_phone, "0000000501")
                try:
                    self.assertTrue(entered.wait(5))
                    writer = pool.submit(file_report)
                    self.assertTrue(writer_started.wait(5))
                    with self.assertRaises(FutureTimeout):
                        writer.result(timeout=0.2)
                finally:
                    release.set()
                first.result(timeout=5)
                created = writer.result(timeout=5)
        self.assertEqual(store.get_complaint(created["complaint_id"])["description"], "New report")
        self.assertEqual(created["complaint_id"], "CIV1005")

    def test_an_empty_preexisting_file_is_seeded(self):
        self._db.touch()
        self.assertIsNotNone(store.get_complaint("CIV1001"))

    def test_a_seed_failure_rolls_back_and_next_connection_retries(self):
        with patch.object(store, "_seed", side_effect=RuntimeError("Interrupted setup")):
            with self.assertRaises(RuntimeError):
                store.connect()
        self.assertIsNotNone(store.get_complaint("CIV1001"))

    def test_migrating_the_existing_store_does_not_restore_old_seed_values(self):
        store.get_complaint("CIV1001")
        with store.connect() as connection:
            connection.execute("UPDATE complaints SET description='Preserved report' "
                               "WHERE complaint_id='CIV1001'")
            connection.execute("PRAGMA user_version=0")
        with patch.object(store, "_seed", side_effect=AssertionError("Must not reseed")):
            self.assertEqual(store.get_complaint("CIV1001")["description"], "Preserved report")


class TestRoutingFlow(TestCase):
    def test_reporting_handoff_ends_without_the_no_report_message(self):
        from rasa.mantle.skills.catalog import load_skill_catalog
        catalog = load_skill_catalog(Path(__file__).resolve().parents[1])
        flow = catalog.flow_by_id("who_handles_this__main")
        call = next(step for step in flow.steps if step.id == "take_the_complaint")
        self.assertEqual(call.next, "END")
        declined = next(step for step in flow.steps if step.id == "sign_off")
        self.assertEqual(declined.action, "utter_nothing_filed")
