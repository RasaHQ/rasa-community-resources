"""Offline tests for the Civico tools.

Every one of these runs with no network and no LLM. That is not a happy
accident — it is the whole point of replacing the geocoder with a directory we
ship. The previous version of this project could not test its own location
logic without hitting OpenStreetMap, so the suite was slow, flaky, and quietly
skipped the cases that mattered most.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import directory, store  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class FakeMemory:
    """Stands in for the engine's per-skill memory."""

    def __init__(self, **initial):
        self.values = dict(initial)

    def set(self, name, value):
        self.values[name] = value

    def get(self, name, default=None):
        return self.values.get(name, default)


class FakeContext:
    def __init__(self, **initial):
        self.memory = FakeMemory(**initial)
        #: What the tool spoke to the caller mid-call via ``context.send``.
        self.said: list[str] = []

    async def send(self, text: str) -> None:
        self.said.append(text)


class TempStore(unittest.TestCase):
    """Base class giving each test its own freshly seeded database."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self._db = Path(self._dir.name) / "civico.db"
        self._original = store.db_path
        store.db_path = lambda: self._db
        self.addCleanup(self._restore)

    def _restore(self):
        store.db_path = self._original
        self._dir.cleanup()


# ---------------------------------------------------------------------------
# The ward directory — what replaced the geocoder
# ---------------------------------------------------------------------------

class TestProjectRoot(unittest.TestCase):
    """The failure mode that cost an evening: tools run from the extracted
    model archive, which contains the code and none of the data."""

    def test_root_is_found_from_a_subdirectory(self):
        from lib import paths
        original = os.getcwd()
        os.chdir(Path(__file__).resolve().parent)
        self.addCleanup(os.chdir, original)
        self.assertTrue((paths.project_root() / "data" / "wards.json").is_file())

    def test_root_is_found_from_an_unrelated_directory(self):
        """Standing in for the temp directory the model archive unpacks into."""
        from lib import paths
        original = os.getcwd()
        with tempfile.TemporaryDirectory() as elsewhere:
            os.chdir(elsewhere)
            self.addCleanup(os.chdir, original)
            self.assertTrue((paths.project_root() / "data" / "wards.json").is_file())

    def test_explicit_override_wins(self):
        from lib import paths
        os.environ["CIVICO_PROJECT_ROOT"] = "/somewhere/else"
        self.addCleanup(os.environ.pop, "CIVICO_PROJECT_ROOT", None)
        self.assertEqual(paths.project_root(), Path("/somewhere/else"))


class TestSpokenDigits(unittest.TestCase):

    def test_pincode_spoken_as_words(self):
        self.assertEqual(directory.extract_pincode("two zero one zero one zero"), "201010")

    def test_pincode_written_as_digits(self):
        self.assertEqual(directory.extract_pincode("my pin code is 201014"), "201014")

    def test_pincode_with_oh_for_zero(self):
        self.assertEqual(directory.extract_pincode("two oh one oh one four"), "201014")

    def test_five_digits_is_not_a_pincode(self):
        """Guessing which sixth digit was meant is how you route the wrong ward."""
        self.assertEqual(directory.extract_pincode("two zero one zero one"), "")

    def test_phone_from_spoken_digits(self):
        spoken = "nine eight seven six five four three two one zero"
        self.assertEqual(directory.extract_phone(spoken), "9876543210")

    def test_phone_strips_country_code(self):
        self.assertEqual(directory.extract_phone("+91 9812345678"), "9812345678")

    def test_phone_strips_leading_zero(self):
        self.assertEqual(directory.extract_phone("09812345678"), "9812345678")

    def test_nine_digits_is_rejected(self):
        self.assertEqual(directory.extract_phone("987654321"), "")

    def test_double_expands(self):
        self.assertEqual(directory.digits_from_speech("double nine eight"), ["998"])


class TestSpokenReferences(unittest.TestCase):
    """The agent reads a reference out character by character, so that is how
    it comes back. Converting it is a fixed transformation, so it is code."""

    def test_spoken_back_character_by_character(self):
        from lib.speech import hear_reference
        self.assertEqual(hear_reference("C I V one zero zero two"), "CIV1002")

    def test_already_a_reference(self):
        from lib.speech import hear_reference
        self.assertEqual(hear_reference("CIV1002"), "CIV1002")

    def test_commas_and_case(self):
        from lib.speech import hear_reference
        self.assertEqual(hear_reference("civ, 1002"), "CIV1002")

    def test_letters_heard_as_the_words_they_sound_like(self):
        from lib.speech import hear_reference
        self.assertEqual(hear_reference("see eye vee one zero zero two"), "CIV1002")

    def test_round_trip(self):
        from lib.speech import hear_reference, say_reference
        self.assertEqual(hear_reference(say_reference("CIV1047")), "CIV1047")

    def test_dates_are_spoken_not_read_as_digits(self):
        from lib.speech import say_date
        self.assertEqual(say_date("2026-09-12"), "the twelfth of September")

    def test_compound_ordinal_is_tts_friendly(self):
        from lib.speech import say_date
        self.assertEqual(say_date("2026-09-23"), "the twenty third of September")

    def test_unparseable_date_passes_through(self):
        from lib.speech import say_date
        self.assertEqual(say_date("soon"), "soon")


class TestWardLookup(unittest.TestCase):

    def test_exact_locality(self):
        matches = directory.find_ward("Indirapuram")["matches"]
        self.assertEqual(matches[0]["label"], "Indirapuram")
        self.assertEqual(matches[0]["ward_id"], "W14")

    def test_mangled_by_speech_recognition(self):
        """The transcript that broke version one, three times, on a live call."""
        result = directory.find_ward("Vishali, two zero one zero one two")
        self.assertEqual(result["matches"][0]["label"], "Vaishali")
        self.assertEqual(result["matches"][0]["officer_name"], "A. Sharma")

    def test_pincode_disagreement_is_surfaced_not_resolved(self):
        """201012 is Vasundhara, but they said Vaishali. Say so; do not pick."""
        result = directory.find_ward("Vishali, two zero one zero one two")
        self.assertTrue(result["matches"][0]["pincode_differs"])

    def test_locality_name_beats_pincode(self):
        result = directory.find_ward("Vishali, two zero one zero one two")
        self.assertEqual(result["matched_on"], "name")

    def test_filler_words_are_ignored(self):
        matches = directory.find_ward("there is a pothole near the market in Kavi Nagar")["matches"]
        self.assertEqual(matches[0]["label"], "Kavi Nagar")

    def test_alias(self):
        self.assertEqual(directory.find_ward("rdc")["matches"][0]["label"], "Raj Nagar")

    def test_confident_match_does_not_drag_near_misses_along(self):
        """Indirapuram also scores 0.76 against Govindpuram. Offer one, not two."""
        matches = directory.find_ward("indirapuram")["matches"]
        self.assertEqual(len(matches), 1)

    def test_pincode_alone_returns_the_ward_once(self):
        """One PIN covers three localities in W09 — offer the ward, not three rows."""
        result = directory.find_ward("201005")
        self.assertEqual(result["matched_on"], "pincode")
        self.assertEqual(len(result["matches"]), 1)
        self.assertIn("/", result["matches"][0]["label"])

    def test_unmappable_description_finds_nothing(self):
        self.assertEqual(directory.find_ward("outside our lane")["matches"], [])

    def test_another_city_is_not_matched(self):
        """The Vijayawada bug: structurally impossible against a fixed table."""
        self.assertEqual(directory.find_ward("Vijayawada")["matches"], [])

    def test_general_cell_is_reachable_by_id(self):
        self.assertIsNotNone(directory.ward_by_id("GEN"))


# ---------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------

class TestStore(TempStore):

    def test_seeded_complaint_is_on_time(self):
        self.assertFalse(store.get_complaint("CIV1001")["is_overdue"])

    def test_seeded_complaint_is_overdue(self):
        row = store.get_complaint("CIV1002")
        self.assertTrue(row["is_overdue"])
        self.assertGreater(row["days_overdue"], 0)

    def test_resolved_complaint_is_never_overdue(self):
        """It missed its date, but a closed complaint is not a live grievance."""
        row = store.get_complaint("CIV1003")
        self.assertLess(row["days_left"], 0)
        self.assertFalse(row["is_overdue"])

    def test_lookup_is_case_and_space_insensitive(self):
        self.assertIsNotNone(store.get_complaint("civ 1001"))

    def test_unknown_reference(self):
        self.assertIsNone(store.get_complaint("CIV9999"))

    def test_complaints_for_phone(self):
        rows = store.complaints_for_phone("9876543210")
        self.assertEqual({r["complaint_id"] for r in rows},
                         {"CIV1001", "CIV1002", "CIV1003"})

    def test_open_only_filter(self):
        rows = store.complaints_for_phone("9876543210", open_only=True)
        self.assertNotIn("CIV1003", {r["complaint_id"] for r in rows})

    def test_similar_matches_category_and_ward(self):
        self.assertEqual([c["complaint_id"] for c in store.open_similar("drainage", "W12")],
                         ["CIV1004"])

    def test_similar_ignores_other_wards(self):
        self.assertEqual(store.open_similar("drainage", "W14"), [])

    def test_similar_ignores_closed(self):
        self.assertEqual(store.open_similar("pothole", "W01"), [])

    def test_insert_sets_target_from_sla(self):
        row = store.insert_complaint(
            phone="9999999999", category="pothole", ward_id="W12",
            locality="Vaishali", exact_spot="by the temple",
            description="Big hole", department="Road Maintenance", sla_days=7,
        )
        self.assertEqual(row["complaint_id"], "CIV1005")
        self.assertEqual(date.fromisoformat(row["target_on"]),
                         date.today() + timedelta(days=7))

    def test_ids_do_not_collide(self):
        first = store.insert_complaint(
            phone="1", category="garbage", ward_id="W12", locality="Vaishali",
            exact_spot="", description="", department="Sanitation", sla_days=2)
        second = store.insert_complaint(
            phone="2", category="garbage", ward_id="W12", locality="Vaishali",
            exact_spot="", description="", department="Sanitation", sla_days=2)
        self.assertNotEqual(first["complaint_id"], second["complaint_id"])

    def test_exact_spot_is_stored_verbatim(self):
        spot = "in front of the Juniper Heights main gate, near the water tank"
        row = store.insert_complaint(
            phone="1", category="pothole", ward_id="W12", locality="Vaishali",
            exact_spot=spot, description="x",
            department="Road Maintenance", sla_days=7)
        self.assertEqual(store.get_complaint(row["complaint_id"])["exact_spot"], spot)

    def test_spoken_id(self):
        self.assertEqual(store.spoken_id("CIV1047"), "C I V one zero four seven")

    def test_escalation_moves_up_one_level(self):
        row = store.raise_escalation("CIV1002")
        self.assertEqual(row["escalation_level"], 2)
        self.assertEqual(row["authority"], "Zonal officer")
        self.assertFalse(row["already_top"])

    def test_escalation_extends_the_target(self):
        row = store.raise_escalation("CIV1002")
        self.assertEqual(date.fromisoformat(row["target_on"]),
                         date.today() + timedelta(days=7))
        self.assertFalse(row["is_overdue"])

    def test_escalation_stops_at_the_top(self):
        store.raise_escalation("CIV1002")
        store.raise_escalation("CIV1002")
        row = store.raise_escalation("CIV1002")
        self.assertTrue(row["already_top"])
        self.assertEqual(row["escalation_level"], 3)

    def test_attach_note_keeps_the_original(self):
        store.attach_note("CIV1004", "Also reported by 9999999999.")
        store.attach_note("CIV1004", "Also reported by 8888888888.")
        note = store.get_complaint("CIV1004")["resolution_note"]
        self.assertIn("9999999999", note)
        self.assertIn("8888888888", note)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class TestReportProblemTools(TempStore):

    def setUp(self):
        super().setUp()
        from skills.report_problem import tools as rt
        self.t = rt

    def _ready_context(self):
        """A context as it stands just before filing."""
        return FakeContext(
            category="pothole", department="Road Maintenance", sla_days="7",
            ward_id="W12", ward_label="Vaishali", ward_officer="A. Sharma",
            ward_confirmed=True, exact_spot="by the temple gate",
            description="Deep pothole", callback_number="9876543210",
            caller_id="501",
            details_verified=True, duplicate_decision="new",
        )

    def test_record_category_sets_department_and_target(self):
        ctx = FakeContext()
        result = run(self.t.record_category("garbage", ctx)).llm_response
        self.assertTrue(result["ok"])
        self.assertEqual(ctx.memory.get("department"), "Sanitation")
        self.assertEqual(ctx.memory.get("sla_days"), "2")

    def test_record_category_normalises_spacing(self):
        ctx = FakeContext()
        self.assertTrue(run(self.t.record_category("water supply", ctx)).llm_response["ok"])

    def test_a_category_is_found_inside_a_phrase(self):
        """Callers hand over a phrase, not a key. "uncollected garbage" used to
        come back as out of scope while "garbage" filed happily."""
        from lib import store
        self.assertEqual(store.normalise_category("uncollected garbage"), "garbage")
        self.assertEqual(store.normalise_category("broken street light"), "streetlight")
        self.assertEqual(store.normalise_category("stray dogs"), "stray_animals")

    def test_the_longest_matching_category_wins(self):
        """"street light" must not be swallowed by the bare word "light"."""
        from lib import store
        self.assertEqual(store.normalise_category("street light"), "streetlight")

    def test_a_phrase_with_no_category_in_it_stays_unmatched(self):
        from lib import store
        self.assertEqual(store.normalise_category("property tax"), "property_tax")

    def test_record_category_rejects_anything_else(self):
        ctx = FakeContext()
        result = run(self.t.record_category("property tax", ctx)).llm_response
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "unsupported_category")
        self.assertIsNone(ctx.memory.get("category"))

    def test_find_ward_stores_candidates(self):
        ctx = FakeContext()
        result = run(self.t.find_ward("Vaishali", ctx)).llm_response
        self.assertEqual(result["found"], 1)
        self.assertTrue(ctx.memory.get("ward_candidates"))

    def test_find_ward_finding_nothing_is_not_an_error(self):
        result = run(self.t.find_ward("outside our lane", FakeContext())).llm_response
        self.assertTrue(result["ok"])
        self.assertEqual(result["found"], 0)

    def test_confirm_ward_writes_the_officer(self):
        ctx = FakeContext()
        run(self.t.find_ward("Indirapuram", ctx))
        result = run(self.t.confirm_ward("1", ctx)).llm_response
        self.assertTrue(result["ok"])
        self.assertEqual(ctx.memory.get("ward_officer"), "S. Kaur")
        self.assertTrue(ctx.memory.get("ward_confirmed"))

    def test_a_plain_yes_confirms_a_single_option(self):
        """Callers do not answer a one-item list with "one". Observed live:
        the agent asked for a digit three turns running."""
        ctx = FakeContext()
        run(self.t.find_ward("Indirapuram", ctx))
        result = run(self.t.confirm_ward("Yes that is the one", ctx)).llm_response
        self.assertTrue(result["ok"])
        self.assertEqual(ctx.memory.get("ward_officer"), "S. Kaur")

    def test_a_plain_yes_is_ambiguous_when_several_were_offered(self):
        from skills.report_problem.tools import _pick
        self.assertEqual(_pick("yes", 3), -1)

    def test_an_ordinal_picks_from_a_list(self):
        from skills.report_problem.tools import _pick
        self.assertEqual(_pick("the second one", 3), 1)

    def test_a_refusal_is_not_a_choice(self):
        from skills.report_problem.tools import _pick
        self.assertEqual(_pick("nope", 1), -1)

    def test_confirm_ward_rejects_an_option_that_was_not_offered(self):
        ctx = FakeContext()
        run(self.t.find_ward("Indirapuram", ctx))
        result = run(self.t.confirm_ward("4", ctx)).llm_response
        self.assertFalse(result["ok"])
        self.assertFalse(ctx.memory.get("ward_confirmed"))

    def test_two_misses_route_to_the_grievance_cell_without_asking_again(self):
        """The caller who cannot name their own locality is the one person on
        this line who least needs to be asked a third time."""
        ctx = FakeContext()
        first = run(self.t.find_ward("outside our lane", ctx)).llm_response
        self.assertEqual(first["found"], 0)
        self.assertFalse(ctx.memory.get("ward_confirmed"))

        second = run(self.t.find_ward("there is nothing nearby", ctx)).llm_response
        self.assertTrue(second["ok"])
        self.assertTrue(ctx.memory.get("ward_confirmed"))
        self.assertEqual(ctx.memory.get("ward_id"), "GEN")
        self.assertIn("grievance cell", ctx.said[-1])

    def test_a_later_success_does_not_trip_the_counter(self):
        ctx = FakeContext()
        run(self.t.find_ward("outside our lane", ctx))
        found = run(self.t.find_ward("Vaishali", ctx)).llm_response
        self.assertEqual(found["found"], 1)
        self.assertNotEqual(ctx.memory.get("ward_id"), "GEN")

    def test_general_cell_takes_the_complaint_anyway(self):
        ctx = FakeContext()
        result = run(self.t.use_general_cell(ctx)).llm_response
        self.assertTrue(result["ok"])
        self.assertTrue(ctx.memory.get("ward_confirmed"))
        self.assertEqual(ctx.memory.get("ward_id"), "GEN")

    def test_callback_number_accepts_spoken_digits(self):
        ctx = FakeContext()
        spoken = "nine eight seven six five four three two one zero"
        result = run(self.t.record_callback_number(spoken, ctx)).llm_response
        self.assertEqual(result["number"], "9876543210")

    def test_callback_number_rejects_short_input(self):
        ctx = FakeContext()
        result = run(self.t.record_callback_number("nine eight seven", ctx)).llm_response
        self.assertFalse(result["ok"])
        self.assertIsNone(ctx.memory.get("callback_number"))

    def test_similar_finds_the_open_one_in_the_same_ward(self):
        ctx = FakeContext(category="drainage", ward_id="W12",
                          callback_number="9876543210")
        result = run(self.t.find_similar_open(ctx)).llm_response
        self.assertEqual(result["found"], 1)
        self.assertEqual(ctx.memory.get("similar_id"), "CIV1004")

    def test_no_duplicate_decides_itself(self):
        """Most calls take this branch and should never hear the word."""
        ctx = FakeContext(category="pothole", ward_id="W14",
                          callback_number="9876543210")
        result = run(self.t.find_similar_open(ctx)).llm_response
        self.assertEqual(result["found"], 0)
        self.assertEqual(ctx.memory.get("duplicate_decision"), "new")
        self.assertEqual(ctx.said, [])

    def test_a_duplicate_leaves_the_decision_to_the_caller(self):
        """The tool finds it and clears the field; only the caller's answer
        fills it in, so the step cannot complete without them."""
        ctx = FakeContext(category="drainage", ward_id="W12",
                          callback_number="9876543210")
        result = run(self.t.find_similar_open(ctx)).llm_response
        self.assertEqual(result["found"], 1)
        self.assertIsNone(ctx.memory.get("duplicate_decision"))
        self.assertEqual(ctx.said, [])

    def test_zero_argument_tools_survive_a_spurious_kwarg(self):
        """Observed live: the model filled the empty parameter object with
        {"": ""} and the call came back as a TypeError."""
        ctx = FakeContext(category="pothole", ward_id="W14",
                          callback_number="9876543210")
        self.assertTrue(run(self.t.find_similar_open(ctx, **{"": ""})).llm_response["ok"])

    def test_similar_never_reads_out_someone_elses_reference(self):
        ctx = FakeContext(category="drainage", ward_id="W12",
                          callback_number="9876543210")
        result = run(self.t.find_similar_open(ctx)).llm_response
        self.assertNotIn("complaint_id", result)

    def test_similar_includes_the_callers_own_complaint(self):
        ctx = FakeContext(category="drainage", ward_id="W12",
                          callback_number="9812345678")
        self.assertEqual(run(self.t.find_similar_open(ctx)).llm_response["found"], 1)

    def test_file_complaint_returns_a_reference(self):
        ctx = self._ready_context()
        result = run(self.t.file_complaint(ctx)).llm_response
        self.assertTrue(result["ok"])
        self.assertEqual(result["officer"], "A. Sharma")
        self.assertEqual(result["spoken_id"], store.spoken_id(result["complaint_id"]))

    def test_the_tool_speaks_the_reference_itself(self):
        """The one sentence the whole call exists to deliver. Left to the
        model it was a coin flip, so the tool says it."""
        ctx = self._ready_context()
        result = run(self.t.file_complaint(ctx)).llm_response
        self.assertEqual(len(ctx.said), 1)
        spoken = ctx.said[0]
        self.assertIn(result["spoken_id"], spoken)
        self.assertIn("A. Sharma", spoken)
        self.assertIn("Vaishali", spoken)

    def test_the_general_cell_line_does_not_name_a_ward_officer(self):
        """"The Grievance Cell duty officer is the ward officer for General
        Grievance Cell" is a sentence only a template could produce."""
        ctx = self._ready_context()
        ctx.memory.set("ward_id", "GEN")
        ctx.memory.set("ward_label", "General Grievance Cell")
        ctx.memory.set("ward_officer", "Grievance Cell duty officer")
        run(self.t.file_complaint(ctx))
        self.assertIn("grievance cell", ctx.said[0])
        self.assertNotIn("is the ward officer for", ctx.said[0])

    def test_the_spoken_line_reads_the_date_not_the_digits(self):
        ctx = self._ready_context()
        run(self.t.file_complaint(ctx))
        self.assertNotRegex(ctx.said[0], r"\d{4}-\d{2}-\d{2}")
        self.assertRegex(ctx.said[0], r"the [a-z ]+ of [A-Z][a-z]+")

    def test_nothing_is_spoken_when_filing_fails(self):
        ctx = self._ready_context()
        os.environ["CIVICO_FORCE_FILE_FAILURE"] = "1"
        self.addCleanup(os.environ.pop, "CIVICO_FORCE_FILE_FAILURE", None)
        run(self.t.file_complaint(ctx))
        self.assertEqual(ctx.said, [])

    def test_file_complaint_persists(self):
        ctx = self._ready_context()
        filed = run(self.t.file_complaint(ctx)).llm_response
        self.assertIsNotNone(store.get_complaint(filed["complaint_id"]))

    def test_forced_failure_files_nothing(self):
        """`make demo-failure` — the on_failure lever, and it must not half-write."""
        ctx = self._ready_context()
        os.environ["CIVICO_FORCE_FILE_FAILURE"] = "1"
        self.addCleanup(os.environ.pop, "CIVICO_FORCE_FILE_FAILURE", None)
        result = run(self.t.file_complaint(ctx)).llm_response
        self.assertFalse(result["ok"])
        self.assertIsNone(store.get_complaint("CIV1005"))

    def test_attach_adds_to_the_existing_complaint(self):
        ctx = self._ready_context()
        ctx.memory.set("category", "drainage")
        ctx.memory.set("duplicate_decision", "attach")
        ctx.memory.set("similar_id", "CIV1004")
        result = run(self.t.attach_to_existing(ctx)).llm_response
        self.assertTrue(result["ok"])
        self.assertIn("CIV1004", [r["complaint_id"]
                                 for r in store.complaints_for_phone("9876543210")])

    def test_attach_speaks_the_existing_reference(self):
        ctx = self._ready_context()
        ctx.memory.set("category", "drainage")
        ctx.memory.set("duplicate_decision", "attach")
        ctx.memory.set("similar_id", "CIV1004")
        result = run(self.t.attach_to_existing(ctx)).llm_response
        self.assertEqual(result["spoken_id"], "C I V one zero zero four")
        self.assertEqual(len(ctx.said), 1)
        self.assertIn(result["spoken_id"], ctx.said[0])


