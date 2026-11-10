# concern: agent-logic
"""Refill-request tools: Mantle @tool bindings over the shared cedar_clinic API.

Every rule about records, matching and receipts runs in cedar_clinic, the
same code the LangGraph and Strands versions call. This file only binds it to
Mantle: the model-facing descriptions come from cedar_clinic.tools.TOOL_SPECS,
the conversation id is Mantle's sender id, and the state the framework keeps
(the verified patient, the selected record entry) lives in memory that only
these tools write. The regions marked refill-guard are that state handling
and the confirmation record; the engine half of the guard is the
tool_constraints block in skill.md.
"""

from __future__ import annotations

from typing import Optional

from cedar_clinic import tools as clinic
from cedar_clinic.tools import TOOL_SPECS
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

PATIENT_KEY = "project.verified_patient_id"
FIRST_NAME_KEY = "project.patient_first_name"


def _turn():
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context()
    except Exception:
        return None


def _conversation_id() -> str:
    turn = _turn()
    return turn.sender_id if turn is not None else "offline"


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


@tool(description=TOOL_SPECS["verify_patient"]["description"])
async def verify_patient(full_name: str, date_of_birth: str, context: ToolContext = None) -> ToolResult:
    """Verify the patient.

    Args:
        full_name: The caller's first and last name as they said it.
        date_of_birth: Date of birth as YYYY-MM-DD, for example 1970-05-21.
    """
    result = clinic.verify_patient(_conversation_id(), full_name, date_of_birth)
    # concern-begin: refill-guard
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
    # concern-end
    return ToolResult(llm_response=clinic.for_model(result))


@tool(description=TOOL_SPECS["select_medication"]["description"])
async def select_medication(medication_name: str, context: ToolContext = None) -> ToolResult:
    """Select one recorded medication.

    Args:
        medication_name: The medicine as the caller named it, for example lisinopril or my blue inhaler.
    """
    result = clinic.select_medication(_conversation_id(), _get(context, PATIENT_KEY), medication_name)
    # concern-begin: refill-guard
    if context is not None:
        # A new selection always replaces the old one, so a correction can
        # never leave the previous medicine confirmed or the gate open for it.
        context.memory.set("selected_record_id", result.get("record_id", ""))
        context.memory.set("selected_medication_label", result.get("medication_label", ""))
    # concern-end
    return ToolResult(llm_response=result)


@tool(description=TOOL_SPECS["send_refill_request"]["description"])
async def send_refill_request(record_id: str, patient_note: str = "", context: ToolContext = None) -> ToolResult:
    """Send one refill request for review.

    Args:
        record_id: The record_id from select_medication, for example CC-RX-2041.
        patient_note: Anything the caller wants the prescribing team to know, in their words, one sentence. May be empty.
    """
    conversation_id = _conversation_id()
    # concern-begin: refill-guard
    # Mantle runs this body only after the requires_confirmation gate in
    # skill.md paused the call, spoke the read-back question and resolved the
    # caller's answer on a later turn as yes. Record that answer with the
    # clinic, with the caller's words from this turn.
    turn = _turn()
    label = _get(context, "selected_medication_label") or ""
    clinic.record_confirmation(
        conversation_id, record_id, True,
        mechanism="rasa mantle requires_confirmation",
        question=clinic.confirmation_question(label) if label else None,
        answer=turn.turn.text if turn is not None else None,
    )
    # concern-end
    result = clinic.send_refill_request(
        conversation_id,
        _get(context, PATIENT_KEY),
        _get(context, "selected_record_id"),
        record_id,
        patient_note,
    )
    return ToolResult(llm_response=result)


@tool(description=TOOL_SPECS["check_request_status"]["description"])
async def check_request_status(submission_key: str, context: ToolContext = None) -> ToolResult:
    """Look up a request.

    Args:
        submission_key: The submission_key from send_refill_request, for example CC-SUB-1A2B3C4D.
    """
    return ToolResult(llm_response=clinic.check_request_status(
        _conversation_id(), _get(context, PATIENT_KEY), submission_key))


@tool(description=TOOL_SPECS["route_clinical_question"]["description"])
async def route_clinical_question(question: str, record_id: str = "", context: ToolContext = None) -> ToolResult:
    """Route a clinical question.

    Args:
        question: The caller's question in one sentence, for example wants to take 20 mg instead of 10 mg.
        record_id: The record_id it is about, if select_medication returned one. May be empty.
    """
    return ToolResult(llm_response=clinic.route_clinical_question(
        _conversation_id(), _get(context, PATIENT_KEY), question, record_id or None))
