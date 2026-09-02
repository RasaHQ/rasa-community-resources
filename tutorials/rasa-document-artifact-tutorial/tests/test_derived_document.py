"""Eval suite. No network, no credentials, no model.

The tests are grouped by the claim each one defends, and the group names match
the declared step list, so a failing test says which teaching claim broke.

The load-bearing ones are in `TestTheRendererRefuses` and
`TestTheModelCannotWriteTheArtifact`. The rest describe the machine; those two
are the guarantee.
"""

from __future__ import annotations

import inspect
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from docpkg import (  # noqa: E402
    ALLOWED_NEGOTIATED,
    BLANK,
    EditRefused,
    ProvenanceBroken,
    build_fixture_state,
    clear_field,
    render_markdown,
    set_negotiated_field,
    set_sourced_field,
)
from docpkg.sources import SOURCES, Citation, UnknownSource, resolve  # noqa: E402
from docpkg.state import FIELDS, FIELDS_BY_KEY, REGULATED_SECTIONS  # noqa: E402


class TestArtifactAsOutcome(unittest.TestCase):
    """step-01: the deliverable is a file, not a reply."""

    def test_rendering_produces_a_document(self):
        document = render_markdown(build_fixture_state())
        self.assertIn("# Suitability record", document)
        self.assertGreater(len(document), 1000)

    def test_the_document_carries_its_own_provenance_table(self):
        document = render_markdown(build_fixture_state())
        self.assertIn("## Provenance", document)
        self.assertIn("## Sources", document)

    def test_the_document_states_what_is_missing_from_it(self):
        document = render_markdown(build_fixture_state())
        completeness = document.split("## Completeness")[1].split("## Sources")[0]
        self.assertIn("property_value", completeness)


class TestStateNotProse(unittest.TestCase):
    """step-02: fields live in declared memory; tools write them."""

    def test_every_sourced_field_is_not_llm_settable(self):
        leaky = [s.key for s in FIELDS if s.kind == "sourced" and s.llm_settable]
        self.assertEqual(leaky, [], "a sourced field the model could set")

    def test_the_only_llm_settable_fields_are_closed_set_selections(self):
        for spec in FIELDS:
            if not spec.llm_settable:
                continue
            self.assertIn(
                spec.key,
                ALLOWED_NEGOTIATED,
                f"{spec.key} is llm_settable with no closed set of allowed values",
            )

    def test_an_undeclared_field_cannot_be_created(self):
        with self.assertRaises(EditRefused) as ctx:
            set_sourced_field(
                build_fixture_state(),
                "a_field_nobody_declared",
                source_id="custodian-extract",
                record_id="VAL-2026-08-29-PF4402",
                record_field="cash_gbp",
                reason="x",
            )
        self.assertEqual(ctx.exception.code, "not_a_declared_field")

    def test_no_declared_field_holds_free_text_from_the_conversation(self):
        """There is no `free_text` field, and adding one should be deliberate."""
        for spec in FIELDS:
            if spec.kind == "negotiated":
                self.assertIn(spec.key, ALLOWED_NEGOTIATED)


