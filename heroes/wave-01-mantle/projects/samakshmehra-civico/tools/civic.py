"""Tools shared across skills.

Only one lives here, because only one writes project-scope memory. Everything
else is owned by exactly one skill and lives in that skill's ``tools.py``.
"""

from __future__ import annotations

import os

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import directory, speech, store


@tool(description="Load the caller's details from the number they are calling from.")
async def load_caller(context: ToolContext = None) -> ToolResult:
    """Identify the caller from caller ID, before the first word is spoken.

    A real telephony channel hands the calling number to the session. The
    Inspector has no caller ID, so the demo number stands in for it — set
    ``CIVICO_DEMO_CALLER`` to an unknown number to hear the other path.

    Not being recognised is not an error. A civic line has no accounts, and
    most people who call one have never called it before.
    """
    phone = os.getenv("CIVICO_DEMO_CALLER", "9876543210")
    citizen = store.citizen_by_phone(phone)

    if context is not None:
        context.memory.set("caller_phone", phone)
        context.memory.set("known_caller", citizen is not None)
        context.memory.set("caller_name", citizen["name"] if citizen else "")
        context.memory.set("caller_id", citizen["citizen_id"] if citizen else "")

    if citizen is None:
        return ToolResult(llm_response={"known": False, "phone": phone})
    return ToolResult(llm_response={
        "known": True,
        "phone": phone,
        "name": citizen["name"],
        "first_name": citizen["name"].split()[0],
    })


def complaint_view(row: dict, context: ToolContext | None) -> dict:
    """The caller-facing view of a complaint row.

    Writes the three fields both check_status and escalate branch on, so the
    skill that called the lookup can gate on the answer without re-reading it.
    """
    if context is not None:
        context.memory.set("complaint_id", row["complaint_id"])
        context.memory.set("is_overdue", bool(row["is_overdue"]))
        context.memory.set("escalation_level", str(row["escalation_level"]))
    ward = directory.ward_by_id(row["ward_id"])
    return {
        "complaint_id": row["complaint_id"],
        "spoken_id": row["spoken_id"],
        "problem": store.routing().get(row["category"], {}).get("spoken", row["category"]),
        "where": f"{row['locality']} — {row['exact_spot']}" if row["exact_spot"] else row["locality"],
        "department": row["department"],
        "officer": ward["officer_name"] if ward else "",
        "status": row["status_spoken"],
        "filed_on": row["created_on"],
        "target_on": row["target_on"],
        # An ISO date read by a text-to-speech voice comes out as "two
        # thousand and twenty-six dash zero nine dash twelve".
        "target_spoken": speech.say_date(row["target_on"]),
        "days_left": row["days_left"],
        "days_overdue": row["days_overdue"],
        "is_overdue": row["is_overdue"],
        "is_open": row["is_open"],
        "escalation_level": row["escalation_level"],
        "resolution_note": row["resolution_note"],
    }


def spoken_status(view: dict) -> str:
    """The whole status of a complaint, as one spoken paragraph.

    Assembled here rather than left to an instruction, for the same reason the
    reference number is: these are the facts the caller rang up for, and a
    model asked to relay six fields will sometimes relay four, sometimes read
    an ISO date aloud, and sometimes announce that it is about to check.
    """
    lines = [
        f"That one is {view['problem']} at {view['where']}.",
        f"It is with {view['department']}"
        + (f", and the ward officer is {view['officer']}." if view["officer"] else "."),
    ]

    if not view["is_open"]:
        lines.append(f"It has been {view['status']}.")
        if view["resolution_note"]:
            lines.append(view["resolution_note"])
    elif view["is_overdue"]:
        # Said plainly. A caller whose complaint is late is owed the number,
        # not a softened version of it.
        lines.append(
            f"It is {view['status']}, and it is "
            f"{speech.say_days(view['days_overdue'])} past its target date."
        )
    else:
        lines.append(
            f"It is {view['status']}, and the target is "
            f"{view['target_spoken']} — {speech.say_days(view['days_left'])} from now."
        )
        # Said before it is asked. A caller told only "it is on time" and then
        # demanding escalation got "is there anything else I can help you
        # with?", because the skill had already finished. Answering the
        # question in advance is cheaper than handling it afterwards.
        lines.append(
            "It can be raised to the next authority once it is past that date, "
            "so call back then if nothing has happened."
        )
    return " ".join(lines)


