"""Mantle owns the conversation; the researcher receives only a read snapshot."""
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from bank_research.casework import CaseSession
from bank_research.bridge import investigate

# Process-local tutorial state; bounded to localhost demonstration sessions.
# A production service needs trusted identity, durable storage and eviction.
SESSIONS = {}


def session():
    from rasa.mantle.orchestration.turn_context import current_turn_context
    key = current_turn_context().sender_id
    return SESSIONS.setdefault(key, CaseSession())


@tool(description="Select a published synthetic demo identity using code 111111 or 222222; not real authentication.")
async def select_demo_identity(code: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=session().verify_demo(code))


@tool(description="Select TX-101 or TX-102 for demo A, or TX-201 for demo B. A correction invalidates any earlier review proposal.")
async def select_charge(transaction_id: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=session().select(transaction_id))


@tool(description="Use Deep Agents to research only the selected synthetic charge. This cannot submit a review or decide fraud or a refund.")
async def research_charge(context: ToolContext = None) -> ToolResult:
    try:
        evidence = session().evidence()
    except ValueError:
        return ToolResult(llm_response={"error": "no_selected_transaction"})
    current = session()
    revision = current.revision
    result = await investigate(evidence)
    if current.revision != revision:
        result = {"error": "selection_changed_during_research"}
    return ToolResult(llm_response=result)


@tool(description="Prepare staff review for the selected charge, returning a proposal_id and exact merchant, amount and date for readback.")
async def prepare_review(context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=session().prepare())


@tool(description="Record staff review for the current proposal only. Confirm its exact charge with the caller before execution. This records an in-memory demo request, never a refund.")
async def submit_review(proposal_id: str, merchant: str, amount: str, currency: str, date: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=session().submit(proposal_id, merchant, amount, currency, date))
