"""End every Gemini request on the customer's side of the conversation. No Rasa imports.

Gemini rejects a request whose last content is the model's ("Requests ending
with a model turn are not supported.", HTTP 400 from gemini-3.8-flash).
Mantle builds one whenever a canned reply went out earlier in the same turn:
it appends a ``system`` reminder ("A canned reply was already sent this
turn...") after the history, and LiteLLM moves every ``system`` message into
Gemini's system instruction, so the canned reply becomes the last content
(rasa/mantle/prompts/constructor.py, ``build_messages``, on 3.21.0.dev5). In
this build it happened after ``cannot_help``: the caller heard the canned
decline and then "Lo siento, algo salió mal", twice in one call
(case-build/results/2026-09-30-gemini-3.8-flash/,
adversarial-someone-elses-account). Claude rejects the same request shape as
"assistant message prefill"; the Willow Shop returns build found it there.

The code is copied from the Northgate advisor-appointment build
(examples/mantle-voice-banking-advisor-appointment-claude/lib/turn_order.py).

``end_on_customer_side`` turns trailing ``system`` messages after an
assistant message into one ``user`` message marked as an engine note, and
leaves every other request untouched. It never invents the customer's words.
"""

from __future__ import annotations

from typing import Any

ENGINE_NOTE = "[Engine note, not from the customer]"


def end_on_customer_side(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """(messages, number of system messages moved). Unchanged unless the request would end on the assistant."""
    last = max((i for i, m in enumerate(messages) if m.get("role") != "system"), default=None)
    if last is None or messages[last].get("role") != "assistant":
        return messages, 0
    trailing = [m for m in messages[last + 1:] if m.get("role") == "system"]
    notes = [str(m.get("content") or "").strip() for m in trailing]
    text = "\n\n".join(n for n in notes if n) or "Continue the conversation."
    note = {"role": "user", "content": f"{ENGINE_NOTE}\n{text}"}
    return [*messages[: last + 1], note], len(trailing)