class TestTheModelCannotWriteTheArtifact(unittest.TestCase):
    """The central claim, asserted against the SIGNATURES that enforce it."""

    def test_set_sourced_field_has_no_value_parameter(self):
        """The claim, in its strongest form: there is no argument for a value."""
        params = set(inspect.signature(set_sourced_field).parameters)
        self.assertNotIn(
            "value",
            params,
            "set_sourced_field grew a `value` parameter — a model can now write a figure",
        )

    def test_render_markdown_takes_only_state(self):
        """No content parameter, no overrides, no hook."""
        params = list(inspect.signature(render_markdown).parameters)
        self.assertEqual(
            params,
            ["state"],
            "render_markdown grew a parameter; content can now bypass the field set",
        )

    def test_the_agent_tool_for_setting_a_field_exposes_no_value_argument(self):
        """The tool the MODEL calls, not just the function underneath it.

        `voice-handoff-context` learned this the hard way: asserting on a
        convenient internal path while the path that actually runs was different.
        The model fills the tool's signature, so the tool's signature is checked.
        """
        from tools.document import point_field_at_record

        params = set(inspect.signature(point_field_at_record).parameters)
        self.assertNotIn("value", params)
        self.assertIn("record_id", params)

    def test_the_render_tool_accepts_nothing_that_could_become_content(self):
        from tools.document import render_document

        params = [p for p in inspect.signature(render_document).parameters if p != "context"]
        self.assertEqual(params, [], f"render_document accepts {params}")

    def test_free_text_into_a_sourced_field_is_refused(self):
        with self.assertRaises(EditRefused) as ctx:
            set_negotiated_field(
                build_fixture_state(), "objective", value="Whatever sounds good", reason="x"
            )
        self.assertEqual(ctx.exception.code, "free_text_into_sourced_field")

    def test_free_text_into_a_regulated_section_is_refused(self):
        for spec in FIELDS:
            if spec.section not in REGULATED_SECTIONS:
                continue
            with self.assertRaises(EditRefused) as ctx:
                set_negotiated_field(
                    build_fixture_state(), spec.key, value="anything", reason="x"
                )
            self.assertEqual(
                ctx.exception.code,
                "free_text_into_regulated_section",
                f"{spec.key} in regulated section {spec.section} was not protected",
            )

    def test_a_negotiated_value_outside_the_closed_set_is_refused(self):
        with self.assertRaises(EditRefused) as ctx:
            set_negotiated_field(
                build_fixture_state(), "addressed_to", value="anyone at all", reason="x"
            )
        self.assertEqual(ctx.exception.code, "value_not_in_allowed_set")


class TestGroundedFields(unittest.TestCase):
    """step-03: every figure traces to a record; unsourced renders BLANK."""

    def test_every_populated_field_carries_a_citation(self):
        state = build_fixture_state()
        for key, held in state.values.items():
            self.assertIsNotNone(held.citation, f"{key} has no citation")
            self.assertTrue(held.citation.record_id)

    def test_the_document_draws_on_both_fixture_sources(self):
        state = build_fixture_state()
        cited = {h.citation.source_id for h in state.values.values()}
        self.assertIn("custodian-extract", cited)
        self.assertIn("advice-factfind", cited)

    def test_a_citation_to_an_undeclared_source_is_rejected(self):
        with self.assertRaises(UnknownSource):
            Citation("some-source-nobody-declared", "REC-1", "value")

    def test_an_unsourced_field_renders_blank(self):
        document = render_markdown(build_fixture_state())
        self.assertIn(f"| Property funds | {BLANK} |", document)

    def test_an_unsourced_field_never_renders_a_plausible_figure(self):
        document = render_markdown(build_fixture_state())
        rows = [ln for ln in document.splitlines() if ln.startswith("| Property funds")]
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(BLANK, row)
            self.assertNotIn("£", row)

    def test_a_citation_to_a_missing_record_resolves_to_none_not_a_guess(self):
        self.assertIsNone(
            resolve(Citation("custodian-extract", "POS-NOT-A-RECORD", "value_gbp"))
        )

    def test_pointing_a_field_at_a_missing_record_renders_blank(self):
        state = set_sourced_field(
            build_fixture_state(),
            "property_value",
            source_id="custodian-extract",
            record_id="POS-NOT-A-RECORD",
            record_field="value_gbp",
            reason="x",
        ).state
        self.assertIn(f"| Property funds | {BLANK} |", render_markdown(state))


