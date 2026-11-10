"""Transfer tools. The guard runs in lib.ledger, not in the prompt.

The selected payee and the current draft live in skill memory that only
these tools write (never ``llm_settable``), so the transfer the engine asks
the caller to confirm is always the draft the tool prepared. The model passes
the caller's words for a payee, an account name, an amount, and a
``payee_ref`` or ``draft_id`` copied from a tool result. No tool takes a
balance, a payee account number or a fact.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import ledger as nb


# Same helpers as tools/northgate_shared.py. Mantle loads each tool module on
# its own, so skill tools import only from lib/, never from tools/.
def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> nb.Ledger:
    return nb.ledger_for(conversation_id())


def session_customer_id(context: Optional[ToolContext]) -> str:
    """The customer bound to this signed-in session, from trusted project memory."""
    if context is None:
        return nb.DEMO_CUSTOMER_ID
    return context.memory.get("project.customer_id") or nb.DEMO_CUSTOMER_ID


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


def _set(context: Optional[ToolContext], **values: str) -> None:
    if context is not None:
        for key, value in values.items():
            context.memory.set(key, value)


@tool(
    description=(
        "Resolve who the caller wants to pay, from their own words (a saved payee's name or nickname, "
        "an account ending, or one of their own accounts), to exactly one destination. Returns a "
        "payee_ref, or blocked when several or none match."
    )
)
async def select_payee(payee: str, context: ToolContext = None) -> ToolResult:
    """Select the destination.

    Args:
        payee: The caller's words for the destination, as they said them, for example Sam, the one ending 42, my savings.
    """
    result = nb.select_payee(service(), session_customer_id(context), payee)
    # A new selection always replaces the old one and voids any draft, so a
    # correction can never leave an earlier destination confirmed.
    _set(
        context,
        selected_payee_ref=result.get("payee_ref", ""),
        selected_payee_label=result.get("payee_label", ""),
        draft_id="",
        draft_summary="",
    )
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Draft one transfer from one of the caller's accounts to the payee_ref select_payee returned. "
        "Reads the source balance from the ledger and returns a draft_id to submit. Moves no money."
    )
)
async def prepare_transfer(from_account: str, payee_ref: str, amount: str, context: ToolContext = None) -> ToolResult:
    """Prepare a transfer.

    Args:
        from_account: The caller's source account as they named it, for example everyday checking.
        payee_ref: The payee_ref from select_payee, for example NB-PAY-2042.
        amount: The amount in dollars, for example 75.00.
    """
    result = nb.prepare_transfer(
        service(),
        session_customer_id(context),
        _get(context, "selected_payee_ref"),
        from_account,
        payee_ref,
        amount,
        conversation_id(),
    )
    _set(context, draft_id=result.get("draft_id", ""), draft_summary=result.get("summary", ""))
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Submit the draft prepare_transfer returned, by its draft_id. The engine asks the caller to "
        "confirm first. The ledger decides at submission and returns a reference with ledger_status "
        "pending or posted, or blocked."
    )
)
async def submit_transfer(draft_id: str, context: ToolContext = None) -> ToolResult:
    """Submit a transfer.

    Args:
        draft_id: The draft_id from prepare_transfer, for example NB-DRF-1A2B3C4D.
    """
    result = nb.submit_transfer(
        service(),
        session_customer_id(context),
        _get(context, "selected_payee_ref"),
        _get(context, "draft_id"),
        draft_id,
        conversation_id(),
    )
    if result.get("status") == "blocked":
        # A refused draft cannot be confirmed again; the next one is new.
        _set(context, draft_id="", draft_summary="")
    return ToolResult(llm_response=result)
