"""Cedar Clinic tools shared by the skills: session binding and the clinical route.

The chat runs for a signed-in patient, so the session, not the patient's
words, says whose intake this is. The patient id always comes from project
memory, which only ``load_session_patient`` writes. The clinical route returns
a contact and records nothing about the question.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import intake as ci

PATIENT_KEY = "project.patient_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


@tool(description="Load the signed-in patient's profile and upcoming visit into project memory at session start.")
async def load_session_patient(context: ToolContext = None) -> ToolResult:
    profile = ci.session_profile()
    if context is not None and not context.memory.get(PATIENT_KEY):
        # Project memory is write-once on the pinned engine: set it once only.
        # Each value is one short field (lib.intake.MEMORY_VALUE_LIMIT).
        context.memory.set(PATIENT_KEY, profile["patient_id"])
        context.memory.set("project.patient_first_name", profile["first_name"])
        context.memory.set("project.visit_summary", profile["visit_summary"])
    public = {k: v for k, v in profile.items() if k not in ("patient_id",)}
    return ToolResult(llm_response={"ok": True, **public})


@tool(
    description=(
        "Give the clinic's route for a clinical, symptom or medication question. This chat handles administrative "
        "intake only; the tool returns a contact and never advice."
    )
)
async def refer_clinical_question(topic: Optional[str] = None, context: ToolContext = None) -> ToolResult:
    """Clinical route.

    Args:
        topic: A few words naming the kind of question, for example medication before visit. Not stored.
    """
    return ToolResult(llm_response=ci.refer_clinical_question(ci.service_for(_conversation_id())))
