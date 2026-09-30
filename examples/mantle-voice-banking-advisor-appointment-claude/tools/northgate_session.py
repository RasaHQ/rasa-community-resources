"""Session tool: bind the signed-in Northgate Bank customer at session start.

The voice assistant runs inside Northgate's online banking for a signed-in
customer, so the session, not the caller's words, says who is booking. The
customer id always comes from project memory, which only this tool writes.
The model never supplies a customer id, a contract fact or a booking outcome.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.appointments import session_profile


@tool(description="Load the signed-in customer's profile into project memory at session start.")
async def load_session_customer(context: ToolContext = None) -> ToolResult:
    profile = session_profile()
    if context is not None and not context.memory.get("project.customer_id"):
        # Project memory is write-once on the pinned engine: set it once only.
        context.memory.set("project.customer_id", profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
    return ToolResult(llm_response={"ok": True, "first_name": profile["first_name"]})
