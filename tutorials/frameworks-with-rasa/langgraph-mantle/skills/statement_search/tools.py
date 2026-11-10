"""Rasa exposes user inputs, not graph thread/account identifiers."""
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from statement_handoff.session import Session

SESSIONS = {}


def session():
    from rasa.mantle.orchestration.turn_context import current_turn_context
    sender = current_turn_context().sender_id
    return SESSIONS.setdefault(sender, Session())


@tool(description="Select a public synthetic demo code supplied by the user: 111111 or 222222. Not authentication.")
async def select_demo(code: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=session().choose_demo(code))


@tool(description="Start a new read-only LangGraph statement lookup for the current demo identity. The graph will ask for its missing month.")
async def start_statement_lookup(context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=await session().start())


@tool(description="Resume the current paused LangGraph lookup with the user's month in YYYY-MM format. Run identity stays application-owned.")
async def answer_statement_month(month: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=await session().resume(month))
