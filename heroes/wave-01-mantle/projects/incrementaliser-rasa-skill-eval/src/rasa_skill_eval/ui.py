"""Clean Rich terminal rendering for evaluation progress."""

from __future__ import annotations

import sys
from typing import Any

from loguru import logger
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from rasa_skill_eval.models import ProgressState

PHASES = ("layer_a", "layer_b", "deepeval", "finalize")


class TerminalProgressUI:
    """Render one stable bar per evaluation phase without scrolling logs."""

    def __init__(self, *, enabled: bool = True) -> None:
        """Create an interactive renderer when stderr is a terminal."""
        self.enabled = enabled and sys.stderr.isatty()
        self.console = Console(stderr=True)
        self.progress: Progress | None = None
        self.tasks: dict[str, int] = {}
        self._started: set[str] = set()
        self._stopped: set[str] = set()
        self.latest_message = ""
        if self.enabled:
            logger.remove()
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("{task.description:10}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                TextColumn("{task.fields[status]}"),
                console=self.console,
                transient=False,
                refresh_per_second=4,
            )
            self.progress.start()
            for phase in PHASES:
                self.tasks[phase] = self.progress.add_task(
                    phase.replace("_", " ").title(),
                    total=1,
                    start=False,
                    status="waiting",
                )

    def update(self, state: ProgressState, message: str = "") -> None:
        """Refresh phase bars and start timers only for active or resumed work."""
        if message:
            self.latest_message = message
        if self.progress is None:
            return
        active = _active_phase(state)
        for phase, task_id in self.tasks.items():
            summary: dict[str, Any] = getattr(state, phase)
            total = int(summary.get("total", 0))
            done = int(summary.get("done", 0))
            if phase not in self._started and total > 0 and (phase == active or done > 0):
                self.progress.start_task(task_id)
                self._started.add(phase)
            if phase not in self._stopped and total > 0 and done >= total:
                self.progress.stop_task(task_id)
                self._stopped.add(phase)
            self.progress.update(
                task_id,
                total=max(total, 1),
                completed=done,
                status=self.latest_message if phase == active else "",
            )

    def close(self, state: ProgressState) -> None:
        """Stop live rendering and restore a normal Loguru stderr sink."""
        self.update(state)
        if self.progress is not None:
            self.progress.stop()
            self.progress = None
            logger.add(sys.stderr, level="INFO")


def _active_phase(state: ProgressState) -> str:
    """Return the first phase with unfinished work."""
    for phase in PHASES:
        summary: dict[str, Any] = getattr(state, phase)
        if summary.get("done", 0) < summary.get("total", 0):
            return phase
    return "finalize"
