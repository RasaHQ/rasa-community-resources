"""Read the tools' view of a conversation from tracker events. No Rasa imports.

Events are recognised by class name (``UserUttered``, ``BotUttered``), so the
offline tests can pass simple stand-ins.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from lib.reminders import ORGANISATION, Conversation

# The reminder a tool sends starts "<organisation> reminder CC-RMD-XXXXXX:".
_REMINDER_RE = re.compile(rf"^{re.escape(ORGANISATION)} reminder (CC-RMD-[0-9A-F]{{6}}):")


def conversation_from_events(events: Iterable[Any]) -> Conversation:
    users: list[str] = []
    sent: list[tuple[str, int]] = []
    for event in events:
        kind = type(event).__name__
        if kind == "UserUttered":
            text = getattr(event, "text", None) or ""
            if text.startswith("/"):
                continue  # /session_start and other intents are not the patient's words
            users.append(text)
        elif kind == "BotUttered":
            match = _REMINDER_RE.match(getattr(event, "text", None) or "")
            if match:
                sent.append((match.group(1), len(users)))
    return Conversation(user_messages=tuple(users), reminders_sent_at=tuple(sent))
