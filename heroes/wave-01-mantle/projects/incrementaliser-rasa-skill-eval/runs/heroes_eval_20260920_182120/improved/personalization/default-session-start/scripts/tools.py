"""Customer profile lookup that runs at session start to personalize the greeting.

This overrides the bundled ``default_session_start`` skill (same skill id wins).
Because this module is auto-discovered at agent load, the ``@tool`` below is
available to the skill's ordered block, which runs it *before* the greeting.
"""

from __future__ import annotations

from datetime import datetime

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

# Fictional signed-in customer for the demo. A real deployment would resolve this
# from the authenticated session / channel identity rather than a hard-coded row.
_CUSTOMER_PROFILE = {
    "customer_id": "cust_00417",
    "legal_name": "Jordan Rivera",
    "preferred_name": "Jordan",  # what we address them as (may differ from legal)
    "tier": "Premier",
    "member_since": "2019",
    "default_account_id": "acc_checking",
    "default_account_label": "Everyday Checking",
}


def _time_of_day(hour: int) -> str:
    """Bucket the current hour into a greeting-friendly part of day."""
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    return "evening"


@tool(
    description=(
        "Look up the signed-in customer's profile (name, tier, tenure, usual "
        "account) at the start of the conversation, before greeting."
    )
)
async def get_customer_profile(context: ToolContext = None) -> ToolResult:
    """Return the customer's profile and record it in shared project memory."""
    time_of_day = _time_of_day(datetime.now().hour)
    if context is not None:
        # Bare names resolve to the root-declared project entries (session.project.*),
        # so every skill can read them. Writing "project.customer_name" would be
        # rejected at train time as an undeclared memory write.
        context.memory.set("customer_name", _CUSTOMER_PROFILE["preferred_name"])
        context.memory.set("customer_tier", _CUSTOMER_PROFILE["tier"])
        context.memory.set("member_since", _CUSTOMER_PROFILE["member_since"])
        context.memory.set("time_of_day", time_of_day)
        context.memory.set("default_account_id", _CUSTOMER_PROFILE["default_account_id"])
        context.memory.set(
            "default_account_label", _CUSTOMER_PROFILE["default_account_label"]
        )
    return ToolResult(
        llm_response={
            "ok": True,
            "customer_id": _CUSTOMER_PROFILE["customer_id"],
            "name": _CUSTOMER_PROFILE["preferred_name"],
            "tier": _CUSTOMER_PROFILE["tier"],
            "member_since": _CUSTOMER_PROFILE["member_since"],
            "time_of_day": time_of_day,
            "default_account": {
                "id": _CUSTOMER_PROFILE["default_account_id"],
                "label": _CUSTOMER_PROFILE["default_account_label"],
            },
        }
    )
