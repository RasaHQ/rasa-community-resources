"""Optional MLflow and Weights & Biases mirrors for evaluation progress."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from loguru import logger

from rasa_skill_eval import PROJECT_ROOT
from rasa_skill_eval.models import ProgressState

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def _wandb_default_entity(wandb: Any) -> str | None:
    """Best-effort entity for wandb 0.30 when ``WANDB_ENTITY`` is unset."""
    try:
        api = wandb.Api()
        guessed = getattr(api, "default_entity", None)
        if guessed:
            return str(guessed)
        viewer = api.viewer() if hasattr(api, "viewer") else None
        if isinstance(viewer, dict):
            value = viewer.get("entity") or viewer.get("username")
            if value:
                return str(value)
    except Exception:
        return None
    return None


def _load_env() -> None:
    """Load gitignored ``.env`` so tracking keys are visible."""
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")


def _progress_metrics(state: ProgressState) -> dict[str, float]:
    """Map a progress snapshot to numeric counters shared by trackers."""
    metrics: dict[str, float] = {"overall_pct": state.overall_pct}
    for phase in ("layer_a", "layer_b", "deepeval", "finalize"):
        summary: dict[str, Any] = getattr(state, phase)
        metrics[f"{phase}_done"] = float(summary.get("done", 0))
        metrics[f"{phase}_total"] = float(summary.get("total", 0))
        metrics[f"{phase}_pct"] = float(summary.get("pct", 0))
    tsr_units = [unit for unit in state.units.values() if unit.key.startswith("scenario:")]
    metrics["tsr_live_count"] = float(sum(unit.status == "complete" for unit in tsr_units))
    metrics["tsr_skipped_count"] = float(sum(unit.status == "skipped" for unit in tsr_units))
    return metrics


class MlflowTracker:
    """Mirror progress to MLflow when its optional dependency is configured."""

    def __init__(
        self,
        run_dir: Path,
        *,
        tracking_uri: str | None = None,
        source_run: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """Start an MLflow run, or remain disabled when unavailable."""
        _load_env()
        self.run_dir = run_dir
        self.mlflow: Any | None = None
        self.step = 0
        uri = tracking_uri or os.getenv("MLFLOW_TRACKING_URI", "").strip()
        if not uri:
            return
        try:
            import mlflow

            mlflow.set_tracking_uri(uri)
            mlflow.set_experiment("rasa-skill-eval")
            mlflow.start_run(run_name=run_dir.name)
            mlflow.set_tags(
                {
                    "run_dir": str(run_dir),
                    "source_run": source_run or "",
                    "status": "running",
                }
            )
            if parameters:
                mlflow.log_params({key: str(value) for key, value in parameters.items()})
            self.mlflow = mlflow
        except Exception as exc:
            logger.warning("MLflow tracking disabled: {}", exc)

    def update(self, state: ProgressState, message: str = "") -> None:
        """Log progress counters and the currently running unit."""
        if self.mlflow is None:
            return
        self.step += 1
        try:
            self.mlflow.log_metrics(_progress_metrics(state), step=self.step)
            running = next(
                (unit for unit in state.units.values() if unit.status == "running"), None
            )
            self.mlflow.set_tags(
                {
                    "current_phase": running.phase if running else "",
                    "current_unit": running.key if running else "",
                    "current_status": message,
                }
            )
        except Exception as exc:
            logger.warning("MLflow progress update failed: {}", exc)

    def close(self, state: ProgressState) -> None:
        """Upload final reports and close the active MLflow run."""
        if self.mlflow is None:
            return
        try:
            for name in ("progress.json", "REPORT.md"):
                path = self.run_dir / name
                if path.is_file():
                    self.mlflow.log_artifact(str(path))
            plots = self.run_dir / "plots"
            if plots.is_dir():
                self.mlflow.log_artifacts(str(plots), artifact_path="plots")
            self.mlflow.set_tag(
                "status", "complete" if state.overall_pct == 100.0 else "partial"
            )
            self.mlflow.end_run()
        except Exception as exc:
            logger.warning("MLflow finalization failed: {}", exc)


class WandbTracker:
    """Mirror progress to hosted Weights & Biases when ``WANDB_API_KEY`` is set."""

    def __init__(
        self,
        run_dir: Path,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """Start a W&B run, or remain disabled without an API key."""
        _load_env()
        self.run_dir = run_dir
        self.wandb: Any | None = None
        self.run: Any | None = None
        self.step = 0
        key = os.getenv("WANDB_API_KEY", "").strip()
        if not key:
            return
        try:
            import wandb

            project = os.getenv("WANDB_PROJECT", "").strip() or "rasa-skill-eval"
            entity = os.getenv("WANDB_ENTITY", "").strip() or None
            init_kwargs: dict[str, Any] = {
                "project": project,
                "name": run_dir.name,
                "config": {name: str(value) for name, value in (parameters or {}).items()},
                "reinit": "finish_previous",
            }
            if entity:
                init_kwargs["entity"] = entity
            try:
                init_kwargs["settings"] = wandb.Settings(start_method="thread")
            except Exception:
                init_kwargs.pop("settings", None)
            try:
                run = wandb.init(**init_kwargs)
            except Exception as exc:
                if entity is None and "entity" in str(exc).lower():
                    guessed = _wandb_default_entity(wandb)
                    if guessed:
                        logger.info("W&B using logged-in entity {}", guessed)
                        init_kwargs["entity"] = guessed
                        run = wandb.init(**init_kwargs)
                    else:
                        raise
                else:
                    raise
            self.wandb = wandb
            self.run = run
            url = str(getattr(run, "url", "") or "")
            logger.info("W&B tracking {}", url or f"project={project}")
        except Exception as exc:
            logger.warning("W&B tracking disabled: {}", exc)

    def update(self, state: ProgressState, message: str = "") -> None:
        """Log progress counters and the currently running unit to W&B."""
        if self.wandb is None:
            return
        self.step += 1
        try:
            self.wandb.log(_progress_metrics(state), step=self.step)
            running = next(
                (unit for unit in state.units.values() if unit.status == "running"), None
            )
            summary = getattr(self.run, "summary", None)
            if summary is not None:
                summary["current_phase"] = running.phase if running else ""
                summary["current_unit"] = running.key if running else ""
                summary["current_status"] = message
        except Exception as exc:
            logger.warning("W&B progress update failed: {}", exc)

    def close(self, state: ProgressState) -> None:
        """Upload final reports and finish the W&B run."""
        if self.wandb is None:
            return
        try:
            artifact = None
            if hasattr(self.wandb, "Artifact"):
                artifact = self.wandb.Artifact(f"{self.run_dir.name}-eval", type="evaluation")
                for name in ("progress.json", "REPORT.md"):
                    path = self.run_dir / name
                    if path.is_file():
                        artifact.add_file(str(path))
                plots = self.run_dir / "plots"
                if plots.is_dir() and hasattr(artifact, "add_dir"):
                    artifact.add_dir(str(plots), name="plots")
                self.wandb.log_artifact(artifact)
            if self.run is not None and getattr(self.run, "summary", None) is not None:
                self.run.summary["status"] = (
                    "complete" if state.overall_pct == 100.0 else "partial"
                )
            self.wandb.finish()
        except Exception as exc:
            logger.warning("W&B finalization failed: {}", exc)
            try:
                self.wandb.finish()
            except Exception:
                pass
