"""Template + state -> document. A pure function, and the only writer of files.

THE DERIVATION
--------------
:func:`render_markdown` takes a :class:`~docpkg.state.DocumentState` and returns
a string. It takes nothing else. There is no ``extra_text`` parameter, no
``overrides`` mapping, and no hook — which is what makes "the model cannot write
the artifact" true at the render boundary as well as at the edit boundary.

It walks :data:`docpkg.state.FIELDS` in declared order, asks state for each key,
and formats what it gets. A field state does not hold renders BLANK: the label
appears, the value is an em-dash, and the field is listed in the completeness
report at the foot of the document. Never a placeholder that reads like a
figure, never a value carried over from a previous render, never a plausible
default.

DETERMINISM, AND WHY IT IS A REQUIREMENT AND NOT A NICETY
---------------------------------------------------------
The same state renders the same bytes, always. No timestamp of rendering, no
random ids, no dict iteration order — fields come from a declared tuple, and the
provenance table is sorted. This is what makes ``revision-as-diff`` mean
anything: if rendering were nondeterministic, every diff would be noise with a
real change buried in it, and nobody would read the diffs.

The document DOES carry dates — the valuation date, the disclosure approval
dates. Those are sourced field values, not render-time clock reads. A document
that changes when you render it twice is not a record of anything.
"""

from __future__ import annotations

from docpkg.sources import SOURCES, Sourced
from docpkg.state import FIELDS, SECTION_ORDER, DocumentState
from docpkg.verify import require_intact_provenance

#: What a blank field renders as. Deliberately not "N/A", "TBC", "0", or an
#: empty string: a reader skimming a column of numbers must be able to see that
#: something is missing, and a zero reads as a figure.
BLANK = "—"


def _money_gbp(value: object) -> str:
    """Format as sterling, with thousands separators and exactly two decimals."""
    try:
        return f"£{float(value):,.2f}"
    except (TypeError, ValueError):
        # An unformattable value is a data problem, not a rendering problem.
        # It is shown raw rather than swallowed, so the document itself carries
        # the evidence of the bad record.
        return str(value)


def _percent(value: object) -> str:
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _integer(value: object) -> str:
    try:
        return f"{int(value):d}"
    except (TypeError, ValueError):
        return str(value)


def _format(value: object, fmt: str) -> str:
    if fmt == "money_gbp":
        return _money_gbp(value)
    if fmt == "percent":
        return _percent(value)
    if fmt == "integer":
        return _integer(value)
    if fmt == "quote":
        # Regulated wording is quoted verbatim, with no reflow and no edit.
        return str(value).strip()
    return str(value).strip()


def render_field(held: Sourced | None, fmt: str) -> str:
    """One field's rendered text, or :data:`BLANK`.

    The single place the blank rule is implemented. Every section goes through
    it, so there is no section where an unsourced field could render as
    something else.
    """
    if held is None or not held.is_present:
        return BLANK
    return _format(held.value, fmt)


def render_markdown(state: DocumentState) -> str:
    """Derive the document. THE ONLY ARGUMENT IS STATE.

    Note the signature. There is no parameter through which a caller — a tool, a
    skill, a model, a future refactor — could pass content. Text that is not in
    a declared field, sourced to a record, cannot reach the output, because
    there is nowhere to put it.

    Raises :class:`~docpkg.verify.ProvenanceBroken` if any stored figure no
    longer matches the record it cites. Refusing is the correct outcome: a
    document with a footnote that does not hold is worse than no document,
    because it carries the authority of having been checked.
    """
    require_intact_provenance(state)

    lines: list[str] = []
    out = lines.append

    out("# Suitability record")
    out("")
    out(f"Document `{state.document_id}` · template `{state.template_id}`")
    out("")
    out("> Derived from structured state. Every figure below is followed by the")
    out("> record it came from. Nothing in this document was written by a model.")
    out("")

    # -- the body, section by declared section -------------------------------
    for section in SECTION_ORDER:
        specs = [spec for spec in FIELDS if spec.section == section]
        if not specs:
            continue
        out(f"## {section}")
        out("")
        out("| Field | Value |")
        out("| --- | --- |")
        for spec in specs:
            rendered = render_field(state.get(spec.key), spec.format)
            # Pipes in a value would break the table. Escaping rather than
            # stripping, so the document never silently loses a character that
            # was in the source record.
            rendered = rendered.replace("|", "\\|")
            out(f"| {spec.label} | {rendered} |")
        out("")

    # -- the provenance table ------------------------------------------------
    # Sorted by field key so the table is stable across renders. This table is
    # the document's audit surface: a reader checking a figure starts here.
    out("## Provenance")
    out("")
    out("Every value above, and the record it came from.")
    out("")
    out("| Field | Value | Source record |")
    out("| --- | --- | --- |")
    for spec in FIELDS:
        held = state.get(spec.key)
        if held is None or not held.is_present:
            continue
        rendered = _format(held.value, spec.format).replace("|", "\\|")
        out(f"| {spec.key} | {rendered} | {held.citation.label} |")
    out("")

    # -- what is NOT here ----------------------------------------------------
    # Every gap is named, and the required ones are marked. A reader must never
    # have to infer from a blank whether the value is absent or merely unsought.
    unsourced = state.unsourced()
    required_gaps = set(state.missing_required())
    out("## Completeness")
    out("")
    if unsourced:
        out(f"{len(unsourced)} declared field(s) have no source and render blank:")
        out("")
        for key in unsourced:
            mark = " **(required)**" if key in required_gaps else ""
            out(f"- `{key}`{mark}")
    else:
        out("Every declared field is sourced.")
    out("")

    # -- the sources themselves ---------------------------------------------
    out("## Sources")
    out("")
    out("| Source | Authoritative for |")
    out("| --- | --- |")
    for source_id in sorted(SOURCES):
        source = SOURCES[source_id]
        out(f"| {source.label} | {source.authoritative_for} |")
    out("")

    # -- history -------------------------------------------------------------
    out("## Revision history")
    out("")
    if not state.revisions:
        out("No revisions recorded.")
    else:
        out("| # | Field | Before | After | Reason |")
        out("| --- | --- | --- | --- | --- |")
        for rev in state.revisions:
            before = BLANK if rev.before is None else rev.before
            after = BLANK if rev.after is None else rev.after
            out(f"| {rev.seq} | {rev.field_key} | {before} | {after} | {rev.reason} |")
    out("")

    return "\n".join(lines)
