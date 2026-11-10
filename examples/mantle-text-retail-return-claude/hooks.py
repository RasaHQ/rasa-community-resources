"""Claude turn-order fix: every model request ends on the customer's side.

Without it, the first message of every web-chat conversation got Mantle's
"I'm sorry, but something went wrong. Please try again." on Claude Sonnet 5.5
(case-build/results/2026-09-30-claude-sonnet-5.5-as-shipped/). The cause and
the rewrite are in lib/turn_order.py. Each rewrite is logged as
``willowshop.turn_order_fix`` with the sender id, so the harness counts it.

The `no-turn-order-hook` variant in case-build/conversations.json sets
ENABLED to False to reproduce the failure.
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
    log.info("willowshop.turn_order_fix", sender_id=payload.sender_id, system_messages_moved=moved,
             iteration=payload.iteration)
    return payload.model_copy(update={"messages": messages})
