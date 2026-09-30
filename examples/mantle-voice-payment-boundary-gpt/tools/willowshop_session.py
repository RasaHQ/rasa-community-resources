"""Session tool: bind the signed-in Willow Shop customer at session start.

The voice assistant runs inside the Willow Shop app and website for a
signed-in customer, so the session, not the caller's words, says whose orders
these are. The customer id always comes from project memory, which only this
tool writes. The model never supplies a customer id, a contract fact or a
payment outcome.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import payments as wp


@tool(description="Load the signed-in customer's profile into project memory at session start.")
async def load_session_customer(context: ToolContext = None) -> ToolResult:
    customer = wp.load_data()["customers"][wp.SESSION_CUSTOMER_ID]
    if context is not None and not context.memory.get("project.customer_id"):
        # Project memory is write-once on the pinned engine: set it once only.
        context.memory.set("project.customer_id", wp.SESSION_CUSTOMER_ID)
        context.memory.set("project.customer_first_name", customer["first_name"])
    return ToolResult(llm_response={"ok": True, "first_name": customer["first_name"]})
