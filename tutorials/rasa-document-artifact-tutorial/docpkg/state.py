"""The document's STATE — the only thing a conversation is allowed to change.

WHAT A CONVERSATION EDITS
-------------------------
Not the document. The state. The document is a pure function of this object
(see :mod:`docpkg.render`), recomputed from scratch every time, so there is no
document to edit — there is only state, and a rendering of it.

Delete a field here and it disappears from the document. That is not a feature
that was added; it is the only behaviour available, because the renderer walks
this object and nothing else.

THE TWO KINDS OF FIELD, AND WHY THE LINE IS WHERE IT IS
-------------------------------------------------------
Every field in a suitability record falls into one of two categories, and
conflating them is the trap this whole tutorial refuses:

``SOURCED``   The field's value comes from a record. Money, weights, dates,
              risk profile, regulated wording. The model may *negotiate* which
              record — "shall I use the August valuation or the July one?" —
              but it may never supply the value. ``llm_settable: false``.

``NEGOTIATED`` The field's value is a choice made in the conversation that no
              record can supply: which sections to include, who the record is
              addressed to, whether the client asked for the property holdings
              to be broken out. These are *selections*, not prose.

Note what is absent: there is no third category for "text the model wrote".
A suitability record has no field a model may fill with prose, because every
sentence in one either quotes an approved disclosure or states a figure, and
both of those are sourced. If a future section seems to need free text, that is
a signal the section has not been decomposed into fields yet — not a signal to
add a ``free_text`` field.

WHY FROZEN
----------
:class:`DocumentState` is frozen, and edits go through :func:`apply_edit`,
which returns a NEW state and appends to the revision log. A mutable state
would make "what changed between version 3 and version 4" unanswerable, and
that question is the entire value of a document that a regulator may later ask
about.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

from docpkg.sources import Citation, Sourced

# ---------------------------------------------------------------------------
# The declared field set
# ---------------------------------------------------------------------------

FieldKind = Literal["sourced", "negotiated"]


@dataclass(frozen=True)
class FieldSpec:
    """What one document field IS, declared before any value exists.

    This is the schema half of ``memory.yml``: it says a field exists, what
    section it belongs to, whether it is sourced, and — crucially —
    ``llm_settable``, which is ``False`` for every sourced field and is checked
    by the tools that write state.
    """

    key: str
    label: str
    section: str
    kind: FieldKind
    #: False for every sourced field. The tool layer refuses a model-supplied
    #: value for these; see docpkg.edits.apply_edit.
    llm_settable: bool
    #: How the value is formatted into the document. Formatting is a property
    #: of the FIELD, not a choice made at render time, so the same value can
    #: never appear as "£486,210.44" in one section and "486210.44" in another.
    format: Literal["text", "money_gbp", "percent", "date", "integer", "quote"] = "text"
    #: Required fields are listed in the completeness report when absent.
    required: bool = True


#: Every field this document can contain. The renderer walks THIS, in order.
#: A field not declared here cannot appear in the document, and a field
#: declared here with no value appears as a blank with a reported gap.
FIELDS: tuple[FieldSpec, ...] = (
    # -- who and when --------------------------------------------------------
    FieldSpec("client_name", "Client", "Heading", "sourced", False, "text"),
    FieldSpec("portfolio_label", "Portfolio", "Heading", "sourced", False, "text"),
    FieldSpec("valuation_date", "Valuation date", "Heading", "sourced", False, "date"),
    # -- what they asked for -------------------------------------------------
    FieldSpec("objective", "Objective", "Objectives", "sourced", False, "text"),
    FieldSpec("time_horizon", "Time horizon (years)", "Objectives", "sourced", False, "integer"),
    FieldSpec("risk_profile", "Risk profile", "Objectives", "sourced", False, "text"),
    FieldSpec("capacity_for_loss", "Capacity for loss", "Objectives", "sourced", False, "text"),
    FieldSpec("knowledge_experience", "Knowledge and experience", "Objectives", "sourced", False, "text", required=False),
    # -- what they hold ------------------------------------------------------
    FieldSpec("total_value", "Total portfolio value", "Portfolio", "sourced", False, "money_gbp"),
    FieldSpec("cash_value", "Cash", "Portfolio", "sourced", False, "money_gbp"),
    FieldSpec("equities_value", "Global equities", "Portfolio", "sourced", False, "money_gbp"),
    FieldSpec("equities_weight", "Global equities weight", "Portfolio", "sourced", False, "percent"),
    FieldSpec("bonds_value", "Sterling corporate bonds", "Portfolio", "sourced", False, "money_gbp"),
    FieldSpec("bonds_weight", "Sterling corporate bonds weight", "Portfolio", "sourced", False, "percent"),
    FieldSpec("property_value", "Property funds", "Portfolio", "sourced", False, "money_gbp", required=False),
    FieldSpec("property_weight", "Property funds weight", "Portfolio", "sourced", False, "percent", required=False),
    # -- what it costs -------------------------------------------------------
    FieldSpec("ongoing_charge", "Ongoing charge", "Charges", "sourced", False, "percent"),
    FieldSpec("advice_fee", "Advice fee", "Charges", "sourced", False, "percent"),
    FieldSpec("charge_basis", "Basis", "Charges", "sourced", False, "text", required=False),
    # -- regulated wording, quoted ------------------------------------------
    FieldSpec("risk_warning", "Risk warning", "Disclosures", "sourced", False, "quote"),
    FieldSpec("charges_warning", "Charges", "Disclosures", "sourced", False, "quote"),
    FieldSpec("scope_note", "Scope", "Disclosures", "sourced", False, "quote", required=False),
    # -- the conversation's own choices -------------------------------------
    # The ONLY llm_settable fields, and note what they are: selections, not
    # prose. `addressed_to` picks between the client and their adviser;
    # `include_property_breakdown` is a yes/no the client makes in conversation.
    FieldSpec("addressed_to", "Addressed to", "Heading", "negotiated", True, "text", required=False),
    FieldSpec("include_property_breakdown", "Include property breakdown", "Portfolio", "negotiated", True, "text", required=False),
)

FIELDS_BY_KEY: dict[str, FieldSpec] = {spec.key: spec for spec in FIELDS}

#: Section order in the rendered document. Declared here rather than inferred
#: from FIELDS so that reordering fields never silently reorders the document.
SECTION_ORDER: tuple[str, ...] = ("Heading", "Objectives", "Portfolio", "Charges", "Disclosures")

#: Sections a model may not touch even through a negotiated field. Named in the
#: refusal messages so the limit is legible in the transcript, not just in code.
REGULATED_SECTIONS: frozenset[str] = frozenset({"Disclosures", "Charges"})


class UnknownField(Exception):
    """Raised when an edit names a field that is not declared in :data:`FIELDS`."""


# ---------------------------------------------------------------------------
# A revision
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Revision:
    """One entry in the append-only history.

    Records the field, what it was, what it became, and why. ``before`` and
    ``after`` are the rendered-ish values rather than the ``Sourced`` objects,
    because the history is read by humans asking "what changed" and a dataclass
    repr is not an answer to that question.
    """

    seq: int
    field_key: str
    before: str | None
    after: str | None
    reason: str


@dataclass(frozen=True)
class DocumentState:
    """The complete state of one document. The renderer's only input.

    ``values`` maps a declared field key to a :class:`Sourced`. A key absent
    from the mapping is a field with no value: it renders blank and is listed
    in the completeness report. There is no separate "deleted" marker, because
    absence already means exactly that — which is why deleting a field makes it
    vanish from the document with no other bookkeeping.
    """

    document_id: str
    template_id: str
    values: dict[str, Sourced] = field(default_factory=dict)
    revisions: tuple[Revision, ...] = ()

    def get(self, key: str) -> Sourced | None:
        return self.values.get(key)

    def spec(self, key: str) -> FieldSpec:
        if key not in FIELDS_BY_KEY:
            raise UnknownField(
                f"{key!r} is not a declared document field. Declared fields "
                f"are in docpkg.state.FIELDS."
            )
        return FIELDS_BY_KEY[key]

    def with_values(self, values: dict[str, Sourced], revisions: tuple[Revision, ...]) -> DocumentState:
        """Return a new state. Never mutates — see the module docstring."""
        return replace(self, values=values, revisions=revisions)

    def unsourced(self) -> tuple[str, ...]:
        """EVERY declared field with nothing to render, required or not.

        Optional fields are included deliberately. "Optional" says the document
        is still valid without the field; it does not say the reader should be
        left guessing whether the property holding is absent because the client
        has none or because nobody looked. A gap is reported either way, and the
        report marks which gaps are required ones.
        """
        out = []
        for spec in FIELDS:
            held = self.values.get(spec.key)
            if held is None or not held.is_present:
                out.append(spec.key)
        return tuple(out)

    def missing_required(self) -> tuple[str, ...]:
        """The subset of :meth:`unsourced` that the document cannot do without."""
        return tuple(key for key in self.unsourced() if FIELDS_BY_KEY[key].required)


def sourced(value: Any, source_id: str, record_id: str, field_name: str) -> Sourced:
    """Build a sourced value. The only sanctioned way to put one in state.

    A helper rather than a bare constructor call so that every value in the
    fixture builder reads as "this value, from this record" on one line — and
    so a future reviewer grepping for how values enter state finds one function
    rather than a scatter of constructors.
    """
    return Sourced(value=value, citation=Citation(source_id, record_id, field_name))
