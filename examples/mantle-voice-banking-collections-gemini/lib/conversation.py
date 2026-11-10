"""Read the tools' view of a call from tracker events. No Rasa imports.

Events are recognised by class name (``UserUttered``, ``BotUttered``), so the
offline tests can pass simple stand-ins. On a voice call a user event's text
is what speech-to-text heard.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from lib.repayment import CONFIRM_UTTER, UTTER_ACTION_KEY, Conversation


def conversation_from_events(events: Iterable[Any]) -> Conversation:
    users: list[str] = []
    question: Optional[str] = None
    answer: Optional[str] = None
    for event in events:
        kind = type(event).__name__
        if kind == "UserUttered":
            text = getattr(event, "text", None) or ""
            if text.startswith("/"):
                continue  # /session_start and other intents are not the customer's words
            users.append(text)
            if question is not None and answer is None:
                answer = text
        elif kind == "BotUttered":
            metadata = getattr(event, "metadata", None) or {}
            if metadata.get(UTTER_ACTION_KEY) == CONFIRM_UTTER:
                question = getattr(event, "text", None) or ""
                answer = None
    return Conversation(user_texts=tuple(users), confirmation_question=question, confirmation_answer=answer)
