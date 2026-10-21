"""Present source-backed text cards; class ownership uses capability IDs.

This pin cannot forward engine identity as MCP metadata. No ownership claim
is inferred from these presentation hooks. Actual runtime proof is required.
"""
from rasa.mantle.hooks import ToolResultPayload, OutgoingTextPayload, modify_tool_result, modify_outgoing_text
from lib.card_text import render_cards
from lib.capability_logging import install as install_log_redaction

install_log_redaction()

_pending_cards: dict[str, str] = {}


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
            boundary = "Access uses possession of a private briefing ID; it is not bound to this conversation. "
            _pending_cards[result.sender_id] = prefix + boundary + "\n\n" + cards
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
