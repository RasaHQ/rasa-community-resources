"""MLflow telemetry is optional and mirrors progress when configured."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from pytest import MonkeyPatch

from rasa_skill_eval.models import ProgressState
from rasa_skill_eval.tracking import MlflowTracker, WandbTracker


def _state() -> ProgressState:
    """Return a minimal progress state for tracker tests."""
    return ProgressState(
        run_id="run",
        started_at="now",
        updated_at="now",
        overall_pct=25.0,
        layer_a={"done": 1, "total": 2, "pct": 50.0},
    )


def test_mlflow_tracker_is_noop_without_uri(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """No tracking URI means no dependency import or external writes."""
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    tracker = MlflowTracker(tmp_path)

    tracker.update(_state())
    tracker.close(_state())

    assert tracker.mlflow is None


def test_mlflow_tracker_logs_progress(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Configured telemetry logs metrics and closes its MLflow run."""
    fake = SimpleNamespace(
        set_tracking_uri=Mock(),
        set_experiment=Mock(),
        start_run=Mock(),
        set_tags=Mock(),
        set_tag=Mock(),
        log_params=Mock(),
        log_metrics=Mock(),
        log_artifact=Mock(),
        log_artifacts=Mock(),
        end_run=Mock(),
    )
    monkeypatch.setitem(sys.modules, "mlflow", fake)
    tracker = MlflowTracker(tmp_path, tracking_uri="file:test")

    tracker.update(_state(), "working")
    tracker.close(_state())

    fake.log_metrics.assert_called_once()
    fake.end_run.assert_called_once()


def test_wandb_tracker_is_noop_without_key(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Missing WANDB_API_KEY must not import wandb or log remotely."""
    monkeypatch.setattr("rasa_skill_eval.tracking._load_env", lambda: None)
    monkeypatch.delenv("WANDB_API_KEY", raising=False)
    tracker = WandbTracker(tmp_path)
    tracker.update(_state())
    tracker.close(_state())
    assert tracker.wandb is None


def test_wandb_tracker_logs_progress(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Configured W&B telemetry logs metrics, the run URL path, and finishes."""
    monkeypatch.setattr("rasa_skill_eval.tracking._load_env", lambda: None)
    monkeypatch.setenv("WANDB_API_KEY", "test-key")
    monkeypatch.setenv("WANDB_PROJECT", "rasa-skill-eval")
    run = SimpleNamespace(
        url="https://wandb.ai/me/rasa-skill-eval/runs/abc",
        summary={},
    )
    artifact = SimpleNamespace(add_file=Mock(), add_dir=Mock())
    fake = SimpleNamespace(
        Settings=Mock(return_value=object()),
        init=Mock(return_value=run),
        log=Mock(),
        Artifact=Mock(return_value=artifact),
        log_artifact=Mock(),
        finish=Mock(),
    )
    monkeypatch.setitem(sys.modules, "wandb", fake)
    tracker = WandbTracker(tmp_path, parameters={"repeats": 3})
    tracker.update(_state(), "working")
    tracker.close(_state())
    fake.init.assert_called_once()
    fake.log.assert_called_once()
    fake.finish.assert_called_once()
    assert tracker.run.url.startswith("https://wandb.ai/")
