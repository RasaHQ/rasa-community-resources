"""Pre-visit intake tools. The guard runs in lib.intake, not in the prompt.

The signed-in patient is project memory that only the session tool writes.
The intake and its read-back values are skill memory that only these tools
write (never ``llm_settable``), so the intake the engine reads back for
confirmation is always the one the tools hold. Each value is one short field:
Mantle cuts a memory value at 100 characters in the prompt without saying so.

When ``lib.intake.TOOL_SENDS_RECEIPT`` is on, ``record_intake`` and
``assign_access_followup`` send the patient their outcome themselves through
``ToolContext.send``. The model's reply comes after it, whatever the model
does.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import intake as ci
from lib.conversation import conversation_from_events

PATIENT_KEY = "project.patient_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> ci.IntakeService:
    return ci.service_for(_conversation_id())


def _patient(context: Optional[ToolContext]) -> Optional[str]:
    return (context.memory.get(PATIENT_KEY) if context is not None else None) or None


def _write_memory(context: Optional[ToolContext], service: ci.IntakeService, intake: Optional[ci.Intake]) -> None:
    if context is None or intake is None:
        return
    for key, value in ci.memory_values(service, intake).items():
        context.memory.set(key, value)


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = ci.customer_receipt(tool_name, result) if ci.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(
    description=(
        "Open the patient's pre-visit intake for their upcoming visit, with the contact phone and insurance on the "
        "clinic's registration record. Nothing is recorded until record_intake."
    )
)
async def start_intake(context: ToolContext = None) -> ToolResult:
    """Open the intake from the details on file."""
    service = _service()
    result, intake = ci.start_intake(service, _patient(context), _conversation_id())
    _write_memory(context, service, intake)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Change a detail on the intake the patient told you has changed: phone, payer, member id or policyholder. "
        "A new payer or member id cancels the earlier eligibility result; check eligibility again."
    )
)
async def update_intake(
    intake_id: str,
    phone: Optional[str] = None,
    payer: Optional[str] = None,
    member_id: Optional[str] = None,
    policyholder: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Change the intake.

    Args:
        intake_id: The intake_id from start_intake, for example CC-IN-3F2A1.
        phone: The new contact phone number, as the patient gave it.
        payer: The insurance payer's name, as the patient gave it.
        member_id: The member id from the patient's insurance card, for example LHP-20417733.
        policyholder: "self", or the name of the person who holds the insurance.
    """
    service = _service()
    result, intake = ci.update_intake(service, _patient(context), intake_id, phone, payer, member_id, policyholder)
    _write_memory(context, service, intake)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Run the administrative eligibility check with the payer for the intake's current payer and member id. "
        "Returns the payer's response code and label. It is not a coverage or payment decision."
    )
)
async def check_eligibility(intake_id: str, context: ToolContext = None) -> ToolResult:
    """Check eligibility.

    Args:
        intake_id: The intake_id from start_intake.
    """
    service = _service()
    result, intake = ci.check_eligibility(service, _patient(context), intake_id)
    _write_memory(context, service, intake)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Assign the open insurance question from an eligibility result that is not active coverage to the patient "
        "access team. Returns a desk reference; it decides nothing and the visit stays booked."
    )
)
async def assign_access_followup(intake_id: str, question: str, context: ToolContext = None) -> ToolResult:
    """Assign the open question to the patient access owner.

    Args:
        intake_id: The intake_id from start_intake.
        question: One short sentence, for example payer could not confirm coverage for the visit.
    """
    service = _service()
    result, intake = ci.assign_access_followup(service, _patient(context), intake_id, question)
    _write_memory(context, service, intake)
    await _send_receipt(context, "assign_access_followup", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Record the confirmed pre-visit intake with its payer response and the owner of any open question. The "
        "engine reads the intake back and asks the patient to confirm first. Returns an intake reference."
    )
)
async def record_intake(intake_id: str, context: ToolContext = None) -> ToolResult:
    """Record one confirmed intake.

    Args:
        intake_id: The intake_id from start_intake.
    """
    memory = {key: (context.memory.get(key) if context is not None else None) or None for key in ci.MEMORY_KEYS}
    events = context.events if context is not None else []
    result = ci.record_intake(_service(), _patient(context), memory, conversation_from_events(events), intake_id)
    await _send_receipt(context, "record_intake", result)
    return ToolResult(llm_response=result)
