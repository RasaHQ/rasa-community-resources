"""Bind MCP ownership to Mantle's engine identity, never model arguments.

Pinned-runtime propagation must be verified before claiming this hook works.
The MCP service independently requires an authenticated Mantle transport peer.
"""
from rasa.mantle.hooks import (
    ToolCallPayload, ToolResultPayload, OutgoingTextPayload,
    modify_tool_call, modify_tool_result, modify_outgoing_text,
)
from lib.card_text import render_cards

_pending_cards: dict[str, str] = {}


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


@modify_tool_result()
async def prepare_source_cards(result: ToolResultPayload) -> ToolResultPayload:
    if result.tool_name not in ("briefing", "mcp/briefing:briefing"):
        return result
    _pending_cards.pop(result.sender_id, None)
    if not result.is_error and isinstance(result.value, dict) and result.value.get("cards"):
        # Build text only from Core-validated references; numbers are never
        # copied from a specialist's or Mantle model's free-form summary.
        try:
            cards = render_cards(result.value)
            status = result.value.get("status")
            prefix = "Briefing complete. " if status == "complete" else "Briefing incomplete; some sources are unavailable. "
            _pending_cards[result.sender_id] = prefix + "\n\n" + cards
        except Exception:
            # Tool-result hooks are fail-open in Mantle. Handle bad cards here
            # so the final utterance cannot present an unchecked model summary.
            _pending_cards[result.sender_id] = "The source cards could not be validated. This briefing is unavailable."
    return result


@modify_outgoing_text()
async def present_source_cards(payload: OutgoingTextPayload) -> OutgoingTextPayload:
    cards = _pending_cards.pop(payload.sender_id, None)
    if cards is None:
        return payload
    return payload.model_copy(update={"text": cards})
