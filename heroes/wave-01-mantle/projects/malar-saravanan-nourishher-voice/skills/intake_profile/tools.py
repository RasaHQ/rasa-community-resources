"""Intake-profile skill tools — local to skills/intake_profile/."""

from __future__ import annotations

from rasa.mantle.memory.manager import ProjectMemoryAlreadySetError
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

_NOT_APPLICABLE = "not_applicable"


def _set_best_effort(context: ToolContext, entry: str, value: object) -> str:
    """Write one project field, tolerating an already-set field this session.

    Project fields are write-once per session (rasa-pro 3.20.0.dev4+) — a
    second intake_profile run in the same session (e.g. the person adds a
    condition later) can only fill in fields that are still unset. Returns
    "set" or "already_set" so the caller can report honestly on partial
    updates instead of the whole tool call failing.
    """
    try:
        context.memory.set(entry, value)
        return "set"
    except ProjectMemoryAlreadySetError:
        return "already_set"


@tool(description="Save the confirmed condition profile to project memory.")
async def save_health_profile(
    hypothyroidism_status: str,
    pcos_status: str,
    diabetes_status: str,
    fertility_status: str,
    takes_levothyroxine: bool,
    meds_list: str,
    allergies_list: str,
    context: ToolContext = None,
) -> ToolResult:
    """Persist the confirmed condition profile at project scope.

    Args:
        hypothyroidism_status: confirmed, suspected, or not_applicable.
        pcos_status: confirmed, suspected, or not_applicable.
        diabetes_status: confirmed, suspected, or not_applicable.
        fertility_status: trying_to_conceive, preconception_planning, or not_applicable.
        takes_levothyroxine: Whether the person takes levothyroxine or another thyroid hormone replacement.
        meds_list: Free-text list of medications/supplements.
        allergies_list: Free-text list of food allergies/intolerances.
    """
    outcomes: dict[str, str] = {}
    if context is not None:
        fields = {
            "has_hypothyroidism": hypothyroidism_status != _NOT_APPLICABLE,
            "hypothyroidism_status": hypothyroidism_status,
            "has_pcos": pcos_status != _NOT_APPLICABLE,
            "pcos_status": pcos_status,
            "has_type2_diabetes": diabetes_status != _NOT_APPLICABLE,
            "diabetes_status": diabetes_status,
            "has_fertility_focus": fertility_status != _NOT_APPLICABLE,
            "fertility_status": fertility_status,
            "takes_levothyroxine": bool(takes_levothyroxine),
            "meds_list": str(meds_list).strip(),
            "allergies_list": str(allergies_list).strip(),
        }
        for entry, value in fields.items():
            outcomes[entry] = _set_best_effort(context, entry, value)
        # Harmless no-op (via the same already-set tolerance) once this has
        # been set on an earlier call this session.
        _set_best_effort(context, "profile_intake_complete", True)

    already_set = [k for k, v in outcomes.items() if v == "already_set"]

    return ToolResult(
        llm_response={
            "ok": True,
            "hypothyroidism_status": hypothyroidism_status,
            "pcos_status": pcos_status,
            "diabetes_status": diabetes_status,
            "fertility_status": fertility_status,
            "takes_levothyroxine": bool(takes_levothyroxine),
            "fields_locked_from_earlier_this_session": already_set or None,
        }
    )
