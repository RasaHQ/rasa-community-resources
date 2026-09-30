"""Shared Horizon Rewards tools, used by more than one skill.

The member id and their verified account come from project memory, which
load_member_profile writes at session start from the signed-in web-chat
session. The model supplies only account numbers as the member said them and
references copied from tool results; it never supplies a member id, a fact or
an outcome.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import horizon as hz


def conversation_id() -> str:
    """The conversation this tool call belongs to, from Mantle's turn context."""
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> hz.RewardsService:
    return hz.service_for(conversation_id())


def session_member(context: Optional[ToolContext]) -> str:
    """The member bound to this session, from trusted project memory."""
    if context is None:
        return hz.DEMO_MEMBER_ID
    return context.memory.get("project.member_id") or hz.DEMO_MEMBER_ID


def session_account(context: Optional[ToolContext]) -> str:
    if context is None:
        return hz.member_profile(service())["rewards_account"]
    return context.memory.get("project.rewards_account") or ""


@tool(description="Load the signed-in member's profile into project memory at session start.")
async def load_member_profile(context: ToolContext = None) -> ToolResult:
    profile = hz.member_profile(service())
    if context is not None and not context.memory.get("project.member_id"):
        context.memory.set("project.member_id", profile["member_id"])
        context.memory.set("project.member_first_name", profile["first_name"])
        context.memory.set("project.rewards_account", profile["rewards_account"])
    return ToolResult(llm_response={"ok": True, **profile})


@tool(
    description=(
        "Read a Horizon Rewards account's points balance, the points reserved by "
        "an active hold, and any earlier redemption whose points and booking do "
        "not match. Only the member's own verified account can be read."
    )
)
async def get_points_balance(rewards_account: str, context: ToolContext = None) -> ToolResult:
    """Read a points balance.

    Args:
        rewards_account: The account number, for example HR-204417. Use the member's own account from memory unless they named another.
    """
    return ToolResult(llm_response=hz.points_balance(service(), session_member(context), rewards_account))


@tool(
    description=(
        "Look up an earlier redemption by its reference (HT-RD-...). Returns the "
        "points state, the booking state and any reversal, from the records."
    )
)
async def get_redemption_status(redemption_reference: str, context: ToolContext = None) -> ToolResult:
    """Look up a redemption.

    Args:
        redemption_reference: The redemption reference, for example HT-RD-58213.
    """
    return ToolResult(
        llm_response=hz.redemption_status(service(), session_member(context), redemption_reference)
    )


@tool(
    description=(
        "Send a redemption whose points and booking do not match to the Horizon "
        "Rewards desk, which reverses inconsistent records. Returns a desk case. "
        "Use it for any redemption that took points without a booking."
    )
)
async def request_rewards_desk_review(
    redemption_reference: str, note: str = "", context: ToolContext = None
) -> ToolResult:
    """Request a rewards desk review.

    Args:
        redemption_reference: The redemption with the mismatch, for example HT-RD-58213.
        note: One short sentence from the member, if they gave one.
    """
    return ToolResult(
        llm_response=hz.rewards_desk_review(service(), session_member(context), redemption_reference, note)
    )
