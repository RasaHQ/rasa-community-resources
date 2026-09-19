"""Shared profile tools for NourishHer — real file-backed persistence.

These read and write the rich, freely-mutable user profile stored per
sender id in ``data/profiles/`` (see ``lib/store.py``). Condition *flags*
that gate skills stay in project memory (written by
``skills/intake_profile/tools.py``); everything a person can casually add,
change, or delete — cuisine, likes/dislikes, cooking time, budget, goals —
lives here so it can be updated any number of times per session.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import store


@tool(
    description=(
        "Retrieve the person's stored nutrition profile (name, age range, "
        "region/cuisine, dietary pattern, likes, dislikes, allergies, cooking "
        "time, budget, goals, and any health context they volunteered). Call "
        "this before giving personalized meal guidance so suggestions match "
        "what they've actually told you — never invent preferences."
    )
)
async def get_user_profile(context: ToolContext = None) -> ToolResult:
    """Return the person's stored profile document (empty if none yet)."""
    profile = store.load_profile(store.user_id_from_context(context))
    return ToolResult(llm_response={"ok": True, "profile": profile, "has_profile": bool(profile)})


@tool(
    description=(
        "Add or change one field of the person's nutrition profile. Valid "
        "fields: name, age_range, region, diet, allergies, likes, dislikes, "
        "cooking_frequency, cooking_time_weekdays_minutes, meal_schedule, "
        "budget, goals, health_context, clinician_constraints. For list fields "
        "(allergies, likes, dislikes, goals, health_context, "
        "clinician_constraints) the value is appended; other fields are "
        "overwritten. Confirm high-impact changes back to the person."
    )
)
async def update_user_profile(field: str, value: str, context: ToolContext = None) -> ToolResult:
    """Set or append one profile field.

    Args:
        field: The profile field to update (see the tool description for the
            allowed set).
        value: The value to store. For list fields it is appended; comma-
            separated values are split into multiple list items.
    """
    field = str(field).strip()
    if field not in store.PROFILE_FIELDS:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "unknown_field",
                "field": field,
                "allowed": sorted(store.PROFILE_FIELDS),
            }
        )

    stored_value: object = value
    if field in store.LIST_FIELDS and isinstance(value, str) and "," in value:
        stored_value = [v.strip() for v in value.split(",") if v.strip()]

    try:
        profile = store.set_profile_field(store.user_id_from_context(context), field, stored_value)
    except KeyError:
        return ToolResult(llm_response={"ok": False, "error": "unknown_field", "field": field})

    return ToolResult(llm_response={"ok": True, "field": field, "profile": profile})


@tool(
    description=(
        "Remove a profile field entirely, or remove one item from a list field "
        "(pass the item as value). Use when the person says to forget or delete "
        "a preference, e.g. 'I'm not vegetarian anymore' or 'remove mushrooms "
        "from my dislikes'."
    )
)
async def delete_user_profile(
    field: str, value: str = None, context: ToolContext = None
) -> ToolResult:
    """Delete a profile field, or one item from a list field.

    Args:
        field: The profile field to modify.
        value: Optional. For a list field, the single item to remove; omit to
            clear the whole field.
    """
    field = str(field).strip()
    if field not in store.PROFILE_FIELDS:
        return ToolResult(
            llm_response={"ok": False, "error": "unknown_field", "field": field}
        )
    profile = store.delete_profile_field(store.user_id_from_context(context), field, value)
    return ToolResult(llm_response={"ok": True, "field": field, "removed": value, "profile": profile})