class TestDerivedRendering(unittest.TestCase):
    """step-04: template + state -> document, recomputed every time."""

    def test_unchanged_state_renders_byte_identically(self):
        first = render_markdown(build_fixture_state()).encode()
        second = render_markdown(build_fixture_state()).encode()
        self.assertEqual(first, second)

    def test_rendering_is_stable_across_many_runs(self):
        renders = {render_markdown(build_fixture_state()).encode() for _ in range(5)}
        self.assertEqual(len(renders), 1)

    def test_deleting_a_field_removes_it_from_the_document_body(self):
        state = clear_field(build_fixture_state(), "objective", reason="withdrawn").state
        body = render_markdown(state).split("## Revision history")[0]
        self.assertNotIn("Draw a steady income", body)

    def test_a_field_not_in_state_simply_does_not_appear(self):
        state = clear_field(build_fixture_state(), "risk_profile", reason="x").state
        document = render_markdown(state)
        provenance = document.split("## Provenance")[1].split("## Completeness")[0]
        self.assertNotIn("| risk_profile |", provenance)

    def test_the_renderer_has_no_parameter_through_which_to_smuggle_content(self):
        """A 'document' handed around the renderer has nowhere to land."""
        self.assertEqual(list(inspect.signature(render_markdown).parameters), ["state"])


class TestTheRendererRefuses(unittest.TestCase):
    """The load-bearing negative: mutate the provenance table, get a refusal."""

    def setUp(self):
        self.source_path = SOURCES["custodian-extract"].path
        self.original = self.source_path.read_text()
        self.backup_dir = Path(tempfile.mkdtemp())
        (self.backup_dir / "holdings.json").write_text(self.original)

    def tearDown(self):
        self.source_path.write_text(self.original)
        shutil.rmtree(self.backup_dir, ignore_errors=True)

    def _restate(self, **changes):
        payload = json.loads(self.original)
        payload["valuations"][0].update(changes)
        self.source_path.write_text(json.dumps(payload, indent=2))

    def test_a_restated_figure_makes_the_renderer_refuse(self):
        state = build_fixture_state()
        self._restate(total_value_gbp=911000.00)
        with self.assertRaises(ProvenanceBroken):
            render_markdown(state)

    def test_the_refusal_names_the_field_that_disagrees(self):
        state = build_fixture_state()
        self._restate(total_value_gbp=911000.00)
        with self.assertRaises(ProvenanceBroken) as ctx:
            render_markdown(state)
        self.assertIn("total_value", [m.field_key for m in ctx.exception.mismatches])

    def test_the_refusal_shows_both_values(self):
        state = build_fixture_state()
        self._restate(total_value_gbp=911000.00)
        with self.assertRaises(ProvenanceBroken) as ctx:
            render_markdown(state)
        message = str(ctx.exception)
        self.assertIn("486210.44", message)
        self.assertIn("911000", message)

    def test_a_deleted_source_record_makes_the_renderer_refuse(self):
        state = build_fixture_state()
        payload = json.loads(self.original)
        payload["valuations"] = []
        self.source_path.write_text(json.dumps(payload, indent=2))
        with self.assertRaises(ProvenanceBroken):
            render_markdown(state)

    def test_restoring_the_source_restores_the_document(self):
        state = build_fixture_state()
        self._restate(total_value_gbp=911000.00)
        with self.assertRaises(ProvenanceBroken):
            render_markdown(state)
        self.source_path.write_text(self.original)
        self.assertIn("£486,210.44", render_markdown(state))

    def test_the_refusal_reaches_the_agent_tool_as_a_refusal_not_a_crash(self):
        """The path the AGENT runs, not just the function underneath it."""
        import tools.document as td

        td._reset_for_tests()
        self._restate(total_value_gbp=911000.00)
        result = td.render_document().llm_response
        self.assertFalse(result["ok"])
        self.assertEqual(result["refused"], "provenance_broken")
        self.assertIn("total_value", result["fields"])
        td._reset_for_tests()


