"""Personal preference tools backed by conversation memory."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

_ALLOWED = {"user_timezone", "response_style", "preferred_slack_channel", "notification_mode"}
_DEFAULTS = {"user_timezone": "Asia/Calcutta", "response_style": "brief", "preferred_slack_channel": "all-devcopilot", "notification_mode": "normal"}


@tool(description="Show the developer's saved personal preferences.")
async def get_preferences(context: ToolContext = None) -> ToolResult:
    values = {}
    if context is not None:
        for key in _ALLOWED:
            values[key] = context.memory.get(key) or _DEFAULTS[key]
    else:
        values = dict(_DEFAULTS)
    return ToolResult(llm_response={"ok": True, "preferences": values})


@tool(description="Save one allowed personal preference.")
async def set_preference(name: str, value: str, context: ToolContext = None) -> ToolResult:
    name = str(name).strip().lower()
    if name not in _ALLOWED:
        return ToolResult(llm_response={"ok": False, "error": "unsupported_preference", "allowed": sorted(_ALLOWED)})
    if context is not None:
        context.memory.set(name, str(value).strip())
    return ToolResult(llm_response={"ok": True, "name": name, "value": str(value).strip()})


@tool(description="Forget one saved personal preference and restore its default.")
async def clear_preference(name: str, context: ToolContext = None) -> ToolResult:
    name = str(name).strip().lower()
    if name not in _ALLOWED:
        return ToolResult(llm_response={"ok": False, "error": "unsupported_preference"})
    if context is not None:
        context.memory.set(name, _DEFAULTS[name])
    return ToolResult(llm_response={"ok": True, "name": name, "value": _DEFAULTS[name]})
