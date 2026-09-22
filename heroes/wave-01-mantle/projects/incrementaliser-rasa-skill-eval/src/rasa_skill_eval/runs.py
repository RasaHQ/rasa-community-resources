"""Create timestamped run output directories."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from rasa_skill_eval.config import load_config


def make_run_dir(name: str, runs_root: Path | None = None) -> Path:
    """Create ``runs/<name>_YYYYMMDD_HHMMSS/`` and return its path."""
    root = runs_root or load_config().runs_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    run_dir = root / f"{name}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def latest_run_dir(runs_root: Path | None = None) -> Path | None:
    """Return the newest dated evaluation folder that contains ``results.json``."""
    root = runs_root or load_config().runs_root()
    if not root.is_dir():
        return None
    prefixes = ("heroes_eval_", "run_all2_", "test_pipeline_")
    candidates = [
        path
        for path in root.iterdir()
        if path.is_dir()
        and path.name.startswith(prefixes)
        and (path / "results.json").is_file()
    ]
    if not candidates:
        return None

    def _stamp(path: Path) -> str:
        """Return the dated suffix so mixed prefixes sort by time, not name."""
        for prefix in prefixes:
            if path.name.startswith(prefix):
                return path.name[len(prefix) :]
        return path.name

    return max(candidates, key=_stamp)


def clone_run_dir(source: Path, runs_root: Path | None = None) -> Path:
    """Copy an existing run into a new timestamped sibling directory."""
    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Source run does not exist: {source}")
    dest = make_run_dir("heroes_eval", runs_root or source.parent)
    shutil.copytree(source, dest, dirs_exist_ok=True)
    return dest
