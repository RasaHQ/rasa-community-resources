"""Present short validated panel notices; class ownership uses capability IDs.

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
    if result.tool_name not in ("briefing", "mcp/briefing:briefing", "find_flights", "mcp/briefing:find_flights"):
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
    if result.tool_name in ("find_flights", "mcp/briefing:find_flights"):
        try:
            from briefing.traveller import discovery_notice
            if result.is_error or not isinstance(value, dict):
                raise ValueError('invalid_discovery')
            _pending_cards[result.sender_id] = discovery_notice(value)
        except Exception:
            _pending_cards[result.sender_id] = "Do you know the airline or flight number? I can use it to check a flight already in the air."
        return result
    if not result.is_error and isinstance(value, dict) and value.get("status") in ("started", "running") and not value.get("cards"):
        _pending_cards[result.sender_id] = "The briefing is still checking sources; say status in a moment."
        return result
    if not result.is_error and isinstance(value, dict) and value.get("status") == "needs_input":
        missing = value.get("needs_input") or {}
        if isinstance(missing, dict) and missing.get("field") in ("meeting_time", "transfer_minutes", "destination", "flight") and isinstance(missing.get("question"), str) and (
                0 < len(missing["question"]) <= 200
                and missing["question"].isprintable()
                and not any(marker in missing["question"] for marker in ("<", ">", "://"))):
            _pending_cards[result.sender_id] = missing["question"]
        else:
            _pending_cards[result.sender_id] = "The briefing needs input, but its question could not be validated."
        return result
    if not result.is_error and isinstance(value, dict) and value.get("cards"):
        # Build text only from Core-validated references; numbers are never
        # copied from a specialist's or Mantle model's free-form summary.
        try:
            # Validate every reference before announcing the panel. Detailed
            # values and provenance belong to the graphical cards, not speech.
            render_cards(value)
            if any(card.get("replaced") is True for card in value["cards"]):
                text = "Your briefing is updating. Check the panel on the right for the current cards."
            elif value.get("status") == "complete":
                text = "Your briefing is ready in the panel on the right. Check the cards for source details and assumptions."
            else:
                text = "Some briefing sources are unavailable. Check the panel on the right for the available cards and reasons."
            if any(card.get("data_ref", {}).get("replay") is True for card in value["cards"]):
                text = "Replay: " + text
            _pending_cards[result.sender_id] = text
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
