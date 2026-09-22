"""Atomic JSON writes, identity merge, and content hashes for resume."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from rasa_skill_eval.models import ImproverDelta, IntegrationIssue, TsrRun

T = TypeVar("T")


def atomic_write_json(path: Path, payload: Any) -> None:
    """Write JSON via a sibling temp file, then replace the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object, or ``{}`` when the file is missing or invalid."""
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def file_sha256(path: Path) -> str:
    """Return the hex digest of one file."""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def text_sha256(*parts: str) -> str:
    """Hash concatenated UTF-8 strings separated by NUL."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def tree_sha256(
    root: Path,
    *,
    skip_dir_names: frozenset[str] | set[str] | None = None,
    skip_file_names: frozenset[str] | set[str] | None = None,
) -> str:
    """Hash files under ``root`` in relative-path order."""
    skip_dirs = skip_dir_names or frozenset()
    skip_files = skip_file_names or frozenset()
    digest = hashlib.sha256()
    if not root.is_dir():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.name in skip_files:
            continue
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def tsr_identity(row: TsrRun) -> tuple[str, str, str, str, int]:
    """Stable key for one scenario repeat on one agent/model/arm."""
    return (row.agent_id, row.model_id, row.arm, row.scenario_id, row.repeat)


def issue_identity(issue: IntegrationIssue) -> tuple[str, str, str, str, str]:
    """Stable key so resume does not duplicate the same failure."""
    return (issue.code, issue.agent_id, issue.model_id, issue.arm, issue.event)


def upsert_by_key(
    existing: list[T],
    incoming: list[T],
    key_fn: Callable[[T], object],
) -> list[T]:
    """Replace items that share ``key_fn``; append new keys in incoming order."""
    by_key: dict[object, T] = {key_fn(item): item for item in existing}
    order = list(by_key.keys())
    for item in incoming:
        key = key_fn(item)
        if key not in by_key:
            order.append(key)
        by_key[key] = item
    return [by_key[key] for key in order]


def upsert_tsr(existing: list[TsrRun], incoming: list[TsrRun]) -> list[TsrRun]:
    """Merge TSR rows by scenario identity."""
    return upsert_by_key(existing, incoming, tsr_identity)


def upsert_issues(
    existing: list[IntegrationIssue],
    incoming: list[IntegrationIssue],
) -> list[IntegrationIssue]:
    """Merge integration issues by code and location."""
    return upsert_by_key(existing, incoming, issue_identity)


def improver_mode_label(deltas: list[ImproverDelta], *, client_available: bool) -> str:
    """Describe how skills were actually rewritten this run."""
    if not deltas:
        return "llm" if client_available else "heuristic"
    modes = {item.mode for item in deltas}
    if modes <= {"llm", "cached"}:
        return "llm"
    if modes == {"heuristic"}:
        return "heuristic"
    if modes == {"cached"}:
        return "cached"
    return "mixed"


def improver_mode_counts(deltas: list[ImproverDelta]) -> dict[str, int]:
    """Count deltas by rewrite mode."""
    counts = {"llm": 0, "heuristic": 0, "cached": 0, "other": 0}
    for item in deltas:
        if item.mode in counts:
            counts[item.mode] += 1
        else:
            counts["other"] += 1
    return counts


def coverage_path(run_dir: Path) -> Path:
    """Return the run-local coverage manifest path."""
    return run_dir / "coverage.json"


def load_coverage(run_dir: Path) -> dict[str, Any]:
    """Load ``coverage.json`` units and summary."""
    payload = load_json_object(coverage_path(run_dir))
    units = payload.get("units")
    if not isinstance(units, dict):
        units = {}
    return {"units": units, **{k: v for k, v in payload.items() if k != "units"}}


def save_coverage(run_dir: Path, coverage: dict[str, Any]) -> None:
    """Atomically persist the coverage manifest."""
    atomic_write_json(coverage_path(run_dir), coverage)


def set_coverage_unit(
    coverage: dict[str, Any],
    key: str,
    *,
    status: str,
    kind: str,
    reason: str | None = None,
    pid: int | None = None,
    log_path: str | None = None,
    model_id: str = "",
    agent_id: str = "",
    arm: str = "",
) -> None:
    """Insert or replace one coverage unit."""
    units = coverage.setdefault("units", {})
    if not isinstance(units, dict):
        units = {}
        coverage["units"] = units
    units[key] = {
        "kind": kind,
        "key": key,
        "status": status,
        "reason": reason,
        "pid": pid,
        "log_path": log_path,
        "model_id": model_id,
        "agent_id": agent_id,
        "arm": arm,
    }


def unit_status(coverage: dict[str, Any], key: str) -> str | None:
    """Return a unit status, or None when the unit was never recorded."""
    units = coverage.get("units")
    if not isinstance(units, dict):
        return None
    row = units.get(key)
    if not isinstance(row, dict):
        return None
    status = row.get("status")
    return str(status) if status else None
