"""Expose existing tools without sharing Strands conversation history."""
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from network_specialist.handoff import NetworkSession
from network_specialist.local_runtime import create_specialist

SPECIALIST = create_specialist()
SESSIONS = {}

def session():
    from rasa.mantle.orchestration.turn_context import current_turn_context
    sender = current_turn_context().sender_id
    return SESSIONS.setdefault(sender, NetworkSession(SPECIALIST))

@tool(description="Select a public synthetic Juniper Mobile network area supplied by the user: north or south. Does not authenticate an account.")
async def select_network_area(area: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=session().select_area(area))

@tool(description="Inspect the selected area's synthetic network observation through the existing Strands tool. Supply only the user's question; cannot change subscriptions or call an arbitrary specialist tool.")
async def inspect_network_for_user(question: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=session().inspect(question))
