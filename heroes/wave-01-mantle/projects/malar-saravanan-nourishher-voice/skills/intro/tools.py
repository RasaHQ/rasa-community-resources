"""Intro skill tools — local to skills/intro/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult


@tool(description="Save the name the person wants to be called.")
async def save_user_name(first_name_given: str, context: ToolContext = None) -> ToolResult:
    """Save the person's preferred name to project memory.

    Args:
        first_name_given: Name the person gave, as they said it.
    """
    cleaned = str(first_name_given).strip()
    if context is not None:
        context.memory.set("user_first_name", cleaned)
    return ToolResult(llm_response={"ok": True, "first_name": cleaned})
