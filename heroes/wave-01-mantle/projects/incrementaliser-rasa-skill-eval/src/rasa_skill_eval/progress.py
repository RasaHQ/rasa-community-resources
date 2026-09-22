"""Durable, resume-aware progress state for long evaluation runs."""

from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from rasa_skill_eval.models import ProgressState, ProgressUnit
from rasa_skill_eval.nvidia_llm import nvidia_key_configured
from rasa_skill_eval.persist import atomic_write_json, load_json_object
from rasa_skill_eval.scenarios import load_scenarios, scenarios_dir
from rasa_skill_eval.skill_io import discover_skill_dirs

PHASES = ("layer_a", "layer_b", "deepeval", "finalize")
_DONE_STATUSES = frozenset({"complete"})
_DEEPEVAL_LLM_METRICS = (
    "task_completion",
    "answer_relevancy",
    "g_eval_tool_correctness",
)


def _nvidia_command_ok(nvidia: list[Any], skill_id: str, command: str) -> bool:
    """True when ``results.json`` has a successful SkillEvaluator command row."""
    for row in nvidia:
        if not isinstance(row, dict):
            continue
        if row.get("skill_id") != skill_id or row.get("command") != command:
            continue
        if row.get("skipped"):
            continue
        if command == "quality-check":
            return row.get("quality_score") is not None
        if command == "rubric-eval":
            return row.get("rubric_score") is not None
        return True
    return False


class ProgressObserver(Protocol):
    """Receive progress snapshots without owning completion semantics."""

    def update(self, state: ProgressState, message: str = "") -> None:
        """Render or export one progress snapshot."""

    def close(self, state: ProgressState) -> None:
        """Release observer resources after the final snapshot."""


