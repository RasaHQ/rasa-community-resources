"""Claude turn-order fix: every model request ends on the customer's side.

Without it, a caller who stayed silent until the silence timeout got
"Are you still there?" and then Mantle's "I'm sorry, but something went
wrong. Please try again." on Claude Sonnet 5.5
(case-build/results/2026-09-30-rerun-failed/, recovery-hold-lapsed). The
cause and the rewrite are in lib/turn_order.py, copied from the Willow Shop
returns build. Each rewrite is logged as ``northgate.turn_order_fix`` with
the sender id, so the harness counts it.

The main run (case-build/results/2026-09-30-claude-sonnet-5.5/) was made
before this hook existed; the `no-turn-order-hook` variant in
case-build/conversations.json sets ENABLED to False to reproduce it.
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
    log.info("northgate.turn_order_fix", sender_id=payload.sender_id, system_messages_moved=moved,
             iteration=payload.iteration)
    return payload.model_copy(update={"messages": messages})
