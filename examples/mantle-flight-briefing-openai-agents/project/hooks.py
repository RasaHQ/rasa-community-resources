"""Bind MCP ownership to Mantle's engine identity, never model arguments.

Pinned-runtime propagation must be verified before claiming this hook works.
The MCP service independently requires an authenticated Mantle transport peer.
"""
from rasa.mantle.hooks import ToolCallPayload, modify_tool_call


@modify_tool_call()
async def bind_briefing_conversation(call: ToolCallPayload) -> ToolCallPayload:
    if call.tool_name not in ("briefing", "mcp/briefing:briefing"):
        return call
    sender = call.sender_id
    if (not isinstance(sender, str) or not sender.strip() or len(sender) > 200
            or any(ord(char) < 32 or ord(char) == 127 for char in sender)):
        # Unexpected modifier errors fail closed in Mantle; do not allow the
        # original call through or fall back to model-provided identity.
        raise ValueError("conversation_identity_required")
    return call.model_copy(update={"metadata": {"rasa.briefing.sender_id": sender}})
