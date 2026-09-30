"""Two Gemini request fixes: every model request opens and ends on the customer's side.

Both are Mantle request shapes that gemini-3.8-flash rejects with HTTP 400,
and in both the caller heard "Lo siento, algo salió mal" in the main run
(case-build/results/2026-09-30-gemini-3.8-flash/):

- ``lib/turn_order.py``: after a canned reply in the same turn (here the
  decline after ``cannot_help``) the request ends on the model's message
  ("Requests ending with a model turn are not supported"). The fix appends
  one engine note as a user message. Copied from the Northgate advisor build,
  where Claude rejected the same shape.
- ``lib/history_start.py``: once a call passes ten user and bot messages,
  Mantle's history window can open on the agent's tool call with no user
  turn before it ("Please ensure that function call turn comes immediately
  after a user turn or after a function response turn"). The fix puts one
  engine note first.

Neither invents the customer's words or drops a message. Each rewrite is
logged (``northgate.turn_order_fix``, ``northgate.history_start_fix``) with
the sender id, so the harness counts them. The main run was made before this
hook existed; the `no-request-hooks` variant in case-build/conversations.json
sets ENABLED to False to reproduce it.
"""

from __future__ import annotations

import structlog

from lib.history_start import start_on_customer_side
from lib.turn_order import end_on_customer_side
from rasa.mantle.hooks import ModelRequestPayload, modify_model_request

log = structlog.get_logger()

ENABLED = True


@modify_model_request()
async def keep_requests_on_customer_side(payload: ModelRequestPayload) -> ModelRequestPayload:
    if not ENABLED:
        return payload
    original = list(payload.messages)
    ended, moved = end_on_customer_side(original)
    if ended is not original:
        log.info("northgate.turn_order_fix", sender_id=payload.sender_id, system_messages_moved=moved,
                 iteration=payload.iteration)
    started = start_on_customer_side(ended)
    if started is not ended:
        log.info("northgate.history_start_fix", sender_id=payload.sender_id, iteration=payload.iteration)
    if started is original:
        return payload
    return payload.model_copy(update={"messages": started})
