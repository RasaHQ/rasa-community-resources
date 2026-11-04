"""Terminal progress bars start clocks only for active phases."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from rasa_skill_eval.models import ProgressState
from rasa_skill_eval.ui import TerminalProgressUI


def _state(**phase_totals: dict[str, int]) -> ProgressState:
    """Build a ProgressState with explicit done/total per phase."""
    now = datetime.now(UTC).isoformat()
    kwargs: dict[str, Any] = {
        "run_id": "test-run",
        "started_at": now,
        "updated_at": now,
    }
    for phase in ("layer_a", "layer_b", "deepeval", "finalize"):
        summary = phase_totals.get(phase, {"done": 0, "total": 0})
        total = int(summary.get("total", 0))
        done = int(summary.get("done", 0))
        kwargs[phase] = {
            "done": done,
            "total": total,
            "pct": round(100 * done / total, 1) if total else 0.0,
        }
    return ProgressState(**kwargs)


def _task(ui: TerminalProgressUI, phase: str) -> Any:
    """Return the Rich task object for a phase."""
    assert ui.progress is not None
    return ui.progress.tasks[ui.tasks[phase]]


@pytest.fixture
def ui(monkeypatch: pytest.MonkeyPatch) -> TerminalProgressUI:
    """Build an enabled UI without requiring a real TTY."""
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    monkeypatch.setattr("rasa_skill_eval.ui.logger.remove", MagicMock())
    monkeypatch.setattr("rasa_skill_eval.ui.logger.add", MagicMock())
    renderer = TerminalProgressUI(enabled=True)
    assert renderer.progress is not None
    yield renderer
    renderer.progress.stop()


def test_phase_timers_start_only_when_active(ui: TerminalProgressUI) -> None:
    """Waiting phases keep start_time unset while an earlier phase runs."""
    for phase in ("layer_a", "layer_b", "deepeval", "finalize"):
        assert _task(ui, phase).start_time is None

    ui.update(_state(layer_a={"done": 0, "total": 2}, layer_b={"done": 0, "total": 4}))

    assert _task(ui, "layer_a").start_time is not None
    assert _task(ui, "layer_b").start_time is None
    assert _task(ui, "deepeval").start_time is None
    assert _task(ui, "finalize").start_time is None


def test_phase_timer_stops_when_complete_and_next_starts(ui: TerminalProgressUI) -> None:
    """Finishing a phase freezes its clock and starts the next active phase."""
    ui.update(_state(layer_a={"done": 1, "total": 2}, layer_b={"done": 0, "total": 3}))
    assert _task(ui, "layer_a").start_time is not None
    assert _task(ui, "layer_b").start_time is None

    ui.update(_state(layer_a={"done": 2, "total": 2}, layer_b={"done": 0, "total": 3}))

    assert _task(ui, "layer_a").finished_time is not None
    assert _task(ui, "layer_b").start_time is not None
    assert "layer_a" in ui._stopped
    assert "layer_b" in ui._started


def test_resume_starts_partially_completed_phase(ui: TerminalProgressUI) -> None:
    """A resumed phase with prior completions starts its timer immediately."""
    ui.update(
        _state(
            layer_a={"done": 2, "total": 2},
            layer_b={"done": 1, "total": 4},
        )
    )

    assert _task(ui, "layer_a").finished_time is not None
    assert _task(ui, "layer_b").start_time is not None
    assert _task(ui, "deepeval").start_time is None
