"""Present source-backed text cards; class ownership uses capability IDs.

This pin cannot forward engine identity as MCP metadata. No ownership claim
is inferred from these presentation hooks. Actual runtime proof is required.
"""
import json
from rasa.mantle.hooks import ToolResultPayload, ModelResponsePayload, modify_tool_result, modify_model_response
from lib.card_text import render_cards
from lib.capability_logging import install as install_log_redaction, redact

install_log_redaction()

_pending_cards: dict[str, str] = {}


@modify_tool_result()
async def prepare_source_cards(result: ToolResultPayload) -> ToolResultPayload:
    if result.tool_name not in ("briefing", "mcp/briefing:briefing"):
        return result
    # Every briefing result owns the next visible response, including failures,
    # unexpected wrappers and empty cards. Never fall back to model prose.
    _pending_cards[result.sender_id] = "The source cards could not be validated. This briefing is unavailable."
    value = result.value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            value = None
    if not result.is_error and isinstance(value, dict) and value.get("status") in ("started", "running"):
        _pending_cards[result.sender_id] = "The briefing is still checking sources; say status in a moment."
        return result
    if not result.is_error and isinstance(value, dict) and value.get("status") == "needs_input":
        missing = value.get("needs_input") or {}
        if isinstance(missing, dict) and missing.get("field") in ("meeting_time", "transfer_minutes") and isinstance(missing.get("question"), str):
            _pending_cards[result.sender_id] = "Briefing needs input: " + missing["question"]
        else:
            _pending_cards[result.sender_id] = "The briefing needs input, but its question could not be validated."
        return result
    if not result.is_error and isinstance(value, dict) and value.get("cards"):
        # Build text only from Core-validated references; numbers are never
        # copied from a specialist's or Mantle model's free-form summary.
        try:
            cards = render_cards(value)
            status = value.get("status")
            prefix = "Briefing complete. " if status == "complete" else "Briefing incomplete; some sources are unavailable. "
            boundary = "Access uses possession of a private briefing ID; it is not bound to this conversation. "
            _pending_cards[result.sender_id] = prefix + boundary + "\n\n" + cards
        except Exception:
            # Tool-result hooks are fail-open in Mantle. Handle bad cards here
            # so the final utterance cannot present an unchecked model summary.
            _pending_cards[result.sender_id] = "The source cards could not be validated. This briefing is unavailable."
    return result


@modify_model_response()
async def present_source_cards(payload: ModelResponsePayload) -> ModelResponsePayload:
    # A model may quote tool context despite instructions. Keep capabilities
    # out of user-visible prose without changing the actual tool arguments.
    payload = payload.model_copy(update={"text": redact(payload.text)})
    # Preserve tool-only iterations: a subsequent get may replace pending data.
    if payload.tool_calls and not payload.text:
        return payload
    cards = _pending_cards.pop(payload.sender_id, None)
    if cards is None:
        return payload
    return payload.model_copy(update={"text": redact(cards)})
