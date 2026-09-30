"""Session-start tool for the Willow Shop subscriptions agent.

The member is identified by the chat login before the agent starts; this tool
binds that identity into project memory once. Mantle project memory is
write-once, so a session bound to one member cannot become another.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import subscriptions as ws


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


@tool(description="Load the signed-in member's profile and subscription list into project memory at session start.")
async def load_member_profile(context: ToolContext = None) -> ToolResult:
    profile = ws.member_profile(ws.service_for(_conversation_id()))
    if context is not None and not context.memory.get("project.member_id"):
        context.memory.set("project.member_id", profile["member_id"])
        context.memory.set("project.member_first_name", profile["first_name"])
        context.memory.set("project.subscription_list", profile["subscription_list"])
    public = {k: v for k, v in profile.items() if k != "member_id"}
    return ToolResult(llm_response={"ok": True, **public})