class ProgressManager:
    """Persist progress units and fan updates out to optional observers."""

    def __init__(self, run_dir: Path, observers: list[ProgressObserver] | None = None) -> None:
        """Load an existing manifest or initialize one for ``run_dir``."""
        self.run_dir = run_dir
        self.path = run_dir / "progress.json"
        raw = load_json_object(self.path)
        now = _now()
        self.state = (
            ProgressState.model_validate(raw)
            if raw
            else ProgressState(run_id=run_dir.name, started_at=now, updated_at=now)
        )
        if self.state.run_id != run_dir.name:
            self.state.run_id = run_dir.name
            self.state.units.pop("report:finalize", None)
        self.observers = observers or []
        self._recalculate()

    def seed_from_run(self, config: Any) -> None:
        """Plan configured work and infer completed units from durable results."""
        payload = load_json_object(self.run_dir / "results.json")
        nvidia = payload.get("nvidia") or []
        deltas = {str(row.get("skill_id")) for row in payload.get("improver") or []}
        units: list[ProgressUnit] = []
        for agent_id in ("rasano", "personalization"):
            entry = config.corpora.get(agent_id)
            if entry is None:
                continue
            root = config.resolve(entry.dest)
            scan = root / "skills" if (root / "skills").is_dir() else root
            for skill_dir in discover_skill_dirs(scan):
                skill_id = f"{agent_id}/{skill_dir.name.replace('_', '-').lower()}"
                required = ["quality-check", "validate"]
                if nvidia_key_configured():
                    required.append("rubric-eval")
                base_ok = all(
                    _nvidia_command_ok(nvidia, skill_id, command) for command in required
                )
                improved_ok = all(
                    _nvidia_command_ok(nvidia, f"{skill_id}#improved", command)
                    for command in required
                )
                status = (
                    "complete"
                    if base_ok and improved_ok and skill_id in deltas
                    else "pending"
                )
                units.append(
                    ProgressUnit(key=f"skill:{skill_id}", phase="layer_a", status=status)
                )

        tsr = payload.get("tsr") or []
        deep = payload.get("deepeval") or []
        scenario_root = self.run_dir / "eval" / "scenarios"
        if not scenario_root.is_dir():
            scenario_root = scenarios_dir(config.resolve(config.paths.data_dir))
        repeats = max(1, config.eval.repeats)
        for model in config.llm.agents:
            model_id = model.path_id()
            for agent_id in ("rasano", "personalization"):
                for spec in load_scenarios(scenario_root, agent_id=agent_id):
                    scenario_id = str(spec["id"])
                    for arm in ("native", "improved"):
                        for repeat in range(repeats):
                            identity = (agent_id, model_id, arm, scenario_id, repeat)
                            row = next(
                                (
                                    item
                                    for item in tsr
                                    if (
                                        item.get("agent_id"),
                                        item.get("model_id"),
                                        item.get("arm"),
                                        item.get("scenario_id"),
                                        item.get("repeat"),
                                    )
                                    == identity
                                ),
                                None,
                            )
                            status = (
                                "pending"
                                if row is None
                                else ("skipped" if row.get("skipped") else "complete")
                            )
                            suffix = f"{agent_id}/{model_id}/{arm}/{scenario_id}/{repeat}"
                            units.append(
                                ProgressUnit(
                                    key=f"scenario:{suffix}",
                                    phase="layer_b",
                                    status=status,
                                )
                            )
                            judged_rows = [
                                item
                                for item in deep
                                if (
                                    item.get("agent_id"),
                                    item.get("model_id"),
                                    item.get("arm"),
                                    item.get("scenario_id"),
                                    item.get("repeat"),
                                )
                                == identity
                            ]
                            scored_metrics = {
                                str(item.get("metric"))
                                for item in judged_rows
                                if item.get("score") is not None and not item.get("skipped")
                            }
                            deepeval_status = (
                                "complete"
                                if all(metric in scored_metrics for metric in _DEEPEVAL_LLM_METRICS)
                                else "pending"
                            )
                            units.append(
                                ProgressUnit(
                                    key=f"deepeval:{suffix}",
                                    phase="deepeval",
                                    status=deepeval_status,
                                )
                            )
        units.append(
            ProgressUnit(key="report:finalize", phase="finalize", status="pending")
        )
        self.plan(units)
        for unit in units:
            stored = self.state.units[unit.key]
            stored.status = unit.status
            stored.phase = unit.phase
        self._publish()

    def plan(self, units: list[ProgressUnit]) -> None:
        """Add expected units while preserving statuses loaded during resume."""
        for unit in units:
            self.state.units.setdefault(unit.key, unit)
        self._publish()

    def mark(
        self,
        key: str,
        phase: str,
        status: str,
        *,
        message: str = "",
        **details: Any,
    ) -> None:
        """Create or update one unit and publish the resulting snapshot."""
        unit = self.state.units.get(key) or ProgressUnit(key=key, phase=phase)
        unit.phase = phase
        unit.status = status
        unit.details.update(details)
        self.state.units[key] = unit
        self._publish(message)

    def note(self, message: str) -> None:
        """Publish a status message without changing completion."""
        self._publish(message)

    def close(self) -> None:
        """Publish once and close every observer."""
        self._publish()
        for observer in self.observers:
            observer.close(self.state)

    def _publish(self, message: str = "") -> None:
        """Recalculate, atomically persist, then notify observers."""
        self._recalculate()
        atomic_write_json(self.path, self.state.model_dump(mode="json"))
        for observer in self.observers:
            observer.update(self.state, message)

    def _recalculate(self) -> None:
        """Derive phase and overall totals from the unit map."""
        completed = 0
        total = len(self.state.units)
        for phase in PHASES:
            units = [unit for unit in self.state.units.values() if unit.phase == phase]
            done = sum(unit.status in _DONE_STATUSES for unit in units)
            setattr(
                self.state,
                phase,
                {
                    "done": done,
                    "total": len(units),
                    "pct": round(100 * done / len(units), 1) if units else 0.0,
                },
            )
            completed += done
        self.state.overall_pct = round(100 * completed / total, 1) if total else 0.0
        self.state.updated_at = _now()


_CURRENT: ContextVar[ProgressManager | None] = ContextVar("progress_manager", default=None)


def set_current_progress(manager: ProgressManager | None) -> Token[ProgressManager | None]:
    """Set the manager used by pipeline modules in the current context."""
    return _CURRENT.set(manager)


def reset_current_progress(token: Token[ProgressManager | None]) -> None:
    """Restore the previous context-local progress manager."""
    _CURRENT.reset(token)


def current_progress() -> ProgressManager | None:
    """Return the current progress manager, if progress is enabled."""
    return _CURRENT.get()


def progress_mark(key: str, phase: str, status: str, **details: Any) -> None:
    """Update the current manager when one is active."""
    manager = current_progress()
    if manager is not None:
        manager.mark(key, phase, status, **details)


def _now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(UTC).isoformat()
