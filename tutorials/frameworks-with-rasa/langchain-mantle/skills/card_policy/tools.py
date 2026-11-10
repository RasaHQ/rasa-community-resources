"""The model supplies a question; the application owns document scope."""
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from policy_worker.handoff import PolicySession

SESSIONS = {}

def session():
    from rasa.mantle.orchestration.turn_context import current_turn_context
    sender = current_turn_context().sender_id
    return SESSIONS.setdefault(sender, PolicySession())

@tool(description="Select the public synthetic policy demo supplied by the user: 111111 personal or 222222 business. Not authentication.")
async def select_policy_demo(code: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=session().select_demo(code))

@tool(description="Retrieve quoted synthetic card-policy sources for the current demo. Only the user's question is an argument; the application chooses document scope. Does not replace a card or execute an account action.")
async def retrieve_card_policy(question: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=session().retrieve(question))
