"""Claude turn-order fix: every model request ends on the employee's side.

Over REST and socket.io the employee's first message starts the session, so
the session-start greeting is a canned reply sent in the same turn. Mantle
then appends a ``system`` reminder after the history, LiteLLM lifts every
``system`` message into Anthropic's top-level prompt, and the request ends on
the greeting. Claude Sonnet 5.5 rejects it with HTTP 400 ("does not support
assistant message prefill") and the employee gets "I'm sorry, but something
went wrong." (found in the Willow Shop returns and Northgate loan builds; this
build records its own as-shipped run). The rewrite is in lib/turn_order.py.
Each rewrite is logged as ``orchard.turn_order_fix`` with the sender id, so
the harness counts it.

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
async def end_requests_on_employee_side(payload: ModelRequestPayload) -> ModelRequestPayload:
    if not ENABLED:
        return payload
    messages, moved = end_on_customer_side(list(payload.messages))
    if messages is payload.messages or messages == payload.messages:
        return payload
    log.info("orchard.turn_order_fix", sender_id=payload.sender_id, system_messages_moved=moved,
             iteration=payload.iteration)
    return payload.model_copy(update={"messages": messages})