@tool(description="Look up one complaint by its reference number.")
async def look_up_complaint(complaint_id: str, context: ToolContext = None) -> ToolResult:
    """Fetch a complaint the caller has the number for.

    Args:
        complaint_id: The reference, like CIV1002. Spoken letters and digits
            are fine — spacing and case are normalised here.
    """
    cleaned = speech.hear_reference(complaint_id)
    row = store.get_complaint(cleaned)
    if row is None:
        return ToolResult(llm_response={
            "ok": False,
            "error": "not_found",
            "heard": cleaned,
            "hint": "Read back what you heard and offer to look it up by phone number instead.",
        })

    view = complaint_view(row, context)
    if context is not None:
        await context.send(spoken_status(view))
    return ToolResult(llm_response={"ok": True,
                                    "already_read_out_to_the_caller": True,
                                    **view})


@tool(description="Raise a complaint to the next authority when it is past its deadline.")
async def escalate_complaint(complaint_id: str = "", context: ToolContext = None) -> ToolResult:
    """Move a complaint up one rung of the escalation ladder.

    Args:
        complaint_id: The reference to escalate. Leave empty to use the
            complaint already being discussed.

    Refuses on a complaint that is still within its target date. The clock,
    not the caller's frustration and not the model's judgement, decides
    whether escalation is available — that is what makes it mean something.
    """
    cleaned = speech.hear_reference(complaint_id)
    if not cleaned and context is not None:
        cleaned = context.memory.get("complaint_id") or ""
    if not cleaned:
        return ToolResult(llm_response={"ok": False, "error": "no_complaint",
                                        "hint": "Ask for the reference number."})

    row = store.get_complaint(cleaned)
    if row is None:
        return ToolResult(llm_response={"ok": False, "error": "not_found",
                                        "heard": cleaned})
    if not row["is_open"]:
        return ToolResult(llm_response={"ok": False, "error": "already_closed",
                                        "status": row["status_spoken"]})
    if not row["is_overdue"]:
        return ToolResult(llm_response={
            "ok": False,
            "error": "still_within_target",
            "days_left": row["days_left"],
            "target_on": row["target_on"],
        })

    updated = store.raise_escalation(row["complaint_id"])
    if updated.get("already_top"):
        return ToolResult(llm_response={
            "ok": False,
            "error": "already_at_top_level",
            "authority": updated["authority"],
            "authority_contact": updated["authority_contact"],
        })

    if context is not None:
        context.memory.set("escalated", True)
        context.memory.set("escalation_level", str(updated["escalation_level"]))
    # Spoken from the tool, for the same reason file_complaint is: the step
    # that calls it completes on `escalated`, which this tool writes, so the
    # model gets no dependable turn in which to say anything. Left to the
    # instruction the caller heard "Done." and never learned which authority
    # now held their complaint or when to expect an answer.
    await context.send(
        f"Done. It is now with the {updated['authority'].lower()}, and the new "
        f"date to expect an update by is {speech.say_date(updated['target_on'])}. "
        f"Your reference does not change — it is still {updated['spoken_id']}."
    )

    return ToolResult(llm_response={
        "ok": True,
        "already_read_out_to_the_caller": True,
        "complaint_id": updated["complaint_id"],
        "spoken_id": updated["spoken_id"],
        "level": updated["escalation_level"],
        "authority": updated["authority"],
        "authority_contact": updated["authority_contact"],
        "new_target_on": updated["target_on"],
        "new_target_spoken": speech.say_date(updated["target_on"]),
        "new_target_days": updated["days_left"],
    })
