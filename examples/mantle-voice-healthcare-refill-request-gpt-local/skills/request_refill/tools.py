"""Refill-request tools. The guard runs in lib.refills, not in the prompt.

The verified patient id and the selected record entry live in memory that
only these tools write (never ``llm_settable``). The model passes a name, a
date of birth, a medication name as the caller said it, a record id copied
from ``select_medication`` and the patient's words. No tool takes a dose, a
strength or a quantity, and none can approve anything.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import refills as cc

PATIENT_KEY = "project.verified_patient_id"
FIRST_NAME_KEY = "project.patient_first_name"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> cc.ClinicService:
    return cc.service_for(_conversation_id())


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


@tool(
    description=(
        "Verify the caller as a Cedar Clinic patient from their full name and date of "
        "birth, before any medication is looked up or requested. Pass the date as YYYY-MM-DD."
    )
)
async def verify_patient(full_name: str, date_of_birth: str, context: ToolContext = None) -> ToolResult:
    """Verify the patient.

    Args:
        full_name: The caller's first and last name as they said it.
        date_of_birth: Date of birth as YYYY-MM-DD, for example 1970-05-21.
    """
    result = cc.verify_patient(_service(), full_name, date_of_birth)
    if context is not None and result["status"] == "verified":
        # Mantle project memory is write-once, so a failed attempt writes
        # nothing and a call verified as one patient cannot become another.
        if not context.memory.get(PATIENT_KEY):
            context.memory.set(PATIENT_KEY, result["patient_id"])
            context.memory.set(FIRST_NAME_KEY, result["first_name"])
        elif context.memory.get(PATIENT_KEY) != result["patient_id"]:
            return ToolResult(llm_response={
                "status": "not_verified",
                "reason": "already_verified_as_another_patient",
                "next_step": "This call is verified for a different patient. Do not act for this one.",
            })
    public = {k: v for k, v in result.items() if k != "patient_id"}
    return ToolResult(llm_response=public)


@tool(
    description=(
        "Find the one medication on the verified patient's record that the caller wants a "
        "refill request for, from the name they said. Returns a record_id, or blocked when "
        "the name matches nothing, several entries, an inactive entry or a controlled medicine."
    )
)
async def select_medication(medication_name: str, context: ToolContext = None) -> ToolResult:
    """Select one recorded medication.

    Args:
        medication_name: The medicine as the caller named it, for example lisinopril or my blue inhaler.
    """
    result = cc.select_medication(_service(), _get(context, PATIENT_KEY), medication_name)
    if context is not None:
        # A new selection always replaces the old one, so a correction can
        # never leave the previous medicine confirmed.
        context.memory.set("selected_record_id", result.get("record_id", ""))
        context.memory.set("selected_medication_label", result.get("medication_label", ""))
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Send a refill request for the one medication returned by select_medication to the "
        "Cedar Clinic prescribing team for review. The engine reads the medication back and "
        "asks the caller to confirm first. Returns a request reference and the review status. "
        "It never approves, renews or changes a prescription, and takes no dose."
    )
)
async def send_refill_request(record_id: str, patient_note: str = "", context: ToolContext = None) -> ToolResult:
    """Send one refill request for review.

    Args:
        record_id: The record_id from select_medication, for example CC-RX-2041.
        patient_note: Anything the caller wants the prescribing team to know, in their words, one sentence. May be empty.
    """
    result = cc.send_refill_request(
        _service(),
        _get(context, PATIENT_KEY),
        _get(context, "selected_record_id"),
        record_id,
        patient_note,
        conversation_id=_conversation_id(),
    )
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Look up a refill request by its original submission_key after send_refill_request "
        "came back pending. Never sends anything."
    )
)
async def check_request_status(submission_key: str, context: ToolContext = None) -> ToolResult:
    """Look up a request.

    Args:
        submission_key: The submission_key from send_refill_request, for example CC-SUB-1A2B3C4D.
    """
    return ToolResult(llm_response=cc.check_request_status(_service(), _get(context, PATIENT_KEY), submission_key))


@tool(
    description=(
        "Pass a clinical question to the Cedar Clinic prescribing team: a different dose, a new "
        "medicine, a medicine that is no longer active, side effects. Returns a question reference. "
        "It never changes the prescription record and never gives advice."
    )
)
async def route_clinical_question(question: str, record_id: str = "", context: ToolContext = None) -> ToolResult:
    """Route a clinical question.

    Args:
        question: The caller's question in one sentence, for example wants to take 20 mg instead of 10 mg.
        record_id: The record_id it is about, if select_medication returned one. May be empty.
    """
    return ToolResult(
        llm_response=cc.route_clinical_question(
            _service(), _get(context, PATIENT_KEY), question, record_id or None, conversation_id=_conversation_id()
        )
    )
