"""Start every Gemini request on the customer's side of the conversation. No Rasa imports.

Gemini rejects a request whose history has a function call that does not
follow a user turn or a function response ("Please ensure that function call
turn comes immediately after a user turn or after a function response turn.",
HTTP 400 from gemini-3.8-flash). Mantle builds one once a call is long enough:
it keeps the last 10 user and bot utterances of the tracker
(``DEFAULT_MAX_UTTERANCES`` and ``_retained_utterance_window`` in
rasa/mantle/prompts/messages.py, 3.21.0.dev5). When the cut lands on a bot
message, the window is snapped back to the start of that turn so its tool
calls are kept, but the customer message that opened the turn is dropped.
The history then opens on the agent's tool call, with no user turn before
it, and every later model call in the call fails with Mantle's "algo salió
mal". Gemini writes a short acknowledgement beside most tool calls and the
tools send their own receipts, so ten utterances go by in three or four
caller turns (case-build/results/2026-09-30-gemini-3.8-flash/).

``start_on_customer_side`` inserts one ``user`` message, marked as an engine
note, before a history that would open on the agent, and leaves every other
request untouched. It never invents the customer's words and drops nothing.
"""

from __future__ import annotations

from typing import Any

ENGINE_NOTE = "[Engine note, not from the customer] Earlier messages of this call are omitted."


def start_on_customer_side(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The messages, with an engine note before the history when it would open on the agent."""
    first = next((i for i, m in enumerate(messages) if m.get("role") != "system"), None)
    if first is None or messages[first].get("role") == "user":
        return messages
    return [*messages[:first], {"role": "user", "content": ENGINE_NOTE}, *messages[first:]]
