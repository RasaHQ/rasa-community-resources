"""A worked state, built the way a real conversation would build it.

Every field here is set through :mod:`docpkg.edits` — the same functions the
agent's tools call — rather than by constructing a state literal. That is on
purpose and it is the same lesson `voice-handoff-context` learned the hard way:
a fixture that assembles its own convenient object tests the fixture, not the
path that runs. If a rule in ``edits.py`` tightened tomorrow, this builder would
start failing, which is the correct outcome.

Note what is deliberately NOT set: ``property_value`` and ``property_weight``
are left unsourced, so the shipped document has real blanks in it. A demo where
every field happens to be populated cannot show what the blank rule does, and
the blank rule is half the point.
"""

from __future__ import annotations

from docpkg.edits import set_negotiated_field, set_sourced_field
from docpkg.state import DocumentState

#: (field_key, source_id, record_id, record_field)
_SOURCED: tuple[tuple[str, str, str, str], ...] = (
    ("client_name", "custodian-extract", "CL-77301", "legal_name"),
    ("portfolio_label", "custodian-extract", "CL-77301", "portfolio_label"),
    ("valuation_date", "custodian-extract", "VAL-2026-08-29-PF4402", "as_of"),
    ("objective", "advice-factfind", "FF-77301-OBJ", "value"),
    ("time_horizon", "advice-factfind", "FF-77301-HZN", "value"),
    ("risk_profile", "advice-factfind", "FF-77301-RSK", "value"),
    ("capacity_for_loss", "advice-factfind", "FF-77301-CAP", "value"),
    ("knowledge_experience", "advice-factfind", "FF-77301-KNW", "value"),
    ("total_value", "custodian-extract", "VAL-2026-08-29-PF4402", "total_value_gbp"),
    ("cash_value", "custodian-extract", "VAL-2026-08-29-PF4402", "cash_gbp"),
    ("equities_value", "custodian-extract", "POS-PF4402-001", "value_gbp"),
    ("equities_weight", "custodian-extract", "POS-PF4402-001", "weight_pct"),
    ("bonds_value", "custodian-extract", "POS-PF4402-002", "value_gbp"),
    ("bonds_weight", "custodian-extract", "POS-PF4402-002", "weight_pct"),
    ("ongoing_charge", "custodian-extract", "CHG-PF4402-2026", "ongoing_charge_pct"),
    ("advice_fee", "custodian-extract", "CHG-PF4402-2026", "advice_fee_pct"),
    ("charge_basis", "custodian-extract", "CHG-PF4402-2026", "basis"),
    ("risk_warning", "disclosure-library", "DISC-RISK-001", "text"),
    ("charges_warning", "disclosure-library", "DISC-CHARGE-002", "text"),
    ("scope_note", "disclosure-library", "DISC-SCOPE-004", "text"),
)


def build_fixture_state(document_id: str = "DOC-SUIT-00417") -> DocumentState:
    """The demo document's state, assembled through the real edit path."""
    state = DocumentState(document_id=document_id, template_id="suitability-record-v1")
    for field_key, source_id, record_id, record_field in _SOURCED:
        state = set_sourced_field(
            state,
            field_key,
            source_id=source_id,
            record_id=record_id,
            record_field=record_field,
            reason="initial population from source records",
        ).state
    state = set_negotiated_field(
        state,
        "addressed_to",
        value="client_and_adviser",
        reason="client asked for their adviser to be copied",
    ).state
    return state
