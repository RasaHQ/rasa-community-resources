"""Shared Northgate Bank tools, used by more than one skill.

The customer id always comes from project memory, which load_caller_profile
writes at session start (the web-chat session is already signed in). The
model supplies an account name or a transfer reference; it never supplies a
customer id, a balance, a fact or an outcome.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import ledger as nb

CUSTOMER_KEY = "project.customer_id"


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
    return context.memory.get(CUSTOMER_KEY) or nb.DEMO_CUSTOMER_ID


@tool(description="Load the signed-in customer's profile into project memory at session start.")
async def load_caller_profile(context: ToolContext = None) -> ToolResult:
    profile = nb.caller_profile(ledger=service())
    if context is not None and not context.memory.get(CUSTOMER_KEY):
        # Project memory is write-once; the session is bound once, here.
        context.memory.set(CUSTOMER_KEY, profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
        context.memory.set("project.account_names", "; ".join(profile["accounts"]))
    return ToolResult(llm_response={"ok": True, "first_name": profile["first_name"], "accounts": profile["accounts"]})


@tool(
    description=(
        "Read one of the caller's account balances from the ledger: posted and available balance "
        "and the ledger revision. A read, not a reservation; it can change before a transfer."
    )
)
async def get_balance(account: str, context: ToolContext = None) -> ToolResult:
    """Read a balance.

    Args:
        account: The account as the caller named it, for example everyday checking or savings.
    """
    return ToolResult(llm_response=nb.get_balance(service(), session_customer_id(context), account))


@tool(
    description=(
        "Look up a transfer on the ledger by its reference (NB-TRF-...) or its attempt_id (NB-DRF-...). "
        "Returns pending, posted or unknown. Use before any retry; it never submits anything."
    )
)
async def check_transfer_status(reference_or_attempt_id: str, context: ToolContext = None) -> ToolResult:
    """Check a transfer.

    Args:
        reference_or_attempt_id: A transfer reference such as NB-TRF-7731, or an attempt_id from submit_transfer.
    """
    return ToolResult(
        llm_response=nb.check_transfer_status(service(), session_customer_id(context), reference_or_attempt_id)
    )


@tool(
    description=(
        "Hand a transfer whose ledger state is unknown or unconfirmed to the payments ledger team "
        "for reconciliation. Returns a reconciliation reference. Never creates a transfer."
    )
)
async def escalate_reconciliation(reference_or_attempt_id: str, note: str, context: ToolContext = None) -> ToolResult:
    """Escalate for reconciliation.

    Args:
        reference_or_attempt_id: The transfer reference or attempt_id.
        note: One short sentence, for example scheme has not reported the transfer state.
    """
    return ToolResult(
        llm_response=nb.escalate_reconciliation(service(), session_customer_id(context), reference_or_attempt_id, note)
    )