class TestCheckStatusTools(TempStore):

    def setUp(self):
        super().setUp()
        from skills.check_status import tools as ct
        from tools import civic
        self.t = ct
        # look_up_complaint is shared, not skill-local: escalate needs it too,
        # and a skill cannot reach into another skill's tools.py.
        self.shared = civic

    def test_look_up_by_reference(self):
        result = run(self.shared.look_up_complaint("CIV1001", FakeContext())).llm_response
        self.assertTrue(result["ok"])
        self.assertEqual(result["officer"], "A. Sharma")

    def test_look_up_tolerates_spoken_spacing(self):
        self.assertTrue(run(self.shared.look_up_complaint("CIV 1001", FakeContext())).llm_response["ok"])

    def test_look_up_accepts_a_reference_read_out_loud(self):
        result = run(self.shared.look_up_complaint(
            "C I V one zero zero one", FakeContext())).llm_response
        self.assertTrue(result["ok"])
        self.assertEqual(result["complaint_id"], "CIV1001")

    def test_look_up_flags_overdue_into_memory(self):
        ctx = FakeContext()
        run(self.shared.look_up_complaint("CIV1002", ctx))
        self.assertTrue(ctx.memory.get("is_overdue"))

    def test_look_up_unknown_reference(self):
        result = run(self.shared.look_up_complaint("CIV9999", FakeContext())).llm_response
        self.assertEqual(result["error"], "not_found")

    def test_list_never_searches_the_calling_number_unasked(self):
        """Caller ID is not consent. This used to default to the calling
        number, handing over a whole complaint history to anyone on the line."""
        ctx = FakeContext(caller_phone="9876543210")
        result = run(self.t.list_my_complaints("", ctx)).llm_response
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "no_number")

    def test_list_offers_only_the_last_four_digits(self):
        ctx = FakeContext(caller_phone="9876543210")
        result = run(self.t.list_my_complaints("", ctx)).llm_response
        self.assertEqual(result["calling_number_ends"], "3210")
        self.assertNotIn("9876543210", json.dumps(result))

    def test_list_searches_once_the_number_is_given(self):
        ctx = FakeContext(caller_phone="9876543210")
        result = run(self.t.list_my_complaints("9876543210", ctx)).llm_response
        self.assertEqual(result["found"], 3)

    def test_list_returns_the_single_match_directly(self):
        ctx = FakeContext(caller_phone="9812345678")
        result = run(self.t.list_my_complaints("9812345678", ctx)).llm_response
        self.assertEqual(result["found"], 1)
        self.assertEqual(result["complaint_id"], "CIV1004")

    def test_list_never_reads_reference_numbers_in_the_options(self):
        ctx = FakeContext(caller_phone="9876543210")
        result = run(self.t.list_my_complaints("9876543210", ctx)).llm_response
        for option in result["options"]:
            self.assertNotIn("CIV", option["say"])

    def test_choose_picks_from_the_list(self):
        ctx = FakeContext(caller_phone="9876543210")
        run(self.t.list_my_complaints("9876543210", ctx))
        result = run(self.t.choose_complaint("1", ctx)).llm_response
        self.assertTrue(result["ok"])
        self.assertTrue(result["complaint_id"].startswith("CIV"))

    def test_choose_rejects_an_option_that_was_not_offered(self):
        ctx = FakeContext(caller_phone="9876543210")
        run(self.t.list_my_complaints("9876543210", ctx))
        self.assertFalse(run(self.t.choose_complaint("9", ctx)).llm_response["ok"])


