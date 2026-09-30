"""Reminder tools. The guard runs in lib.reminders, not in the prompt.

The patient is project memory that only the session tool writes. The latest
reminder's values are skill memory that only these tools write (never
``llm_settable``). Each value is one short field: Mantle cuts a memory value
at 100 characters in the prompt without saying so.

No tool takes a revision, a time the tools trust, a fact or an attendance
answer from the model. The model passes the patient's words for the
appointment and, if the patient named one, where to send; the tools read the
current revision from the booking system and the patient's answer from the
patient's own messages.

When ``lib.reminders.TOOL_SENDS_RECEIPT`` is on, the tools send the patient
their outcome themselves through ``ToolContext.send``: the reminder itself
(reference, current time and the contract's question), the attendance
receipt, or the change-request reference.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import reminders as cc
from lib.conversation import conversation_from_events

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


def _conversation(context: Optional[ToolContext]) -> cc.Conversation:
    return conversation_from_events(context.events) if context is not None else cc.Conversation()


def _write_memory(context: Optional[ToolContext], values: dict) -> None:
    if context is None:
        return
    for key, value in values.items():
        context.memory.set(key, value)


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = cc.customer_receipt(tool_name, result) if cc.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(
    description=(
        "Send the patient a reminder for one appointment by SMS to the confirmed number on file. The tool reads the "
        "appointment's current time from the booking system, sends at most one reminder per version of the "
        "booking, and sends the reminder text to the patient itself. It refuses a time from an earlier version, a "
        "second reminder for the same version, and any contact that is not confirmed."
    )
)
async def send_appointment_reminder(appointment: str, send_to: Optional[str] = None,
                                    context: ToolContext = None) -> ToolResult:
    """Send one appointment reminder.

    Args:
        appointment: The appointment as the patient named it, for example my follow-up with Dr Marr, or physio on
            Monday. Include a time or date only if the patient said one.
        send_to: Only if the patient asked for somewhere else, their words for it, for example 555-0188 or email.
            Leave empty for the number on file.
    """
    service = _service()
    result = cc.send_reminder(service, _patient(context), appointment, send_to)
    _write_memory(context, cc.memory_values(service, result))
    await _send_receipt(context, "send_appointment_reminder", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Record the patient's answer to a delivered reminder. The tool reads the answer from the patient's own "
        "latest message: a yes records attendance for the current version of the booking only; a change or a "
        "dispute records nothing. Delivery and attendance are kept separate."
    )
)
async def record_reminder_reply(reminder_reference: str, context: ToolContext = None) -> ToolResult:
    """Record the patient's reply to a reminder.

    Args:
        reminder_reference: The reminder reference, for example CC-RMD-E333CD, from a tool result.
    """
    service = _service()
    result = cc.record_reply(service, _patient(context), _conversation(context), reminder_reference)
    _write_memory(context, cc.memory_values(service, result))
    await _send_receipt(context, "record_reminder_reply", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Pass a request to change an appointment's time to the Cedar Clinic scheduling team, and pause that "
        "appointment's reminders until they confirm. Moves nothing itself; returns a change-request reference."
    )
)
async def request_appointment_change(appointment: str, requested_time: Optional[str] = None,
                                     reason: Optional[str] = None, context: ToolContext = None) -> ToolResult:
    """Request a change to one appointment.

    Args:
        appointment: The appointment as the patient named it, for example my follow-up with Dr Marr.
        requested_time: The time the patient asked for, in their words, if they gave one.
        reason: One short sentence, for example the patient cannot attend on Thursday.
    """
    service = _service()
    result = cc.request_change(service, _patient(context), _conversation_id(), appointment, requested_time, reason)
    _write_memory(context, cc.memory_values(service, result))
    await _send_receipt(context, "request_appointment_change", result)
    return ToolResult(llm_response=result)
