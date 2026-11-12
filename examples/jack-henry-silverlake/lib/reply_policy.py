# SPDX-License-Identifier: MIT
"""End a banking turn after its host-owned message has actually been delivered.

This is presentation control, never transfer authority. The host still checks
consent and journals the request before sending. Records live for one runtime
turn only and are not persisted or shared with another example.
"""
from collections import OrderedDict
import re
import time
from uuid import uuid4

from rasa.mantle.hooks.payloads import ModelResponsePayload
from rasa.mantle.orchestration.turn_context import current_turn_context

_delivered = OrderedDict()
# Host-owned wording (silverlake_demo/rasa_adapter.py): a transfer review and an acceptance.
HOST_ONLY = re.compile(r"\breview:\s*transfer\b|\btransfer (request )?was accepted\b|\baccepted does not mean posted\b",
                       re.IGNORECASE)
NO_TRANSFER_TEXT = "No transfer was reviewed or sent in this turn. To move money, ask for a new transfer review."
_MAX_RECORDS = 128
_MAX_AGE = 300


def _turn():
    try:
        native = current_turn_context()
    except LookupError:
        return None
    if native.is_cancelled:
        return None
    return native


def delivery_pending():
    native = _turn()
    if native is None:
        return False
    saved = _delivered.get(native.sender_id)
    return bool(saved and saved[0] is native.turn and time.monotonic()-saved[1] <= _MAX_AGE)


def remember_delivery():
    native = _turn()
    if native is None:
        return
    _delivered[native.sender_id] = (native.turn, time.monotonic())
    _delivered.move_to_end(native.sender_id)
    while len(_delivered) > _MAX_RECORDS:
        _delivered.popitem(last=False)


async def deliver_reply(context, text):
    if context is None or context.is_cancelled or delivery_pending():
        return
    await context.send(text)
    remember_delivery()


async def keep_host_reply_once(payload: ModelResponsePayload) -> ModelResponsePayload:
    native = _turn()
    if native is None or native.sender_id != payload.sender_id:
        return payload
    saved = _delivered.pop(payload.sender_id, None)
    if not saved or saved[0] is not native.turn or time.monotonic()-saved[1] > _MAX_AGE:
        # A review or submit result must come from the host, not a model
        # prediction spoken before that tool runs. Keep the requested calls.
        protected = {"banking_review_transfer", "banking_submit_transfer", "banking_transfer_status"}
        if payload.text and any(call.get("tool_name") in protected for call in payload.tool_calls):
            return payload.model_copy(update={"text": None})
        # Only the host may announce a review or an acceptance. With no host
        # delivery this turn, model text that imitates one is replaced, so a
        # caller never hears a review or "accepted" for a transfer that was
        # never reviewed or sent.
        if payload.text and HOST_ONLY.search(payload.text):
            return payload.model_copy(update={"text": NO_TRANSFER_TEXT})
        return payload
    # Agentic banking has no collect/confirmation flow steps. The supported
    # listen tool ends this turn without a second review, status paraphrase,
    # or another tool call after the host's canonical message.
    return payload.model_copy(update={"text": None, "tool_calls": [{
        "id": "host-reply-" + uuid4().hex, "tool_name": "listen",
        "tool_args": {}, "type": "function"}]})