class TestEscalateTool(TempStore):

    def setUp(self):
        super().setUp()
        from tools import civic
        self.t = civic

    def test_overdue_complaint_escalates(self):
        result = run(self.t.escalate_complaint("CIV1002", FakeContext())).llm_response
        self.assertTrue(result["ok"])
        self.assertEqual(result["authority"], "Zonal officer")

    def test_the_tool_speaks_the_new_authority_and_date(self):
        """The step completes on a field this tool writes, so the model gets no
        dependable turn. Left to the instruction the caller heard "Done." """
        ctx = FakeContext()
        run(self.t.escalate_complaint("CIV1002", ctx))
        self.assertEqual(len(ctx.said), 1)
        self.assertIn("zonal officer", ctx.said[0])
        self.assertIn("C I V one zero zero two", ctx.said[0])
        self.assertNotRegex(ctx.said[0], r"\d{4}-\d{2}-\d{2}")

    def test_nothing_is_spoken_when_escalation_is_refused(self):
        ctx = FakeContext()
        run(self.t.escalate_complaint("CIV1001", ctx))
        self.assertEqual(ctx.said, [])

    def test_the_clock_refuses_not_the_model(self):
        result = run(self.t.escalate_complaint("CIV1001", FakeContext())).llm_response
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "still_within_target")

    def test_closed_complaint_cannot_escalate(self):
        result = run(self.t.escalate_complaint("CIV1003", FakeContext())).llm_response
        self.assertEqual(result["error"], "already_closed")

    def test_escalating_resets_the_clock(self):
        """A complaint just raised to the zonal officer is not instantly
        overdue again — the new authority gets its own seven days before it
        can be pushed further. Escalations cannot be chained in one call."""
        run(self.t.escalate_complaint("CIV1002", FakeContext()))
        result = run(self.t.escalate_complaint("CIV1002", FakeContext())).llm_response
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "still_within_target")

    def test_top_of_the_ladder_is_admitted_not_invented(self):
        run(self.t.escalate_complaint("CIV1002", FakeContext()))
        self._make_overdue("CIV1002")
        run(self.t.escalate_complaint("CIV1002", FakeContext()))
        self._make_overdue("CIV1002")
        result = run(self.t.escalate_complaint("CIV1002", FakeContext())).llm_response
        self.assertEqual(result["error"], "already_at_top_level")
        self.assertIn("grievance cell", result["authority"])

    def _make_overdue(self, complaint_id):
        """Push a target date into the past, standing in for time passing."""
        past = (date.today() - timedelta(days=2)).isoformat()
        with store.connect() as conn:
            conn.execute("UPDATE complaints SET target_on = ? WHERE complaint_id = ?",
                         (past, complaint_id))
            conn.commit()

    def test_falls_back_to_the_complaint_in_hand(self):
        ctx = FakeContext(complaint_id="CIV1002")
        self.assertTrue(run(self.t.escalate_complaint("", ctx)).llm_response["ok"])

    def test_unknown_reference(self):
        result = run(self.t.escalate_complaint("CIV9999", FakeContext())).llm_response
        self.assertEqual(result["error"], "not_found")


