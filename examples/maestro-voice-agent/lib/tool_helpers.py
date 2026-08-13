"""Shared helpers for travel @tool functions."""

from __future__ import annotations

from typing import Any, Optional

from lib.database import resolve_customer_id


def active_customer_id(context: Any = None) -> str:
    """Return the demo traveler id from memory, falling back to Maya / 456."""
    if context is None:
        return resolve_customer_id()
    return resolve_customer_id(context.memory.get("customer_id"))


def traveler_display_name(context: Any = None) -> Optional[str]:
    """Best-effort first + last name from project memory."""
    if context is None:
        return None
    first = context.memory.get("customer_first_name")
    last = context.memory.get("customer_last_name")
    if first and last:
        return f"{first} {last}"
    if first:
        return str(first)
    return None
