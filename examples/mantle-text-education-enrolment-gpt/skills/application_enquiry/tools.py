"""Application enquiry tools. The guard runs in lib.enrolment, not in the prompt.

The signed-in applicant is project memory that only the session tool writes.
The record the engine asks about is skill memory that only lookup_application
writes (never ``llm_settable``), so the enquiry the applicant confirms is
always on the record the tool resolved. Each value is one short field: Mantle
cuts a memory value at 100 characters in the prompt without saying so.

When ``lib.enrolment.TOOL_SENDS_RECEIPT`` is on, ``record_enquiry`` sends the
applicant its outcome itself through ``ToolContext.send``: the support
reference, the team, the stage, the decision status and the deadlines, or
"not recorded yet". The model's reply comes after it, whatever the model does.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import enrolment as pu

APPLICANT_KEY = "project.applicant_id"


# Same helpers as tools/pine_applicant.py. Mantle loads each tool module on its
# own, so skill tools import only from lib/, never from tools/.
def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> pu.Records:
    return pu.service_for(_conversation_id())


def _applicant(context: Optional[ToolContext]) -> Optional[str]:
    return (context.memory.get(APPLICANT_KEY) if context is not None else None) or None


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    if not pu.TOOL_SENDS_RECEIPT or context is None:
        return
    text = pu.customer_receipt(_service(), tool_name, result)
    if text:
        await context.send(text)


@tool(
    description=(
        "Look up one of the signed-in applicant's applications (admission, financial aid, scholarship or "
        "enrolment) by its reference or the applicant's words for it. Returns its stage, any decision the "
        "responsible team has issued, outstanding evidence and deadlines from the authoritative record. "
        "Read only."
    )
)
async def lookup_application(reference_or_form: str, context: ToolContext = None) -> ToolResult:
    """Look up an application.

    Args:
        reference_or_form: The reference the applicant gave, for example AID-26-1182, or their words for the form, for example my financial aid application.
    """
    service = _service()
    result, selected = pu.lookup_application(service, _applicant(context), reference_or_form)
    if context is not None:
        # A new lookup always replaces the record the engine will ask about; a
        # record that cannot be resolved clears it, which hides record_enquiry.
        for key, value in pu.memory_values(service, selected).items():
            context.memory.set(key, value)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Record the applicant's enquiry with the team responsible for the application lookup_application "
        "returned. The engine asks the applicant first. Returns a support reference and the team, or pending "
        "when the team's queue has not acknowledged it. Records no decision and changes no deadline."
    )
)
async def record_enquiry(application_reference: str, topic: str, question: str, context: ToolContext = None) -> ToolResult:
    """Record one enquiry.

    Args:
        application_reference: The reference from lookup_application, for example AID-26-1182.
        topic: One of missing_evidence, deadline, decision_timing, decision_question, enrolment_step, other.
        question: The applicant's question in their own words, one or two sentences.
    """
    selected = (context.memory.get("enquiry_ref") if context is not None else None) or None
    result = pu.record_enquiry(_service(), _applicant(context), selected, application_reference, topic, question,
                               _conversation_id())
    await _send_receipt(context, "record_enquiry", result)
    return ToolResult(llm_response=result)
