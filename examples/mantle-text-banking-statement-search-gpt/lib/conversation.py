"""Read the caller's own words from tracker events. No Rasa imports.

Events are recognised by class name (``UserUttered``), so the offline tests
can pass simple stand-ins.
"""

from __future__ import annotations

from typing import Any, Iterable


def caller_texts(events: Iterable[Any]) -> list[str]:
    """Every message the caller typed in this conversation, oldest first."""
    texts = []
    for event in events:
        if type(event).__name__ != "UserUttered":
            continue
        text = getattr(event, "text", None) or ""
        if text.startswith("/"):
            continue  # /session_start and other intents are not the caller's words
        texts.append(text)
    return texts
