"""The only door into state — and the reason the model cannot walk through it.

THIS FILE IS THE CLAIM
----------------------
Everything else in this package is arrangement. The claim — *the model can
never write the artifact directly* — is enforced here, by three rules that hold
regardless of what the model says, how it is prompted, or what a future skill
author tries to pass in.

RULE 1 — a sourced field takes a CITATION, not a value.
    ``set_sourced_field`` has no ``value`` parameter. It takes a record id and
    a field name, looks the value up itself, and stores what it found. A model
    that wants the total portfolio value to read £900,000 has no argument to
    put £900,000 into. It can only name a record, and the record says what it
    says.

RULE 2 — a negotiated field takes a value from a CLOSED SET.
    ``set_negotiated_field`` accepts a value, but only one drawn from
    ``ALLOWED_NEGOTIATED``. It is a selection, not prose. A model supplying
    free text to a negotiated field is refused with the same vocabulary as any
    other refusal.

RULE 3 — there is no third function.
    No ``set_text``, no ``append_paragraph``, no ``set_section_body``. The
    absence is the mechanism. A model cannot call a tool that does not exist,
    and a future author who needs one has to add it to this file, where the
    refusal rules are the first thing they read.

WHAT ABOUT THE MODEL'S OWN OUTPUT?
----------------------------------
It goes in the transcript, where it belongs. The model negotiates: it asks
which valuation date, explains what a section will say, reads a figure back for
confirmation. None of that reaches the renderer. The renderer's only input is
:class:`docpkg.state.DocumentState`, and the only way a value enters that is
through this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from docpkg.sources import CONVERSATION_SOURCE, Citation, Sourced, resolve
from docpkg.state import (
    FIELDS_BY_KEY,
    REGULATED_SECTIONS,
    DocumentState,
    Revision,
    UnknownField,
)

# ---------------------------------------------------------------------------
# Refusal vocabulary
# ---------------------------------------------------------------------------
# One word per reason, used identically in the tools, the proof output, and the
# chapters. A refusal a reader cannot match to the sentence that described it
# is a refusal they will assume was a bug.

REFUSE_NOT_A_FIELD = "not_a_declared_field"
REFUSE_FREE_TEXT = "free_text_into_sourced_field"
REFUSE_REGULATED = "free_text_into_regulated_section"
REFUSE_NOT_IN_SET = "value_not_in_allowed_set"
REFUSE_SILENT_OVERWRITE = "overwrite_without_reason"
REFUSE_NO_RECORD = "citation_resolves_to_no_record"


class EditRefused(Exception):
    """A refused edit. Carries the vocabulary word so callers can branch on it."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


#: The closed sets a negotiated field may draw from. A negotiated field with no
#: entry here cannot be set at all — the default is "no", not "anything".
ALLOWED_NEGOTIATED: dict[str, tuple[str, ...]] = {
    "addressed_to": ("client", "adviser", "client_and_adviser"),
    "include_property_breakdown": ("yes", "no"),
}


@dataclass(frozen=True)
class EditResult:
    """What an accepted edit did. Returned to the tool layer, and to the proof."""

    state: DocumentState
    field_key: str
    before: str | None
    after: str | None
    citation_label: str | None


def _display(held: Sourced | None) -> str | None:
    """The value as the revision log records it."""
    if held is None or not held.is_present:
        return None
    return str(held.value)


def _append(state: DocumentState, key: str, before: str | None, after: str | None, reason: str) -> tuple[Revision, ...]:
    """Append to the history. The history is never rewritten, only extended.

    ``seq`` is derived from the existing length rather than stored separately,
    so a revision cannot be inserted with a sequence number that lies about
    when it happened.
    """
    return state.revisions + (
        Revision(seq=len(state.revisions) + 1, field_key=key, before=before, after=after, reason=reason),
    )


