"""Mantle-facing seam; all services are supplied by the authenticated host.

The producer retains the original result and makes its canonical envelope.
Neither this adapter nor rendering performs a second Broker read.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from .turns import TurnView


@dataclass(frozen=True)
class RetainedRead:
    operation: str
    invocation: str
    envelope: bytes


async def show_current(
    view: TurnView,
    operation: str,
    invocation: str,
    read: Callable[[], Awaitable[RetainedRead]],
    retained_original: Callable[[str, str], bool],
) -> dict[str, str]:
    """Use once for the current host turn; begin/clear also on non-tool turns."""
    turn = view.begin(operation, invocation)
    try:
        result = await asyncio.wait_for(read(), timeout=8)
        if (result.operation, result.invocation) != (operation, invocation):
            raise ValueError("producer_binding")
        accepted = view.accept(
            turn, result.envelope, retained_original=retained_original
        )
    except Exception:
        view.fail(turn)
        accepted = False
    return {"status": "displayed" if accepted else "unavailable"}
