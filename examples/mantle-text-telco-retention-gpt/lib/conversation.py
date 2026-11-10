"""Read the tools' view of a conversation from tracker events. No Rasa imports.

Events are recognised by class name (``UserUttered``, ``BotUttered``), so the
offline tests can pass simple stand-ins.

Only ``/session_start`` is dropped from the customer's words. Every other
message starting with ``/`` is kept: on Telegram, ``/stop`` is how a user
tells a bot to stop, and it has to count as a refusal.
"""

from __future__ import annotations

from typing import Any, Iterable

from lib.retention import CONFIRM_UTTER, UTTER_ACTION_KEY, Conversation, OfferQuestion

ENGINE_TRIGGERS = ("/session_start",)


def conversation_from_events(events: Iterable[Any]) -> Conversation:
    users: list[str] = []
    questions: list[list] = []  # [text, answer]
    for event in events:
        kind = type(event).__name__
        if kind == "UserUttered":
            text = getattr(event, "text", None) or ""
            if text.strip().lower().startswith(ENGINE_TRIGGERS):
                continue
            users.append(text)
            if questions and questions[-1][1] is None:
                questions[-1][1] = text
        elif kind == "BotUttered":
            metadata = getattr(event, "metadata", None) or {}
            if metadata.get(UTTER_ACTION_KEY) == CONFIRM_UTTER:
                questions.append([getattr(event, "text", None) or "", None])
    return Conversation(user_messages=tuple(users),
                        offer_questions=tuple(OfferQuestion(text=q, answer=a) for q, a in questions))