def set_sourced_field(
    state: DocumentState,
    field_key: str,
    *,
    source_id: str,
    record_id: str,
    record_field: str,
    reason: str,
) -> EditResult:
    """Point a sourced field at a record. NOTE THE ABSENT PARAMETER.

    There is no ``value``. The value is whatever ``resolve`` finds in the named
    record, and if it finds nothing the field is stored as present-but-empty —
    which renders blank rather than raising, because "the August valuation has
    no property line" is a legitimate state for a document to be in and the
    reader needs to see the gap.

    A caller wanting a specific number must find a record that contains it.
    That is the intended difficulty: it is the difference between reporting and
    inventing.
    """
    if field_key not in FIELDS_BY_KEY:
        raise EditRefused(REFUSE_NOT_A_FIELD, f"{field_key!r} is not a declared document field")
    spec = FIELDS_BY_KEY[field_key]
    if spec.kind != "sourced":
        raise EditRefused(
            REFUSE_FREE_TEXT,
            f"{field_key!r} is a negotiated field; use set_negotiated_field",
        )
    if not reason.strip():
        raise EditRefused(
            REFUSE_SILENT_OVERWRITE,
            f"changing {field_key!r} requires a reason — the history is the point",
        )

    citation = Citation(source_id=source_id, record_id=record_id, field=record_field)
    found = resolve(citation)
    before = _display(state.get(field_key))

    values = dict(state.values)
    values[field_key] = Sourced(value=found, citation=citation)
    after = _display(values[field_key])
    revisions = _append(state, field_key, before, after, reason)
    return EditResult(
        state=state.with_values(values, revisions),
        field_key=field_key,
        before=before,
        after=after,
        citation_label=citation.label,
    )


def set_negotiated_field(
    state: DocumentState,
    field_key: str,
    *,
    value: str,
    reason: str,
) -> EditResult:
    """Set a conversation-chosen field, from a closed set of allowed values.

    This is the ONLY function in the package that accepts a value from its
    caller, and it accepts one only if it appears verbatim in
    :data:`ALLOWED_NEGOTIATED`. Free text is refused here, which is what stops
    this function becoming the back door that rules 1 and 3 closed.
    """
    if field_key not in FIELDS_BY_KEY:
        raise EditRefused(REFUSE_NOT_A_FIELD, f"{field_key!r} is not a declared document field")
    spec = FIELDS_BY_KEY[field_key]
    if spec.section in REGULATED_SECTIONS:
        raise EditRefused(
            REFUSE_REGULATED,
            f"{spec.section!r} is a regulated section; its wording comes from "
            f"the disclosure library, never from the conversation",
        )
    if spec.kind != "negotiated" or not spec.llm_settable:
        raise EditRefused(
            REFUSE_FREE_TEXT,
            f"{field_key!r} is a sourced field — it takes a citation, not a value",
        )
    allowed = ALLOWED_NEGOTIATED.get(field_key, ())
    if value not in allowed:
        raise EditRefused(
            REFUSE_NOT_IN_SET,
            f"{value!r} is not an allowed value for {field_key!r}; allowed: {list(allowed)}",
        )
    if not reason.strip():
        raise EditRefused(REFUSE_SILENT_OVERWRITE, f"changing {field_key!r} requires a reason")

    before = _display(state.get(field_key))
    values = dict(state.values)
    # A negotiated field still carries a citation — to the conversation itself,
    # via CONVERSATION_SOURCE. Every field in the provenance table has an
    # origin; none is exempt, and none borrows an origin belonging to another
    # value. The record id is the field key, because the revision log is keyed
    # by field: "who chose this and why" is answerable for a negotiated field
    # exactly as "which record did this come from" is for a sourced one.
    values[field_key] = Sourced(
        value=value,
        citation=Citation(CONVERSATION_SOURCE, field_key, "value"),
    )
    after = value
    revisions = _append(state, field_key, before, after, reason)
    return EditResult(
        state=state.with_values(values, revisions),
        field_key=field_key,
        before=before,
        after=after,
        citation_label="negotiated in conversation",
    )


def clear_field(state: DocumentState, field_key: str, *, reason: str) -> EditResult:
    """Remove a field from state. It then disappears from the document.

    No tombstone, no "deleted" flag. The renderer walks the declared field list
    and asks state for each one; a key that is not there has no value, and a
    field with no value renders blank. Deletion needs no special support
    because absence already means exactly that.
    """
    if field_key not in FIELDS_BY_KEY:
        raise EditRefused(REFUSE_NOT_A_FIELD, f"{field_key!r} is not a declared document field")
    if not reason.strip():
        raise EditRefused(REFUSE_SILENT_OVERWRITE, f"clearing {field_key!r} requires a reason")
    before = _display(state.get(field_key))
    values = dict(state.values)
    values.pop(field_key, None)
    revisions = _append(state, field_key, before, None, reason)
    return EditResult(
        state=state.with_values(values, revisions),
        field_key=field_key,
        before=before,
        after=None,
        citation_label=None,
    )
