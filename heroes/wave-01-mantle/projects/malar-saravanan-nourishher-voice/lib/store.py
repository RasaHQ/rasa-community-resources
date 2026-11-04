"""Real, file-backed per-user data store for NourishHer.

Not a mock or seeded dataset — this is the app's actual persistence layer.
Each conversation's ``sender_id`` gets its own JSON profile document and a
JSONL meal/symptom log, so the five documented test profiles (and any real
user) stay isolated from one another across sessions.

Why files rather than project ``memory.yml``:
- Project memory is write-once per field per session in rasa-pro 3.20.0.dev4+
  (see ``memory.yml`` header). A profile the user can update/delete freely,
  a meal log that grows every turn, and saved plans that change over time all
  need many writes per session — project memory cannot express any of them.
- Condition *flags* still live in project memory because skill ``requires:``
  expressions can only read ``session.project.*``. This store holds the
  richer, freely-mutable preference data and all append-only history.

Writes are atomic (write-temp-then-rename) so a crash or a voice barge-in
mid-write can never leave a half-written profile on disk.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Not `Path(__file__).resolve().parent.parent`: Mantle runs the agent from a
# temp-copied snapshot of the project (see `rasa.mantle` snapshot execution),
# so `__file__` resolves inside that throwaway copy and every write would be
# lost on the next restart. The process's cwd stays pinned to the real
# project root for the life of the server (every Makefile target invokes
# `rasa`/`uv run` from here without `cd`), so anchor persistence to that.
DATA_DIR = Path.cwd() / "data"

# Fields the rich profile document accepts. Anything else is rejected by
# update_user_profile so a typo can't silently create a dead field.
PROFILE_FIELDS = {
    "name",
    "age_range",
    "region",              # country/region or cuisine preference
    "diet",                # dietary pattern, free text
    "allergies",           # list[str]
    "likes",               # list[str]
    "dislikes",            # list[str]
    "cooking_frequency",
    "cooking_time_weekdays_minutes",
    "meal_schedule",
    "budget",
    "goals",               # list[str], plain-language user intent
    "health_context",      # list[str], user-volunteered only
    "clinician_constraints",  # list[str], only if the user shares them
}

# Fields that hold lists; update_user_profile appends to these instead of
# overwriting, matching how a person adds "also, I don't like mushrooms".
LIST_FIELDS = {
    "allergies",
    "likes",
    "dislikes",
    "goals",
    "health_context",
    "clinician_constraints",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def user_id_from_context(context: Any) -> Optional[str]:
    """Best-effort extraction of the conversation's sender id from a ToolContext.

    The public ToolContext surface (rasa-pro 3.20.0.dev6) does not expose the
    sender id, so we read it off the underlying tracker handle defensively.
    Returns None if unavailable, and every store function degrades to the
    shared "default" key in that case rather than raising.
    """
    if context is None:
        return None
    try:
        return context._handle.tracker.sender_id  # noqa: SLF001
    except AttributeError:
        return None


def _safe_user_key(user_id: Optional[str]) -> str:
    """Return a filesystem-safe key for *user_id*.

    Falls back to "default" when no sender id is available (e.g. a tool run
    outside a live turn). Keeps only characters that are safe in a filename.
    """
    raw = (user_id or "default").strip() or "default"
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in raw)[:128]


def _profile_path(user_key: str) -> Path:
    return DATA_DIR / "profiles" / f"{user_key}.json"


def _log_path(user_key: str) -> Path:
    return DATA_DIR / "meal_logs" / f"{user_key}.jsonl"


def _plans_path(user_key: str) -> Path:
    return DATA_DIR / "meal_plans" / f"{user_key}.json"


def _atomic_write(path: Path, text: str) -> None:
    """Write *text* to *path* atomically (temp file + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #
def load_profile(user_id: Optional[str]) -> Dict[str, Any]:
    """Return the stored profile document, or an empty scaffold if none exists."""
    path = _profile_path(_safe_user_key(user_id))
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def set_profile_field(user_id: Optional[str], field: str, value: Any) -> Dict[str, Any]:
    """Set or append one profile field. Returns the updated profile.

    List-typed fields append (de-duplicated, case-insensitive); scalar fields
    overwrite. Raises KeyError for an unknown field.
    """
    if field not in PROFILE_FIELDS:
        raise KeyError(field)

    user_key = _safe_user_key(user_id)
    profile = load_profile(user_id)

    if field in LIST_FIELDS:
        current: List[str] = list(profile.get(field, []))
        new_items = value if isinstance(value, list) else [value]
        seen = {str(x).strip().lower() for x in current}
        for item in new_items:
            token = str(item).strip()
            if token and token.lower() not in seen:
                current.append(token)
                seen.add(token.lower())
        profile[field] = current
    else:
        profile[field] = value

    profile["updated_at"] = _now()
    _atomic_write(_profile_path(user_key), json.dumps(profile, indent=2))
    return profile


def delete_profile_field(
    user_id: Optional[str], field: str, value: Optional[Any] = None
) -> Dict[str, Any]:
    """Remove a whole field, or one item from a list field. Returns the profile."""
    if field not in PROFILE_FIELDS:
        raise KeyError(field)

    user_key = _safe_user_key(user_id)
    profile = load_profile(user_id)
    if field not in profile:
        return profile

    if value is not None and field in LIST_FIELDS:
        target = str(value).strip().lower()
        profile[field] = [x for x in profile[field] if str(x).strip().lower() != target]
    else:
        del profile[field]

    profile["updated_at"] = _now()
    _atomic_write(_profile_path(user_key), json.dumps(profile, indent=2))
    return profile


# --------------------------------------------------------------------------- #
# Meal / symptom log
# --------------------------------------------------------------------------- #
def append_log(user_id: Optional[str], entry: Dict[str, Any]) -> Dict[str, Any]:
    """Append one timestamped log entry (JSONL). Returns the stored entry."""
    user_key = _safe_user_key(user_id)
    record = {"timestamp": _now(), **entry}
    path = _log_path(user_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def read_log(user_id: Optional[str], since_days: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return log entries, newest last, optionally limited to the last N days."""
    path = _log_path(_safe_user_key(user_id))
    if not path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    cutoff = None
    if since_days is not None:
        cutoff = datetime.now(timezone.utc).timestamp() - since_days * 86400
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if cutoff is not None:
            try:
                ts = datetime.fromisoformat(rec["timestamp"]).timestamp()
            except (KeyError, ValueError):
                ts = None
            if ts is not None and ts < cutoff:
                continue
        entries.append(rec)
    return entries


# --------------------------------------------------------------------------- #
# Saved meal plans
# --------------------------------------------------------------------------- #
def save_plan(user_id: Optional[str], date: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a meal plan keyed by date (one plan per date). Returns the plan."""
    user_key = _safe_user_key(user_id)
    path = _plans_path(user_key)
    plans: Dict[str, Any] = {}
    if path.exists():
        try:
            plans = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            plans = {}
    record = {"saved_at": _now(), **plan}
    plans[date] = record
    _atomic_write(path, json.dumps(plans, indent=2))
    return record


def get_plan(user_id: Optional[str], date: str) -> Optional[Dict[str, Any]]:
    """Return the saved plan for *date*, or None."""
    path = _plans_path(_safe_user_key(user_id))
    if not path.exists():
        return None
    try:
        plans = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return plans.get(date)
