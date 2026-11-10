"""Rasa collects the public type; the isolated native crew retains its tasks."""

import asyncio
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from crew_transport import CrewProcess, SOURCES

WORKER = CrewProcess()
SESSIONS = {}


def sender():
    from rasa.mantle.orchestration.turn_context import current_turn_context

    return current_turn_context().sender_id


@tool(
    description="Select the user's public synthetic HarborCover claim type: vehicle or travel. Does not authenticate an insurance account."
)
async def select_claim_type(claim_type: str, context: ToolContext = None) -> ToolResult:
    current = sender()
    if claim_type not in SOURCES:
        result = {"status": "unknown_claim_type"}
    elif current in SESSIONS and SESSIONS[current] != claim_type:
        result = {"status": "claim_type_changed"}
    else:
        SESSIONS[current] = claim_type
        result = {"status": "claim_type_selected"}
    return ToolResult(llm_response=result)


@tool(
    description="Run the existing isolated research crew and explain its checked claim-document result. Supply only the user's question; the application supplies the selected public type. Does not file or approve claims."
)
async def research_claim_documents(
    question: str, context: ToolContext = None
) -> ToolResult:
    selected = SESSIONS.get(sender())
    if selected is None:
        return ToolResult(llm_response={"status": "needs_claim_type"})
    return ToolResult(
        llm_response=await asyncio.to_thread(WORKER.checklist, selected, question)
    )
