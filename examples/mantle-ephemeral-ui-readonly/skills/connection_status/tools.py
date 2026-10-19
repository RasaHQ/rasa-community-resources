"""Mantle entrypoint; the authenticated host binds services for this turn."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Awaitable, Callable

from rasa.mantle.tools.decorator import tool
from rasa.mantle.tools.result import ToolResult

from lib.mantle_adapter import RetainedRead, show_current
from lib.turns import TurnView


@dataclass(frozen=True)
class Services:
    view: TurnView
    operation: str
    invocation: str
    read: Callable[[], Awaitable[RetainedRead]]
    retained_original: Callable[[str, str], bool]


_services: ContextVar[Services | None] = ContextVar("readonly_ui_services", default=None)


@contextmanager
def bind_services(services: Services):
    """Host-only hook around a single authenticated Mantle turn; never memory."""
    token = _services.set(services)
    try:
        yield
    finally:
        _services.reset(token)


@tool(description="Show the connections made visible to this application's device. Does not read provider content or invoke provider operations.")
async def show_connection_status() -> ToolResult:
    services = _services.get()
    if services is None:
        return ToolResult(llm_response={"status": "unavailable"})
    status = await show_current(
        services.view, services.operation, services.invocation,
        services.read, services.retained_original,
    )
    return ToolResult(llm_response=status)
