from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

CARDS = [
    {"id": "card_1", "ending": "5502", "kind": "debit"},
    {"id": "card_2", "ending": "5502", "kind": "credit"},
]


@tool(description="List the caller's cards: id, the last four digits and the kind.")
async def list_cards(context: ToolContext) -> ToolResult:
    return ToolResult(llm_response={"cards": CARDS})


@tool(description="Block exactly one card by its id. The caller cannot undo this without a branch visit.")
async def block_card(card_id: str, context: ToolContext) -> ToolResult:
    return ToolResult(llm_response={"blocked": card_id})
