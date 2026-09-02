"""The agent's tools — and the shape of their SIGNATURES is the security model.

The engine publishes every non-``context`` parameter of a tool to the model as a
JSON schema, and the model fills them in. So a tool's signature is not an
implementation detail: it is the exact list of things the model is allowed to
decide. Read these signatures as a permission list.

    point_field_at_record(field_key, source_id, record_id, record_field, reason)
        ^ no `value`. The model chooses which RECORD. The record chooses the
          value. A model that wants the total to read nine hundred thousand has
          no argument through which to say so.

          The name is NOT `set_document_field`, and that is an engine
          constraint rather than a style choice: `load_shared_tools` in
          3.20.0.dev6 DELETES any shared tool whose name begins with `set_`,
          because that prefix is reserved for a skill's auto-generated collect
          setter. It does so with a `structlog` warning and no error, so the
          tool simply is not there — and the failure surfaces later as
          `unresolved_tool` against the skill, pointing at the skill rather
          than at the name. Worth knowing before naming a shared tool.

    choose_option(field_key, option, reason)
        ^ `option` is a value, and it is checked against a closed set before it
          reaches state. The allowed options are listed back to the model in the
          error, so a wrong guess is corrected rather than silently dropped.

    render_document()
        ^ NO PARAMETERS AT ALL. There is no `content`, no `notes`, no
          `extra_section`. The document is a pure function of state, and this
          tool is a pure function of state too. It cannot be given anything to
          put in the document because it accepts nothing.

The state itself lives in a module-level store rather than in project memory.
Rasa memory holds text; the document state is a typed object graph with
citations, and flattening it into strings to store it would lose exactly the
part that makes the guarantee — a value would be a value again, with its
provenance stripped, which is the condition this whole tutorial exists to
prevent. See ``STATE`` below for what a real deployment does instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from rasa.mantle.tools.decorator import ToolContext, tool
    from rasa.mantle.tools.result import ToolResult
except ModuleNotFoundError:  # pragma: no cover — the bare-python proof path
    # `make prove` runs under bare python3 with no venv and no engine. These
    # shims exist solely so this module imports there; the agent runtime always
    # has the real engine, and the loader only ever sees these tools through it.
    ToolContext = None  # type: ignore[assignment,misc]

    def tool(*, description):  # type: ignore[no-redef]
        def _wrap(func):
            func._tool_description = description
            return func

        return _wrap

    class ToolResult:  # type: ignore[no-redef]
        def __init__(self, llm_response=None):
            self.llm_response = llm_response


from docpkg import (
    ALLOWED_NEGOTIATED,
    EditRefused,
    ProvenanceBroken,
    build_fixture_state,
    clear_field,
    render_markdown,
    set_negotiated_field,
    set_sourced_field,
)
from docpkg.sources import SOURCES, load_source
from docpkg.state import FIELDS, FIELDS_BY_KEY

_OUT = Path(__file__).resolve().parent.parent / "out"

# The document under construction, for the length of this process.
#
# A real deployment keeps this in a document service keyed by `document_id`, and
# the tools become thin clients of it. What must NOT change in that move is the
# direction of the dependency: the document service owns the state and derives
# the artifact, and the agent never receives an artifact it can edit and hand
# back. A round trip through the model is a round trip through something that
# can rewrite a number while sounding certain about it.
STATE = build_fixture_state()


def _reset_for_tests() -> None:
    """Restore the fixture state. Used by the eval suite, never by the agent."""
    global STATE
    STATE = build_fixture_state()


@tool(
    description=(
        "Point a document field at the source record it should take its value "
        "from. Use this for every figure, date, name and disclosure. You do NOT "
        "supply the value — you name the record, and the record supplies it. "
        "Call list_document_fields first if you are unsure of the field_key, and "
        "list_source_records to find a record_id."
    )
)
def point_field_at_record(
    field_key: str,
    source_id: str,
    record_id: str,
    record_field: str,
    reason: str,
    context: Any = None,
) -> ToolResult:
    """Re-point a sourced field. Note the absent `value` parameter."""
    global STATE
    try:
        result = set_sourced_field(
            STATE,
            field_key,
            source_id=source_id,
            record_id=record_id,
            record_field=record_field,
            reason=reason,
        )
    except EditRefused as exc:
        return ToolResult(
            llm_response={"ok": False, "refused": exc.code, "detail": exc.message}
        )
    except Exception as exc:  # unknown source, malformed citation
        return ToolResult(
            llm_response={"ok": False, "refused": "invalid_citation", "detail": str(exc)}
        )

    STATE = result.state
    blank = result.after is None
    return ToolResult(
        llm_response={
            "ok": True,
            "field": result.field_key,
            "before": result.before,
            "after": result.after,
            "cited_as": result.citation_label,
            # Said plainly so the agent tells the caller rather than hiding it.
            "note": (
                "That record has no such value, so this field will render blank."
                if blank
                else None
            ),
        }
    )


@tool(
    description=(
        "Choose one of the options for a field that the conversation decides "
        "rather than a record — currently who the record is addressed to, and "
        "whether to break out the property holdings. Only the listed options "
        "are accepted; this is a selection, not free text."
    )
)
def choose_option(field_key: str, option: str, reason: str, context: Any = None) -> ToolResult:
    """Set a negotiated field from its closed set."""
    global STATE
    try:
        result = set_negotiated_field(STATE, field_key, value=option, reason=reason)
    except EditRefused as exc:
        return ToolResult(
            llm_response={
                "ok": False,
                "refused": exc.code,
                "detail": exc.message,
                "allowed": list(ALLOWED_NEGOTIATED.get(field_key, ())),
            }
        )
    STATE = result.state
    return ToolResult(
        llm_response={
            "ok": True,
            "field": result.field_key,
            "before": result.before,
            "after": result.after,
        }
    )


@tool(
    description=(
        "Remove a field's value. The field then renders blank and is listed as "
        "a gap. Use when a value should not appear in this record at all."
    )
)
def clear_document_field(field_key: str, reason: str, context: Any = None) -> ToolResult:
    """Clear a field. Absence is the only deletion mechanism there is."""
    global STATE
    try:
        result = clear_field(STATE, field_key, reason=reason)
    except EditRefused as exc:
        return ToolResult(
            llm_response={"ok": False, "refused": exc.code, "detail": exc.message}
        )
    STATE = result.state
    return ToolResult(
        llm_response={"ok": True, "field": result.field_key, "was": result.before}
    )


@tool(
    description=(
        "Derive the document from the current state and write it to a file. "
        "Takes no arguments — the document is computed entirely from the fields "
        "that have been set. Returns the path, the number of blank fields, and "
        "nothing you can edit."
    )
)
def render_document(context: Any = None) -> ToolResult:
    """Derive and write. NO PARAMETERS: there is nothing to inject."""
    try:
        markdown = render_markdown(STATE)
    except ProvenanceBroken as exc:
        # The source moved under a figure already in the document. Refusing is
        # the whole point; the agent reports it and does not offer to proceed.
        return ToolResult(
            llm_response={
                "ok": False,
                "refused": "provenance_broken",
                "detail": str(exc),
                "fields": [m.field_key for m in exc.mismatches],
            }
        )

    _OUT.mkdir(exist_ok=True)
    path = _OUT / f"{STATE.document_id}.md"
    path.write_text(markdown)
    unsourced = STATE.unsourced()
    return ToolResult(
        llm_response={
            "ok": True,
            "path": str(path.relative_to(_OUT.parent)),
            "bytes": len(markdown.encode()),
            "unsourced_fields": list(unsourced),
            "unsourced_count": len(unsourced),
            "revisions": len(STATE.revisions),
        }
    )


@tool(
    description=(
        "List the fields this document can contain, which section each belongs "
        "to, whether it is sourced or negotiated, and whether it currently has "
        "a value. Use this to answer questions about what the record will say."
    )
)
def list_document_fields(context: Any = None) -> ToolResult:
    """The declared field set, with current status. Read-only."""
    rows = []
    for spec in FIELDS:
        held = STATE.get(spec.key)
        rows.append(
            {
                "field_key": spec.key,
                "label": spec.label,
                "section": spec.section,
                "kind": spec.kind,
                "has_value": bool(held and held.is_present),
                "cited_as": held.citation.label if held else None,
            }
        )
    return ToolResult(llm_response={"ok": True, "fields": rows})


@tool(
    description=(
        "List the records available in a source, so a field can be pointed at "
        "one. Sources are 'custodian-extract' (holdings, valuations, charges), "
        "'advice-factfind' (objectives and risk) and 'disclosure-library' "
        "(approved wording)."
    )
)
def list_source_records(source_id: str, context: Any = None) -> ToolResult:
    """What is actually in a source. The model picks from THIS, not from memory."""
    if source_id not in SOURCES:
        return ToolResult(
            llm_response={
                "ok": False,
                "refused": "unknown_source",
                "allowed": sorted(SOURCES),
            }
        )
    payload = load_source(source_id)
    records = []
    for key, value in payload.items():
        if key.startswith("_") or not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict) and "record_id" in item:
                records.append(
                    {
                        "record_id": item["record_id"],
                        "fields": sorted(k for k in item if k != "record_id"),
                    }
                )
    return ToolResult(
        llm_response={
            "ok": True,
            "source": SOURCES[source_id].label,
            "authoritative_for": SOURCES[source_id].authoritative_for,
            "records": records,
        }
    )


@tool(
    description=(
        "Show what has changed on this document so far: every field edit, what "
        "it was, what it became, and the reason given. Append-only."
    )
)
def show_revisions(context: Any = None) -> ToolResult:
    """The audit trail, as the caller may ask for it."""
    return ToolResult(
        llm_response={
            "ok": True,
            "revisions": [
                {
                    "seq": r.seq,
                    "field": r.field_key,
                    "before": r.before,
                    "after": r.after,
                    "reason": r.reason,
                }
                for r in STATE.revisions
            ],
        }
    )
