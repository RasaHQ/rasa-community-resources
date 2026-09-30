"""Transaction-search tools. The guard runs in lib.history, not in the prompt.

The model passes the caller's words for the period, the statuses, an account
and a merchant, or a search_ref copied from a tool result. The tool reads the
caller's own messages from the tracker to check that the period and statuses
are theirs. No tool takes a date range, a fact, a customer id or a total.

When ``lib.history.TOOL_SENDS_RECEIPT`` is on, each issued result is sent to
the customer by the tool itself through ``ToolContext.send``: the search
reference, range, statuses and whether the result is complete. The model's
reply comes after it, whatever the model does.

The last search is kept in skill memory that only these tools write (never
``llm_settable``), one short field per value: Mantle cuts a memory value at
100 characters in the prompt without saying so.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import history as nb
from lib.conversation import caller_texts

CUSTOMER_KEY = "project.customer_id"


# Same helpers as tools/northgate_history.py. Mantle loads each tool module on
# its own, so skill tools import only from lib/, never from tools/.
def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> nb.HistoryService:
    return nb.service_for(conversation_id())


def session_customer_id(context: Optional[ToolContext]) -> str:
    """The customer bound to this signed-in session, from trusted project memory."""
    if context is None:
        return nb.SESSION_CUSTOMER_ID
    return context.memory.get(CUSTOMER_KEY) or nb.SESSION_CUSTOMER_ID


async def deliver(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    if context is None:
        return
    for key, value in nb.memory_values(result).items():
        context.memory.set(key, value)
    text = nb.customer_receipt(tool_name, result) if nb.TOOL_SENDS_RECEIPT else None
    if text:
        await context.send(text)


@tool(
    description=(
        "Search the signed-in customer's transaction history. Pass the caller's own words for the period and for "
        "which transactions to include (posted, pending or both), and the account and merchant if they named them. "
        "Returns a search result with a reference, the exact date range, the statuses and whether it is complete, "
        "or blocked with the questions to ask the caller."
    )
)
async def search_transactions(
    period: str,
    statuses: str,
    account: Optional[str] = None,
    merchant: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Search transactions.

    Args:
        period: The caller's words for the dates, for example March 2026, last month, March last year, 3 to 17 March 2026.
        statuses: The caller's words for which transactions, for example posted only, including pending, both. Empty if they have not said.
        account: The account as the caller named it, for example everyday checking or rewards card. Empty for all accounts.
        merchant: A merchant the caller named, for example Acme Hardware. Empty for all merchants.
    """
    texts = caller_texts(context.events) if context is not None else [period, statuses]
    result = nb.search_transactions(
        service(), session_customer_id(context), texts, period, statuses, account, merchant, conversation_id()
    )
    await deliver(context, "search_transactions", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Read the rest of a partial search, by the search_ref search_transactions returned. Same range, statuses, "
        "account and merchant as that search; for anything different call search_transactions."
    )
)
async def continue_search(search_ref: str, context: ToolContext = None) -> ToolResult:
    """Continue a partial search.

    Args:
        search_ref: The search_ref of a partial result, for example NB-SRCH-1A2B3C4D.
    """
    result = nb.continue_search(service(), session_customer_id(context), search_ref)
    await deliver(context, "continue_search", result)
    return ToolResult(llm_response=result)
