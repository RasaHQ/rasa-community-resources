"""Shared meal tools for NourishHer — logging, history, plans, grocery lists.

All data is real and file-backed per sender id (see ``lib/store.py``). None
of these fabricate meals or nutrition facts: logs store exactly what the
person said, history reads back what was logged, and grocery lists derive
from a plan the person actually saved. Specific nutrient numbers always come
from the USDA tool (``tools/nutrition.py``), never from these functions.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Any, Dict, List

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import store


@tool(
    description=(
        "Log a meal the person describes, exactly as they said it. Store the "
        "description verbatim plus meal_type and confidence; never invent "
        "quantities or nutrition facts they did not give. Confirm what was "
        "logged afterwards."
    )
)
async def log_meal(
    description: str,
    meal_type: str = "unspecified",
    confidence: str = "medium",
    context: ToolContext = None,
) -> ToolResult:
    """Append a meal entry to the person's log.

    Args:
        description: The meal as the person described it, e.g. "two idlis,
            sambar, and coffee". Store approximate descriptions as given.
        meal_type: breakfast, lunch, dinner, snack, or unspecified.
        confidence: high, medium, or low — how complete/certain the
            description was (low for "a sandwich, not sure what was in it").
    """
    if context is not None and context.is_cancelled:
        return ToolResult(llm_response={"ok": False, "reason": "interrupted"})

    entry = store.append_log(
        store.user_id_from_context(context),
        {
            "kind": "meal",
            "description": str(description).strip(),
            "meal_type": str(meal_type).strip().lower() or "unspecified",
            "confidence": str(confidence).strip().lower() or "medium",
            "source": "voice",
        },
    )
    return ToolResult(llm_response={"ok": True, "logged": entry})


@tool(
    description=(
        "Log a symptom or how the person felt after a meal, in their own "
        "words. Use for check-ins like 'I felt sluggish after lunch'. Do not "
        "draw medical conclusions from it."
    )
)
async def log_symptom(entry_text: str, context: ToolContext = None) -> ToolResult:
    """Append a symptom/feeling note to the person's log.

    Args:
        entry_text: Short summary of the symptom or feeling, as described.
    """
    if context is not None and context.is_cancelled:
        return ToolResult(llm_response={"ok": False, "reason": "interrupted"})

    entry = store.append_log(
        store.user_id_from_context(context),
        {"kind": "symptom", "description": str(entry_text).strip()},
    )
    return ToolResult(llm_response={"ok": True, "logged": entry})


@tool(
    description=(
        "Retrieve the person's logged meals and symptoms over a recent window "
        "so you can answer 'what did I eat yesterday?' or summarize the week. "
        "Summarize only what is actually logged — do not infer medical "
        "conclusions."
    )
)
async def get_meal_history(range_days: int = 7, context: ToolContext = None) -> ToolResult:
    """Return logged entries from the last *range_days* days (default 7).

    Args:
        range_days: How many days back to include. Use 1 for "today",
            2 for "yesterday", 7 for "this week".
    """
    try:
        days = max(1, int(range_days))
    except (TypeError, ValueError):
        days = 7

    entries = store.read_log(store.user_id_from_context(context), since_days=days)
    meals = [e for e in entries if e.get("kind") == "meal"]
    symptoms = [e for e in entries if e.get("kind") == "symptom"]
    return ToolResult(
        llm_response={
            "ok": True,
            "range_days": days,
            "count": len(entries),
            "meals": meals,
            "symptoms": symptoms,
        }
    )


@tool(
    description=(
        "Return a cautious behavioral summary of logged history over a window "
        "(counts and simple observed patterns only — e.g. how many days "
        "breakfast was logged). Present observations tentatively; never turn a "
        "pattern into a medical conclusion."
    )
)
async def get_behavioral_summary(range_days: int = 7, context: ToolContext = None) -> ToolResult:
    """Return count-based observations over the last *range_days* days.

    Args:
        range_days: Days back to summarize (default 7).
    """
    try:
        days = max(1, int(range_days))
    except (TypeError, ValueError):
        days = 7

    entries = store.read_log(store.user_id_from_context(context), since_days=days)
    meals = [e for e in entries if e.get("kind") == "meal"]

    by_type: Dict[str, int] = {}
    days_seen: set[str] = set()
    for m in meals:
        by_type[m.get("meal_type", "unspecified")] = by_type.get(m.get("meal_type", "unspecified"), 0) + 1
        ts = m.get("timestamp", "")
        if ts:
            days_seen.add(ts[:10])

    return ToolResult(
        llm_response={
            "ok": True,
            "range_days": days,
            "total_meals_logged": len(meals),
            "distinct_days_with_a_log": len(days_seen),
            "meals_by_type": by_type,
            "symptom_notes_logged": len([e for e in entries if e.get("kind") == "symptom"]),
            "note": "Observations only. Do not infer medical conclusions from these counts.",
        }
    )


@tool(
    description=(
        "Save a meal plan the person accepted, keyed by date, so it can be "
        "recalled later and turned into a grocery list. Pass the meals as a "
        "short description per meal type."
    )
)
async def create_meal_plan(
    date: str,
    meals: str,
    context: ToolContext = None,
) -> ToolResult:
    """Persist an accepted meal plan for a date.

    Args:
        date: The plan's date in YYYY-MM-DD, or "today"/"tomorrow".
        meals: The agreed meals as text, e.g. "breakfast: oats with fruit;
            dinner: dal and rice".
    """
    resolved = str(date).strip().lower()
    if resolved in {"today", ""}:
        resolved = _date.today().isoformat()
    elif resolved == "tomorrow":
        from datetime import timedelta

        resolved = (_date.today() + timedelta(days=1)).isoformat()

    record = store.save_plan(
        store.user_id_from_context(context),
        resolved,
        {"meals": str(meals).strip()},
    )
    return ToolResult(llm_response={"ok": True, "date": resolved, "plan": record})


@tool(description="Retrieve a meal plan the person previously saved for a given date.")
async def get_saved_plan(date: str, context: ToolContext = None) -> ToolResult:
    """Return the saved plan for a date, or a not-found result.

    Args:
        date: The plan's date in YYYY-MM-DD, or "today"/"tomorrow".
    """
    resolved = str(date).strip().lower()
    if resolved in {"today", ""}:
        resolved = _date.today().isoformat()
    elif resolved == "tomorrow":
        from datetime import timedelta

        resolved = (_date.today() + timedelta(days=1)).isoformat()

    plan = store.get_plan(store.user_id_from_context(context), resolved)
    if plan is None:
        return ToolResult(llm_response={"ok": False, "error": "no_plan", "date": resolved})
    return ToolResult(llm_response={"ok": True, "date": resolved, "plan": plan})


@tool(
    description=(
        "Build a grocery list from a meal plan the person saved for a date. "
        "Reads the real saved plan; if none exists, returns not-found rather "
        "than inventing one."
    )
)
async def create_grocery_list(date: str, context: ToolContext = None) -> ToolResult:
    """Return the saved plan's meal text so a grocery list can be built from it.

    Args:
        date: The plan's date in YYYY-MM-DD, or "today"/"tomorrow".
    """
    resolved = str(date).strip().lower()
    if resolved in {"today", ""}:
        resolved = _date.today().isoformat()
    elif resolved == "tomorrow":
        from datetime import timedelta

        resolved = (_date.today() + timedelta(days=1)).isoformat()

    plan = store.get_plan(store.user_id_from_context(context), resolved)
    if plan is None:
        return ToolResult(llm_response={"ok": False, "error": "no_plan", "date": resolved})
    return ToolResult(
        llm_response={
            "ok": True,
            "date": resolved,
            "plan_meals": plan.get("meals", ""),
            "note": "Derive the grocery items from these planned meals only.",
        }
    )


@tool(
    description=(
        "Record that the person should be referred to a qualified professional "
        "(clinician, dietitian, pharmacist, or urgent care) and return a "
        "structured referral note. Use alongside a safety hand-off, never as "
        "medical advice itself."
    )
)
async def request_professional_referral(
    reason: str, referral_type: str = "clinician", context: ToolContext = None
) -> ToolResult:
    """Log a professional-referral event to the person's history.

    Args:
        reason: Short reason for the referral, e.g. "medication timing
            question" or "urgent symptom".
        referral_type: clinician, dietitian, pharmacist, or urgent_care.
    """
    entry = store.append_log(
        store.user_id_from_context(context),
        {
            "kind": "referral",
            "reason": str(reason).strip(),
            "referral_type": str(referral_type).strip().lower() or "clinician",
        },
    )
    return ToolResult(llm_response={"ok": True, "referral": entry})