class TestWhoHandlesTool(TempStore):

    def setUp(self):
        super().setUp()
        from skills.who_handles_this import tools as wt
        self.t = wt

    def test_category_and_area(self):
        result = run(self.t.who_handles("garbage", "Indirapuram", FakeContext())).llm_response
        self.assertEqual(result["department"], "Sanitation")
        self.assertEqual(result["officer"], "S. Kaur")

    def test_category_alone(self):
        result = run(self.t.who_handles("pothole", "", FakeContext())).llm_response
        self.assertEqual(result["target_days"], 7)
        self.assertNotIn("officer", result)

    def test_area_alone(self):
        result = run(self.t.who_handles("", "Mohan Nagar", FakeContext())).llm_response
        self.assertEqual(result["officer"], "B. Rathore")

    def test_the_category_map_is_shared_with_the_report_flow(self):
        """"Who handles potholes" was told this line does not handle
        potholes, while "there is a pothole" filed one without complaint —
        the alias map lived inside the other skill's tools."""
        result = run(self.t.who_handles("potholes", "Kavi Nagar", FakeContext())).llm_response
        self.assertEqual(result["department"], "Road Maintenance")
        self.assertNotIn("unsupported_category", result)

    def test_ward_numbers_are_read_the_same_way_everywhere(self):
        result = run(self.t.who_handles("", "Kavi Nagar", FakeContext())).llm_response
        self.assertEqual(result["ward"], "1")

    def test_unknown_area_is_admitted(self):
        result = run(self.t.who_handles("garbage", "Vijayawada", FakeContext())).llm_response
        self.assertEqual(result["area_not_found"], "Vijayawada")
        self.assertNotIn("officer", result)


class TestLoadCaller(TempStore):

    def setUp(self):
        super().setUp()
        from tools import civic
        self.t = civic

    def test_known_number(self):
        os.environ["CIVICO_DEMO_CALLER"] = "9876543210"
        self.addCleanup(os.environ.pop, "CIVICO_DEMO_CALLER", None)
        ctx = FakeContext()
        result = run(self.t.load_caller(ctx)).llm_response
        self.assertTrue(result["known"])
        self.assertEqual(result["first_name"], "Ravi")
        self.assertTrue(ctx.memory.get("known_caller"))

    def test_unknown_number_is_normal(self):
        os.environ["CIVICO_DEMO_CALLER"] = "9000000000"
        self.addCleanup(os.environ.pop, "CIVICO_DEMO_CALLER", None)
        ctx = FakeContext()
        result = run(self.t.load_caller(ctx)).llm_response
        self.assertFalse(result["known"])
        self.assertEqual(ctx.memory.get("caller_phone"), "9000000000")


if __name__ == "__main__":
    unittest.main(verbosity=2)
