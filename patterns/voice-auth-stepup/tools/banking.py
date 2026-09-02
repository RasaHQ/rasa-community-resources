"""The six demo actions, one per row of `authpolicy.actions.POLICIES`.

Every tool with a tier follows the same three-line shape, and the shape is the
pattern:

    try:
        require_tier("reissue_card", context)      # 1. resolve, at attempt time
    except StepUpRequired as exc:
        return _step_up(exc, context)              # 2. refuse, and say what is missing
    ...                                            # 3. only now, the side effect

Line 1 is before line 3. That ordering is the entire security property, and it
is checkable by reading the function — which is the reason the check is written
inline in each tool rather than hidden in a decorator. A decorator would be less
repetitive and would put the guard somewhere a reviewer skimming the diff of a
new tool would not see it.

Note what `_step_up` returns: `ok: False`, and no data. A refusal that returned
a partial result — the last four digits, the balance rounded to the nearest
hundred, "the card is already on its way" — would be a disclosure wearing a
denial's clothes.
"""

from __future__ import annotations

import logging

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from authpolicy import (
    AuthTier,
    StepUpRequired,
    factor_for,
    reason_for,
    require_tier,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixture data. One demo customer, no database, no network.
# ---------------------------------------------------------------------------

_CUSTOMER = {"name": "Sam Okafor", "account_id": "acc_4821", "label": "Everyday Checking"}

_BALANCE = "$3,182.44"

_RECENT_BILL = {
    "period": "August 2026",
    "amount": "$88.10",
    "due": "2026-09-14",
    "status": "unpaid",
}

_STORE_HOURS = [
    {"branch": "Northgate Central", "weekdays": "9am to 5pm", "saturday": "9am to 1pm"},
    {"branch": "Harbour Road", "weekdays": "10am to 4pm", "saturday": "closed"},
]

_FEES = [
    {"name": "Overdraft", "amount": "$28 per transaction, max 3 per day"},
    {"name": "Replacement card", "amount": "free once per year, then $12"},
    {"name": "International transfer", "amount": "$15 flat"},
]


def _step_up(exc: StepUpRequired, context: ToolContext | None) -> ToolResult:
    """Turn a refused attempt into a result the agent can act on conversationally.

    Records the pending action so the step-up skill knows what to resume, and
    names the factor so the agent asks the right question instead of guessing.

    The log line carries tiers and an action name. It never carries the factor
    the caller supplied — see `authpolicy.guard.redact` for why that is a rule
    rather than a preference on a voice channel.
    """
    logger.info(
        "step_up_required action=%s required=%s held=%s",
        exc.action,
        exc.required.value,
        exc.held.value,
    )
    if context is not None:
        context.memory.set("pending_action", exc.action)
        context.memory.set("pending_tier", exc.required.value)

    return ToolResult(
        llm_response={
            "ok": False,
            "step_up_required": True,
            "action": exc.action,
            "required_tier": exc.required.value,
            "held_tier": exc.held.value,
            "factor": factor_for(exc.required),
            "why": reason_for(exc.action),
            "hint": (
                "This action did NOT happen. Tell the caller what verification "
                "is still needed and help them complete it. Do not offer an "
                "alternative way to achieve the same outcome."
            ),
        }
    )


# ---------------------------------------------------------------------------
# LOW — no step-up. These deliberately do NOT call require_tier.
# ---------------------------------------------------------------------------
#
# Calling the guard here and having it pass would be harmless but dishonest: it
# would suggest low-tier actions are permitted *because* a check ran, when the
# truth is that no check is needed. An agent that challenges a caller for branch
# opening hours has misunderstood the pattern, and this absence is the example.


@tool(description="Return public branch opening hours. No verification needed.")
async def get_store_hours(context: ToolContext = None) -> ToolResult:
    """Public information. Anonymous callers get this."""
    return ToolResult(llm_response={"ok": True, "branches": _STORE_HOURS})


@tool(description="Return the public fee schedule. No verification needed.")
async def get_fee_schedule(context: ToolContext = None) -> ToolResult:
    """Public information, identical for every customer."""
    return ToolResult(llm_response={"ok": True, "fees": _FEES})


# ---------------------------------------------------------------------------
# MEDIUM — account-specific disclosure. Knowledge factor.
# ---------------------------------------------------------------------------


@tool(description="Return the caller's account balance. Requires verification.")
async def get_balance(context: ToolContext = None) -> ToolResult:
    """Disclose a balance, but only to a caller who reached MEDIUM."""
    try:
        require_tier("get_balance", context)
    except StepUpRequired as exc:
        return _step_up(exc, context)

    return ToolResult(
        llm_response={
            "ok": True,
            "account": _CUSTOMER["label"],
            "balance": _BALANCE,
        }
    )


@tool(description="Return the caller's most recent bill. Requires verification.")
async def get_recent_bill(context: ToolContext = None) -> ToolResult:
    """Disclose billing history, but only to a caller who reached MEDIUM."""
    try:
        require_tier("get_recent_bill", context)
    except StepUpRequired as exc:
        return _step_up(exc, context)

    return ToolResult(llm_response={"ok": True, "bill": _RECENT_BILL})


# ---------------------------------------------------------------------------
# HIGH — irreversible. Possession factor, then a human on failure.
# ---------------------------------------------------------------------------


@tool(
    description=(
        "Order a replacement card to a delivery address. Irreversible once "
        "posted. Requires the strongest verification."
    )
)
async def reissue_card(
    delivery_address: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Post a card to an address supplied during this call.

    The tool the whole pattern is built to protect. A caller holding MEDIUM —
    who correctly said the passphrase, who may well be the real customer —
    cannot reach the line that returns a dispatch reference. The guard runs
    before the address is even looked at.

    Args:
        delivery_address: Where to send the card. Free text in this demo.
    """
    try:
        require_tier("reissue_card", context)
    except StepUpRequired as exc:
        return _step_up(exc, context)

    return ToolResult(
        llm_response={
            "ok": True,
            "dispatched": True,
            "reference": "RC-70413",
            "delivery_address": delivery_address or "address on file",
            "eta": "five to seven business days",
        }
    )


@tool(
    description=(
        "Transfer funds out of the caller's account. Cannot be recalled. "
        "Requires the strongest verification."
    )
)
async def transfer_funds(
    amount: str = "",
    destination: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Move money out of the account.

    Args:
        amount: Amount to transfer, as the caller said it.
        destination: Where the money is going.
    """
    try:
        require_tier("transfer_funds", context)
    except StepUpRequired as exc:
        return _step_up(exc, context)

    return ToolResult(
        llm_response={
            "ok": True,
            "transferred": True,
            "reference": "TF-88205",
            "amount": amount or "unspecified",
            "destination": destination or "unspecified",
        }
    )
