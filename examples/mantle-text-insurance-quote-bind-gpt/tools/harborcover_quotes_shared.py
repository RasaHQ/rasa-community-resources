"""Session-start tool for the HarborCover quote-and-bind agent.

The customer is identified by the web-chat session before the agent starts;
this tool binds that identity into project memory once. Mantle project memory
is write-once, so a session bound to one customer cannot become another.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import quotes as hq


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


@tool(description="Load the signed-in customer's profile and saved quotes into project memory at session start.")
async def load_caller_profile(context: ToolContext = None) -> ToolResult:
    profile = hq.caller_profile(hq.service_for(_conversation_id()))
    if context is not None and not context.memory.get("project.customer_id"):
        context.memory.set("project.customer_id", profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
        context.memory.set("project.saved_quotes", hq.saved_quotes_line(profile["quotes"]))
    public = {k: v for k, v in profile.items() if k != "customer_id"}
    return ToolResult(llm_response={"ok": True, **public})
