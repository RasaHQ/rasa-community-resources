"""Host-owned deadline shared across a turn's threads and subprocesses."""

from contextvars import ContextVar
from dataclasses import dataclass, field
import threading
import time
from typing import Callable


@dataclass
class TurnBudget:
    deadline: float
    cancelled: threading.Event = field(default_factory=threading.Event)
    valid: Callable[[], bool] = lambda: True

    def remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if self.cancelled.is_set() or remaining <= 0 or not self.valid():
            raise TimeoutError("turn_unavailable")
        return remaining


current_budget: ContextVar[TurnBudget | None] = ContextVar("ui_turn_budget", default=None)
