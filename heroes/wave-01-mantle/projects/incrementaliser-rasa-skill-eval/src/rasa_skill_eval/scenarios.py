"""Load eval scenario YAML from ``data/eval/scenarios`` (per-agent folders)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rasa_skill_eval import PROJECT_ROOT


def scenarios_dir(config_data_dir: Path | None = None) -> Path:
    """Return the directory of committed scenario files."""
    root = config_data_dir or (PROJECT_ROOT / "data")
    return root / "eval" / "scenarios"


def load_scenarios(
    directory: Path | None = None,
    *,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    """Load every ``*.yml`` scenario, optionally filtered by ``agent`` field."""
    folder = directory or scenarios_dir()
    if not folder.is_dir():
        return []
    items: list[dict[str, Any]] = []
    paths = sorted(folder.rglob("*.yml")) if folder.is_dir() else []
    for path in paths:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        if "agent" not in raw:
            # Infer from parent folder name when present (rasano/, personalization/).
            parent = path.parent.name
            if parent in {"rasano", "personalization"}:
                raw["agent"] = parent
            else:
                raw["agent"] = "rasano"
        if agent_id is not None and str(raw.get("agent")) != agent_id:
            continue
        items.append(raw)
    items.sort(key=lambda row: str(row.get("id")))
    return items
