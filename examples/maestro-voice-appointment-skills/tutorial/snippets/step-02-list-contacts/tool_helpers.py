"""Helpers shared by the shared tools and every skill-local ``tools.py``.

Skill-local tool modules import from ``lib`` rather than from
``tools/clinic.py`` so that no skill depends on another skill's tools and
nothing imports in a circle.
"""

from __future__ import annotations

from typing import Any, Optional

from rasa.calm_v2.tools.decorator import ToolContext


def memory_value(context: Optional[ToolContext], key: str) -> Any:
    """Read a memory entry, tolerating a missing context (unit tests, REPL)."""
    if context is None:
        return None
    return context.memory.get(key)


def set_memory(context: Optional[ToolContext], key: str, value: Any) -> None:
    """Write a memory entry, tolerating a missing context.

    Shared tools may run under several skills. If the active skill does not
    declare *key* (and neither does project memory), skip the write instead of
    failing the whole tool — the ``ToolResult`` payload is still returned.
    """
    if context is None:
        return
    try:
        context.memory.set(key, value)
    except Exception:
        return
