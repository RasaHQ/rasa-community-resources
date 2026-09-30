"""Session tool: bind the signed-in Willow Shop customer at session start.

The voice widget runs on the Willow Shop website for a signed-in customer, so
the session, not the caller's words, says whose orders these are. The customer
id always comes from project memory, which only this tool writes. The model
never supplies a customer id, a contract fact or a milestone.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.orders import session_profile


@tool(description="Load the signed-in customer's profile into project memory at session start.")
async def load_session_customer(context: ToolContext = None) -> ToolResult:
    profile = session_profile()
    if context is not None and not context.memory.get("project.customer_id"):
        # Project memory is write-once on the pinned engine: set it once only.
        context.memory.set("project.customer_id", profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
        context.memory.set("project.order_numbers", ", ".join(profile["order_numbers"]))
    public = {k: v for k, v in profile.items() if k != "customer_id"}
    return ToolResult(llm_response={"ok": True, **public})
