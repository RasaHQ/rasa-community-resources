"""Derive a document from structured state — never write one with a model.

The public surface, in the order the pieces run:

    sources   a value and the record it came from, welded into one type
    state     the declared field set; the only thing a conversation edits
    edits     the ONLY door into state, and the reason a model cannot write prose
    verify    re-check every figure against its record; refuse if any disagrees
    render    template + state -> document, a pure function of state alone
"""

from docpkg.edits import (
    ALLOWED_NEGOTIATED,
    EditRefused,
    EditResult,
    clear_field,
    set_negotiated_field,
    set_sourced_field,
)
from docpkg.fixture import build_fixture_state
from docpkg.render import BLANK, render_field, render_markdown
from docpkg.sources import SOURCES, Citation, Sourced, UnknownSource, resolve
from docpkg.state import (
    FIELDS,
    FIELDS_BY_KEY,
    REGULATED_SECTIONS,
    SECTION_ORDER,
    DocumentState,
    FieldSpec,
    Revision,
    UnknownField,
    sourced,
)
from docpkg.verify import Mismatch, ProvenanceBroken, require_intact_provenance, verify_state

__all__ = [
    "ALLOWED_NEGOTIATED",
    "BLANK",
    "Citation",
    "DocumentState",
    "EditRefused",
    "EditResult",
    "FIELDS",
    "FIELDS_BY_KEY",
    "FieldSpec",
    "Mismatch",
    "ProvenanceBroken",
    "REGULATED_SECTIONS",
    "Revision",
    "SECTION_ORDER",
    "SOURCES",
    "Sourced",
    "UnknownField",
    "UnknownSource",
    "build_fixture_state",
    "clear_field",
    "render_field",
    "render_markdown",
    "require_intact_provenance",
    "resolve",
    "set_negotiated_field",
    "set_sourced_field",
    "sourced",
    "verify_state",
]
