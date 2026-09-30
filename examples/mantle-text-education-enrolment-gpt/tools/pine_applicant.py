"""Pine University tools shared by the enquiry skills: session binding, enquiry lookup, routing.

The chat runs in the signed-in applicant portal, so the session, not the
applicant's words, says whose records these are. The applicant id always
comes from project memory, which only ``load_applicant_profile`` writes. The
guard runs in lib.enrolment, not in the prompt; the model never supplies an
applicant id, a contract fact, a stage, a decision or a deadline.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import enrolment as pu

APPLICANT_KEY = "project.applicant_id"


def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> pu.Records:
    return pu.service_for(conversation_id())


def session_applicant_id(context: Optional[ToolContext]) -> Optional[str]:
    return (context.memory.get(APPLICANT_KEY) if context is not None else None) or None


async def send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    if not pu.TOOL_SENDS_RECEIPT or context is None:
        return
    text = pu.customer_receipt(service(), tool_name, result)
    if text:
        await context.send(text)


@tool(description="Load the signed-in applicant's profile into project memory at session start.")
async def load_applicant_profile(context: ToolContext = None) -> ToolResult:
    profile = pu.session_profile()
    if context is not None and not context.memory.get(APPLICANT_KEY):
        # Project memory is write-once on the pinned engine: set it once only.
        # Each value is one short field (Mantle cuts memory values at 100
        # characters in the prompt; see lib.enrolment.MEMORY_VALUE_LIMIT).
        context.memory.set(APPLICANT_KEY, profile["applicant_id"])
        context.memory.set("project.applicant_first_name", profile["first_name"])
        context.memory.set("project.application_list", profile["application_list"])
    return ToolResult(llm_response={"ok": True, "first_name": profile["first_name"],
                                    "applications": profile["applications"]})


@tool(
    description=(
        "Look up an enquiry already recorded for the applicant, by its support reference (PU-SUP-...) or the "
        "attempt_id (PU-ATT-...) record_enquiry returned. After a pending enquiry this finds the same one. "
        "Never records anything."
    )
)
async def check_enquiry(reference: str, context: ToolContext = None) -> ToolResult:
    """Look up an enquiry.

    Args:
        reference: A support reference such as PU-SUP-40A1C2, or an attempt_id such as PU-ATT-1A2B3C.
    """
    result = pu.check_enquiry(service(), session_applicant_id(context), reference)
    await send_receipt(context, "check_enquiry", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Pass one of the applicant's applications to its responsible team (admissions, financial aid, "
        "scholarships or registrar) when its records disagree, when the applicant record needs the team, or "
        "when the applicant asks for something only the team can decide, such as an extension. Returns a desk "
        "reference. Decides nothing and changes no deadline."
    )
)
async def route_to_team(reference: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Route to the responsible team.

    Args:
        reference: The application reference, for example SCH-26-0309.
        reason: One short sentence, for example portal and committee records disagree about the stage.
    """
    result = pu.route_to_team(service(), session_applicant_id(context), reference, reason, conversation_id())
    await send_receipt(context, "route_to_team", result)
    return ToolResult(llm_response=result)
