"""End every Claude request on the customer's side of the conversation. No Rasa imports.

Anthropic's API rejects a request whose last message is the assistant's
("This model does not support assistant message prefill. The conversation
must end with a user message.", HTTP 400 from claude-sonnet-5-5). Mantle
builds one whenever a canned reply went out earlier in the same turn: it
appends a ``system`` reminder ("A canned reply was already sent this turn...")
after the history, and LiteLLM moves every ``system`` message into
Anthropic's top-level system prompt, so the canned reply becomes the last
message (rasa/mantle/prompts/constructor.py, ``build_messages``, on
3.21.0.dev5). Over REST that happens on every conversation's first message
(found in examples/mantle-text-retail-return-claude). On browser_audio the
session starts on connect, so the first turn is clean, but the silence
timeout is a canned check-in ("Are you still there?") followed by a model
call in the same turn, and Claude rejected it twice
(case-build/results/2026-09-30-rerun-failed/, recovery-hold-lapsed).

Copied from the Northgate advisor-appointment build, which copied it from the
Willow Shop returns build.

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
