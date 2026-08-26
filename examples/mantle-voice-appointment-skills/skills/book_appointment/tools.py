"""Tools only the book_appointment skill uses. Auto-discovered — no import_tools."""

from __future__ import annotations

from datetime import datetime

from lib.appointments import describe_slot, query_slots, slot_options, summarise_slots
from lib.database import Database, get_user_id, username_from_context
from lib.tool_helpers import set_memory
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult


@tool(description="Find bookable appointment slots that match the patient's preferences.")
async def query_available_slots(
    preferred_doctor: str = "any",
    start_date: str = "any",
    end_date: str = "any",
    start_time: str = "any",
    end_time: str = "any",
    context: ToolContext = None,
) -> ToolResult:
    """Search the clinic diary.

    Every argument accepts "any" when the patient has no preference.

    Args:
        preferred_doctor: Doctor the patient asked for, for example Patel.
        start_date: Earliest date to consider, in DD/MM/YYYY format.
        end_date: Latest date to consider, in DD/MM/YYYY format.
        start_time: Earliest time of day, in HH:MM 24-hour format.
        end_time: Latest time of day, in HH:MM 24-hour format.
    """
    slots = query_slots(
        preferred_doctor=preferred_doctor,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
    )

    set_memory(context, "slots_found", len(slots))
    if preferred_doctor and str(preferred_doctor).strip().lower() != "any":
        set_memory(context, "preferred_doctor", str(preferred_doctor).strip())

    if not slots:
        return ToolResult(
            llm_response={
                "ok": True,
                "slots": [],
                "slot_count": 0,
                "message": (
                    "No appointments are free in that window. Offer a wider date "
                    "range or a different time of day."
                ),
            }
        )

    return ToolResult(
        llm_response={
            "ok": True,
            "slots": slot_options(slots),
            "slot_count": len(slots),
            "preferred_doctor": preferred_doctor,
            "spoken_summary": summarise_slots(slots),
            "hint": "Read out two or three options, not the whole list.",
        }
    )


@tool(description="Book a confirmed appointment slot for the patient.")
async def confirm_appointment_booking(
    selected_slot: str,
    preferred_doctor: str = "any",
    visit_reason: str = "routine",
    context: ToolContext = None,
) -> ToolResult:
    """Write the appointment to the clinic diary.

    Args:
        selected_slot: The slot the patient chose, in DD/MM/YYYY HH:MM format.
        preferred_doctor: Doctor for the appointment, or "any".
        visit_reason: routine, urgent, or follow_up.
    """
    username = username_from_context(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "patient_not_found"})

    if not selected_slot:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "no_slot_selected",
                "hint": "Ask the patient to choose one of the offered times first.",
            }
        )

    doctor = (
        str(preferred_doctor).strip()
        if preferred_doctor and str(preferred_doctor).strip().lower() != "any"
        else "next available doctor"
    )
    reference = f"APT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    db.run_query(
        """
        INSERT INTO appointments (user_id, doctor, slot, visit_reason, status, reference)
        VALUES (?, ?, ?, ?, 'confirmed', ?)
        """,
        (user_id, doctor, selected_slot, visit_reason, reference),
        one_record=False,
    )
    db.commit()

    set_memory(context, "booked", True)
    set_memory(context, "selected_slot", selected_slot)
    set_memory(context, "booking_reference", reference)

    return ToolResult(
        llm_response={
            "ok": True,
            "reference": reference,
            "doctor": doctor,
            "slot": selected_slot,
            "spoken_slot": describe_slot(selected_slot),
            "visit_reason": visit_reason,
            "status": "confirmed",
        }
    )