class TestRevisionAsDiff(unittest.TestCase):
    """step-05: an edit changes state and re-renders; history is append-only."""

    def test_an_edit_appends_to_the_history(self):
        state = build_fixture_state()
        before = len(state.revisions)
        edited = set_sourced_field(
            state, "risk_profile", source_id="advice-factfind",
            record_id="FF-77301-RSK", record_field="scale", reason="scale asked for",
        ).state
        self.assertEqual(len(edited.revisions), before + 1)

    def test_the_history_is_append_only(self):
        state = build_fixture_state()
        edited = set_sourced_field(
            state, "risk_profile", source_id="advice-factfind",
            record_id="FF-77301-RSK", record_field="scale", reason="x",
        ).state
        self.assertEqual(edited.revisions[: len(state.revisions)], state.revisions)

    def test_a_change_without_a_reason_is_refused(self):
        with self.assertRaises(EditRefused) as ctx:
            set_sourced_field(
                build_fixture_state(), "total_value", source_id="custodian-extract",
                record_id="VAL-2026-08-29-PF4402", record_field="cash_gbp", reason="   ",
            )
        self.assertEqual(ctx.exception.code, "overwrite_without_reason")

    def test_clearing_without_a_reason_is_refused(self):
        with self.assertRaises(EditRefused) as ctx:
            clear_field(build_fixture_state(), "objective", reason="")
        self.assertEqual(ctx.exception.code, "overwrite_without_reason")

    def test_one_field_changed_means_one_field_diffs(self):
        state = build_fixture_state()
        before = render_markdown(state).split("## Revision history")[0]
        edited = set_sourced_field(
            state, "risk_profile", source_id="advice-factfind",
            record_id="FF-77301-RSK", record_field="scale", reason="x",
        ).state
        after = render_markdown(edited).split("## Revision history")[0]

        changed = [
            (b, a)
            for b, a in zip(before.splitlines(), after.splitlines())
            if b != a
        ]
        self.assertTrue(changed)
        for b, a in changed:
            self.assertTrue(
                "risk_profile" in b or "Risk profile" in b,
                f"an unrelated line changed: {b!r} -> {a!r}",
            )

    def test_the_deleted_value_survives_in_the_history(self):
        state = clear_field(build_fixture_state(), "objective", reason="withdrawn").state
        history = render_markdown(state).split("## Revision history")[1]
        self.assertIn("Draw a steady income", history)


class TestStatedLimits(unittest.TestCase):
    """step-06: the refusals, in the same vocabulary the chapters use."""

    def test_every_refusal_code_is_reachable(self):
        """Each documented refusal is produced by some real call."""
        state = build_fixture_state()
        seen = set()

        for call in (
            lambda: set_sourced_field(state, "nope", source_id="custodian-extract",
                                      record_id="X", record_field="y", reason="r"),
            lambda: set_negotiated_field(state, "objective", value="v", reason="r"),
            lambda: set_negotiated_field(state, "risk_warning", value="v", reason="r"),
            lambda: set_negotiated_field(state, "addressed_to", value="nope", reason="r"),
            lambda: clear_field(state, "objective", reason=""),
        ):
            try:
                call()
            except EditRefused as exc:
                seen.add(exc.code)

        self.assertEqual(
            seen,
            {
                "not_a_declared_field",
                "free_text_into_sourced_field",
                "free_text_into_regulated_section",
                "value_not_in_allowed_set",
                "overwrite_without_reason",
            },
        )

    def test_the_regulated_sections_are_named_not_implied(self):
        self.assertTrue(REGULATED_SECTIONS)
        for section in REGULATED_SECTIONS:
            self.assertIn(section, {spec.section for spec in FIELDS})

    def test_disclosures_are_quoted_verbatim_from_the_library(self):
        """The wording in the document is byte-identical to the approved text."""
        library = json.loads(SOURCES["disclosure-library"].path.read_text())
        approved = {d["record_id"]: d["text"] for d in library["disclosures"]}
        document = render_markdown(build_fixture_state())
        for text in approved.values():
            with self.subTest(text=text[:40]):
                self.assertIn(text, document)


if __name__ == "__main__":
    unittest.main()
