"""Read the tools' view of a conversation from tracker events. No Rasa imports.

Events are recognised by class name (``UserUttered``, ``BotUttered``), so the
offline tests can pass simple stand-ins.
"""

from __future__ import annotations

from typing import Any, Iterable

from lib.claims import CONFIRM_UTTER, UTTER_ACTION_KEY, Conversation, UserMessage, attachments_in


def conversation_from_events(events: Iterable[Any]) -> Conversation:
    users: list[UserMessage] = []
    question = None
    answered = False
    for event in events:
        kind = type(event).__name__
        if kind == "UserUttered":
            text = getattr(event, "text", None) or ""
            if text.startswith("/"):
                continue  # /session_start and other intents are not the customer's words
            metadata = getattr(event, "metadata", None) or {}
            users.append(UserMessage(text=text, attachments=attachments_in(text, metadata)))
            if question is not None:
                answered = True
        elif kind == "BotUttered":
            metadata = getattr(event, "metadata", None) or {}
            if metadata.get(UTTER_ACTION_KEY) == CONFIRM_UTTER:
                question = getattr(event, "text", None) or ""
                answered = False
    return Conversation(user_messages=tuple(users), confirmation_question=question, confirmation_answered=answered)
