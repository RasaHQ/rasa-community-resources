"""Cedar Clinic tools shared by the reminder skill: session binding, bookings, the delivery ledger.

The SMS thread belongs to a patient whose number is on file, so the session,
not the patient's words, says whose appointments these are. The patient id
always comes from project memory, which only ``load_patient_profile`` writes.
The guard runs in lib.reminders, not in the prompt.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import reminders as cc

PATIENT_KEY = "project.patient_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> cc.ReminderService:
    return cc.service_for(_conversation_id())


def _patient(context: Optional[ToolContext]) -> str:
    return (context.memory.get(PATIENT_KEY) if context is not None else None) or cc.SESSION_PATIENT_ID


def _write_memory(context: Optional[ToolContext], values: dict) -> None:
    if context is None:
        return
    for key, value in values.items():
        context.memory.set(key, value)


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = cc.customer_receipt(tool_name, result) if cc.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(description="Load the patient this SMS thread belongs to into project memory at session start.")
async def load_patient_profile(context: ToolContext = None) -> ToolResult:
    profile = cc.patient_profile(_service())
    if context is not None and not context.memory.get(PATIENT_KEY):
        # Project memory is write-once on the pinned engine: set it once only.
        # Each value is one short field (MEMORY_VALUE_LIMIT).
        context.memory.set(PATIENT_KEY, profile["patient_id"])
        context.memory.set("project.patient_first_name", profile["first_name"])
        context.memory.set("project.sms_on_file", profile["sms_on_file"])
        context.memory.set("project.today", profile["today"])
    public = {k: v for k, v in profile.items() if k != "patient_id"}
    return ToolResult(llm_response={"ok": True, **public})


@tool(
    description=(
        "List the patient's upcoming appointments as the booking system holds them now: the current time of each, "
        "any earlier versions that were moved, the reminders on the ledger by version with their delivery state, "
        "and attendance. Changes nothing and sends nothing."
    )
)
async def list_appointments(context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=cc.list_appointments(_service(), _patient(context)))


@tool(
    description=(
        "Query one appointment's reminder ledger by version, with a reminder reference (CC-RMD-...) or the "
        "appointment in the patient's words. Reconciles a reminder whose delivery was not acknowledged. Sends no "
        "reminder."
    )
)
async def check_reminder_delivery(reference: str, context: ToolContext = None) -> ToolResult:
    """Query the reminder ledger for one appointment.

    Args:
        reference: A reminder reference such as CC-RMD-4E6F6B, or the appointment as the patient named it.
    """
    service = _service()
    result = cc.check_delivery(service, _patient(context), reference)
    _write_memory(context, cc.memory_values(service, result))
    await _send_receipt(context, "check_reminder_delivery", result)
    return ToolResult(llm_response=result)
