"""Claude turn-order fix: every model request ends on the caller's side.

On browser_audio the first turn is clean, because the session starts when the
socket connects. But Mantle's silence timeout sends a canned check-in ("Are
you still there?") and then calls the model in the same turn, and Claude
Sonnet 5.5 rejected that request with HTTP 400 "does not support assistant
message prefill" in the Northgate advisor-appointment build
(examples/mantle-voice-banking-advisor-appointment-claude,
case-build/results/2026-09-30-rerun-failed/). The cause and the rewrite are in
lib/turn_order.py, copied from that build. Each rewrite is logged as
``harborcover.turn_order_fix`` with the sender id, so the harness counts it.
"""

from __future__ import annotations

import structlog

from lib.turn_order import end_on_customer_side
from rasa.mantle.hooks import ModelRequestPayload, modify_model_request

log = structlog.get_logger()

ENABLED = True


@modify_model_request()
async def end_requests_on_customer_side(payload: ModelRequestPayload) -> ModelRequestPayload:
    if not ENABLED:
        return payload
    messages, moved = end_on_customer_side(list(payload.messages))
    if messages is payload.messages or messages == payload.messages:
        return payload
    log.info("harborcover.turn_order_fix", sender_id=payload.sender_id, system_messages_moved=moved,
             iteration=payload.iteration)
    return payload.model_copy(update={"messages": messages})
