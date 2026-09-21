"""Tools for the check_status skill.

``look_up_complaint`` is not here — the escalate skill needs it too, and a
skill cannot reach into another skill's local tools, so it lives in the shared
``tools/`` folder. Local unless genuinely shared is the rule; this is the one
place in the project that is genuinely shared.

This half of the line is the reason the project exists. Filing a complaint is
a form; a municipal line earns its keep when the number it handed out three
weeks ago still means something.
"""

from __future__ import annotations

import json

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import directory, store
from tools.civic import complaint_view, spoken_status


@tool(description="List the complaints filed from a phone number.")
async def list_my_complaints(phone: str = "", context: ToolContext = None) -> ToolResult:
    """Find complaints by phone number, for a caller without their reference.

    Args:
        phone: The number to search on. Required — there is no silent
            fallback to the number they are calling from.

    Caller ID is not consent. This used to default to the calling number, so
    anyone on that line got somebody's whole complaint history without asking
    for it and without being asked for anything. Offering the number and
    having it accepted takes one turn, and it is the difference between a
    convenience and a leak.
    """
    digits = directory.extract_phone(phone) if phone else ""
    if not digits:
        calling = str(context.memory.get("caller_phone") or "") if context else ""
        return ToolResult(llm_response={
            "ok": False,
            "error": "no_number",
            # Last four only. Enough for the caller to recognise their own
            # number, not enough to read a stranger's out loud.
            "calling_number_ends": calling[-4:] if len(calling) >= 4 else "",
            "hint": "Offer the number they are calling from, saying only the "
                    "last four digits, and pass it if they agree. Otherwise "
                    "ask which ten-digit number the complaint was filed on.",
        })

    rows = store.complaints_for_phone(digits)
    if context is not None:
        context.memory.set("complaint_options", json.dumps(
            [r["complaint_id"] for r in rows[:4]]))
    if not rows:
        return ToolResult(llm_response={"ok": True, "found": 0, "phone": digits})

    if len(rows) == 1:
        view = complaint_view(rows[0], context)
        if context is not None:
            await context.send(spoken_status(view))
        return ToolResult(llm_response={"ok": True, "found": 1,
                                        "already_read_out_to_the_caller": True,
                                        **view})

    return ToolResult(llm_response={
        "ok": True,
        "found": len(rows),
        "options": [
            {
                "number": i + 1,
                "say": (
                    f"{store.routing().get(r['category'], {}).get('spoken', r['category'])}"
                    f" in {r['locality']}, filed {r['created_on']}"
                ),
                "complaint_id": r["complaint_id"],
                "status": r["status_spoken"],
                "is_overdue": r["is_overdue"],
            }
            for i, r in enumerate(rows[:4])
        ],
    })


@tool(description="Pick one complaint from the list that was just read out.")
async def choose_complaint(choice: str = "", context: ToolContext = None) -> ToolResult:
    """Select a complaint by its position in the list.

    Args:
        choice: What the caller said — the option number, an ordinal like
            "the first one", or a plain "yes" when only one was offered.
    """
    if context is None:
        return ToolResult(llm_response={"ok": False, "error": "no_context"})

    try:
        options = json.loads(context.memory.get("complaint_options") or "[]")
    except (ValueError, TypeError):
        options = []
    if not isinstance(options, list):
        options = []
    from skills.report_problem.tools import _pick

    index = _pick(choice, len(options))
    if index < 0 or index >= len(options):
        return ToolResult(llm_response={"ok": False, "error": "no_such_option",
                                        "offered": len(options)})
    selected = store.get_complaint(options[index])
    if selected is None:
        return ToolResult(llm_response={"ok": False, "error": "not_found"})

    view = complaint_view(selected, context)
    await context.send(spoken_status(view))
    return ToolResult(llm_response={"ok": True,
                                    "already_read_out_to_the_caller": True,
                                    **view})
