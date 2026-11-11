"""Shared helpers for DevPilot @tool functions."""

from __future__ import annotations

from typing import Any, Optional

from lib.database import (
    DEMO_TECH_ID,
    Database,
    get_technician,
    resolve_tech_id,
)


def active_tech_id(context: Any = None) -> str:
    """Return the demo developer id from memory, falling back to Alex / 101."""
    if context is None:
        return resolve_tech_id()
    candidate = resolve_tech_id(context.memory.get("tech_id"))
    if candidate == DEMO_TECH_ID:
        return candidate
    db = Database()
    if get_technician(db, candidate) is None:
        return DEMO_TECH_ID
    return candidate


def tech_display_name(context: Any = None) -> Optional[str]:
    """Best-effort first + last name from project memory."""
    if context is None:
        return None
    first = context.memory.get("tech_first_name")
    last = context.memory.get("tech_last_name")
    if first and last:
        return f"{first} {last}"
    if first:
        return str(first)
    return None
