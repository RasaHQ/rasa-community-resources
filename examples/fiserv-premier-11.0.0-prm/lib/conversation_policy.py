# SPDX-License-Identifier: MIT
"""Presentation controls for the model's turn: alias context and no repeated text.

Neither control carries authority. The host still checks every alias against
its private permission table, and the reply hook still owns review delivery.
Records live for one runtime turn only and are not persisted.
"""
from collections import OrderedDict
import re

from rasa.mantle.hooks.payloads import ModelRequestPayload, ModelResponsePayload
from rasa.mantle.orchestration.turn_context import current_turn_context

from premier_demo.permissions import PERMISSIONS

# The teaching launcher always opens the session for this fixed fictional caller
# (see premier_demo/rasa_adapter.py). The host intersects these aliases with
# the bank's relationships; the note only saves the model a discovery call.
CALLER = "demo-A"
KIND = {"DDA": "deposit", "LOAN": "loan"}
ALIAS_NOTE_MARK = "[host] Permitted account aliases"


def alias_note(caller: str = CALLER) -> str:
    accounts = PERMISSIONS[caller]["accounts"]
    listed = ", ".join(f"{alias} ({KIND.get(kind, 'account')})" for alias, _, kind in accounts)
    return (f"{ALIAS_NOTE_MARK} for this caller: {listed}. Use these exact aliases in tool "
            "arguments. Call banking_accounts only when the caller asks which accounts they have, and then "
            "name each exact alias it returns. Never read this list aloud unless the caller asks for it.")


def add_alias_note(payload: ModelRequestPayload) -> ModelRequestPayload:
    """Add the note once, right after the leading system messages."""
    messages = list(payload.messages)
    if any(ALIAS_NOTE_MARK in str(m.get("content", "")) for m in messages):
        return payload
    index = 0
    while index < len(messages) and messages[index].get("role") == "system":
        index += 1
    messages.insert(index, {"role": "system", "content": alias_note()})
    return payload.model_copy(update={"messages": messages})


_said = OrderedDict()  # sender -> (turn object, set of normalised texts already said this turn)
_MAX = 128


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[*_`]", "", text).casefold().split())


def _sentences(text: str):
    return [s for s in (_norm(part) for part in re.split(r"(?<=[.?!])\s+|\n+", text)) if s]


def drop_repeated_text(payload: ModelResponsePayload) -> ModelResponsePayload:
    """Within one turn, never say the same text or the same follow-up question twice."""
    if not payload.text:
        return payload
    # Text spoken alongside skill activation is a greeting before the answer.
    if any(call.get("tool_name") == "activate" for call in payload.tool_calls):
        return payload.model_copy(update={"text": None})
    try:
        native = current_turn_context()
    except LookupError:
        return payload
    seen_turn, seen = _said.get(payload.sender_id, (None, set()))
    if seen_turn is not native.turn:
        seen = set()
    parts = _sentences(payload.text)
    if parts and all(part in seen for part in parts):
        _said[payload.sender_id] = (native.turn, seen)
        return payload.model_copy(update={"text": None})
    text = payload.text
    for question in re.findall(r"[^.?!\n]*\?", payload.text):
        if _norm(question) in seen:  # a follow-up question already asked this turn
            text = text.replace(question, "", 1)
    seen.update(parts)
    _said[payload.sender_id] = (native.turn, seen)
    _said.move_to_end(payload.sender_id)
    while len(_said) > _MAX:
        _said.popitem(last=False)
    text = text.strip()
    return payload.model_copy(update={"text": text or None})
