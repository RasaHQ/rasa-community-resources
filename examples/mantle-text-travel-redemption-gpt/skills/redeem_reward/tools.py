"""Redemption tools. The guard runs in lib.horizon, not in the prompt.

The hold the engine asks the member to confirm lives in skill memory that only
these tools write (never ``llm_settable``): hold_reward sets it, release_hold
and a committed redemption clear it. redeem_reward is withheld from the model
while no hold is set, and the tool itself checks that the hold it is given is
that confirmed hold.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import horizon as hz

HELD_KEYS = ("held_hold_id", "held_reward_label", "held_points", "held_account")


# The same three helpers as tools/horizon_shared.py. Skill tool modules import
# lib/, not each other, so each module carries its own copy.
def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> hz.RewardsService:
    return hz.service_for(conversation_id())


def session_member(context: Optional[ToolContext]) -> str:
    if context is None:
        return hz.DEMO_MEMBER_ID
    return context.memory.get("project.member_id") or hz.DEMO_MEMBER_ID


def session_account(context: Optional[ToolContext]) -> str:
    if context is None:
        return hz.member_profile(service())["rewards_account"]
    return context.memory.get("project.rewards_account") or ""


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


def _set_held(context: Optional[ToolContext], values: dict[str, str]) -> None:
    if context is None:
        return
    for key in HELD_KEYS:
        context.memory.set(key, values.get(key, ""))


@tool(
    description=(
        "Search Horizon Rewards flights and hotel stays bookable with points, by "
        "destination and, if the member gave one, travel date. Results show "
        "points prices; they are not holds."
    )
)
async def search_reward_options(
    destination: str, travel_date: Optional[str] = None, context: ToolContext = None
) -> ToolResult:
    """Search reward options.

    Args:
        destination: City or airport the member named, for example Lisbon.
        travel_date: Travel date as YYYY-MM-DD, only if the member gave one.
    """
    return ToolResult(llm_response=hz.search_options(service(), destination, travel_date))


@tool(
    description=(
        "Hold one reward option's inventory and reserve its points together, "
        "before any redemption. Only one reward can be held at a time. Returns a "
        "hold_id and the points, or why nothing was held."
    )
)
async def hold_reward(option_id: str, rewards_account: str, context: ToolContext = None) -> ToolResult:
    """Hold a reward.

    Args:
        option_id: The option_id from search_reward_options, for example RW-LIS-1014.
        rewards_account: The account the points come from. The member's own account from memory, unless they named another number.
    """
    result = hz.hold_reward(
        service(), session_member(context), rewards_account, option_id, conversation_id()
    )
    if result["status"] == "held":
        # A new hold always replaces what the confirmation will read, so the
        # member confirms the current reward and the current points.
        _set_held(context, {
            "held_hold_id": result["hold_id"],
            "held_reward_label": result["reward"],
            "held_points": hz.points_text(result["points"]),
            "held_account": result["rewards_account"],
        })
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Release an active hold without redeeming it: the inventory and the "
        "reserved points go back. Use when the member switches reward or no "
        "longer wants it."
    )
)
async def release_hold(hold_id: str, context: ToolContext = None) -> ToolResult:
    """Release a hold.

    Args:
        hold_id: The hold_id from hold_reward, for example HT-H-3F2A1.
    """
    result = hz.release_hold(service(), session_member(context), hold_id)
    if result["status"] == "released" and hz.normalise_id(hold_id) == _get(context, "held_hold_id"):
        _set_held(context, {})
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Redeem the one held reward: take the points and book it, then check the "
        "points ledger and the booking agree. The engine asks the member to "
        "confirm the points and the held reward first. Returns a redemption "
        "reference with both states."
    )
)
async def redeem_reward(hold_id: str, context: ToolContext = None) -> ToolResult:
    """Redeem a held reward.

    Args:
        hold_id: The hold_id from hold_reward.
    """
    result = hz.redeem_reward(
        service(),
        session_member(context),
        session_account(context),
        _get(context, "held_hold_id"),
        hold_id,
        conversation_id(),
    )
    if result.get("effects") == 1:
        # The hold is spent; nothing is left to confirm or redeem.
        _set_held(context, {})
    return ToolResult(llm_response=result)
