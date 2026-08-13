#!/usr/bin/env python3
"""Bump rasa-pro across all discovered community resource projects.

Updates:
  - RASA_PRO_VERSION (when --version is provided)
  - each project's pyproject.toml pin
  - each project's uv.lock (via `uv lock --prerelease=allow`)
  - README.md / AGENTS.md version strings

Usage:
    python scripts/migrate_rasa_pro.py
    python scripts/migrate_rasa_pro.py --version 3.19.0.dev5
    python scripts/migrate_rasa_pro.py --version 3.19.0.dev5 --skip-lock
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rasa_projects import (  # noqa: E402
    ASSESSED_ON_RE,
    NOTES_HEADING_RE,
    RASA_PRO_DEP_RE,
    REPO_ROOT,
    VERIFIED_WITH_RE,
    VERSION_FILE,
    VERSION_TOKEN,
    discover_projects,
    read_expected_version,
    read_pyproject_pin,
)

# Broader prose pin: rasa-pro==X.Y.Z or rasa-pro X.Y.Z (not only Verified with)
PROSE_EQ_RE = re.compile(rf"(rasa-pro==)(?P<version>{VERSION_TOKEN})")
PROSE_SPACE_RE = re.compile(rf"(rasa-pro\s+)(?P<version>{VERSION_TOKEN})")


def _replace_pin_in_pyproject(text: str, new_version: str) -> tuple[str, str | None, bool]:
    match = RASA_PRO_DEP_RE.search(text)
    if not match:
        return text, None, False
    old = match.group("version")
    if old == new_version:
        return text, old, False
    updated = RASA_PRO_DEP_RE.sub(
        lambda m: f"{m.group('prefix')}{new_version}{m.group('suffix')}",
        text,
        count=1,
    )
    return updated, old, True


def _rewrite_doc_text(
    text: str,
    old_version: str | None,
    new_version: str,
    *,
    touch_assessed_on: bool,
    pin_changed: bool,
) -> tuple[str, bool]:
    changed = False

    def sub_verified(m: re.Match[str]) -> str:
        nonlocal changed
        if m.group("version") != new_version:
            changed = True
        return f"{m.group(1)}{new_version}"

    def sub_notes(m: re.Match[str]) -> str:
        nonlocal changed
        # Only rewrite headings that look like version pins we manage.
        current = m.group("version")
        if old_version and current == old_version and current != new_version:
            changed = True
            return f"{m.group(1)}{new_version}"
        if current != new_version and re.fullmatch(r"\d+\.\d+\.\d+(?:\.dev\d+)?", current):
            changed = True
            return f"{m.group(1)}{new_version}"
        return m.group(0)

    def sub_eq(m: re.Match[str]) -> str:
        nonlocal changed
        if m.group("version") != new_version:
            changed = True
        return f"{m.group(1)}{new_version}"

    def sub_space(m: re.Match[str]) -> str:
        nonlocal changed
        # Avoid rewriting unrelated "rasa-pro Developer Edition" style phrases:
        # only rewrite when the token after rasa-pro looks like a version.
        if not re.match(r"\d", m.group("version")):
            return m.group(0)
        if m.group("version") != new_version:
            changed = True
        return f"{m.group(1)}{new_version}"

    text = VERIFIED_WITH_RE.sub(sub_verified, text)
    text = NOTES_HEADING_RE.sub(sub_notes, text)
    text = PROSE_EQ_RE.sub(sub_eq, text)
    # Verified-with already handled; still catch leftover "rasa-pro X.Y.Z" in body.
    text = PROSE_SPACE_RE.sub(sub_space, text)

    if touch_assessed_on and pin_changed:
        today = date.today().isoformat()

        def sub_assessed(m: re.Match[str]) -> str:
            nonlocal changed
            if m.group("date") != today:
                changed = True
            return f"{m.group(1)}{today}"

        text = ASSESSED_ON_RE.sub(sub_assessed, text, count=1)

    return text, changed


def _update_docs(project_path: Path, old_version: str | None, new_version: str, touch_assessed_on: bool, pin_changed: bool) -> list[str]:
    updated_files: list[str] = []
    for name in ("README.md", "AGENTS.md"):
        path = project_path / name
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        rewritten, changed = _rewrite_doc_text(
            original,
            old_version,
            new_version,
            touch_assessed_on=touch_assessed_on,
            pin_changed=pin_changed,
        )
        if changed and rewritten != original:
            path.write_text(rewritten, encoding="utf-8")
            updated_files.append(name)
    return updated_files


def _run_uv_lock(project_path: Path) -> None:
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv not found on PATH")
    subprocess.run(
        [uv, "lock", "--prerelease=allow"],
        cwd=project_path,
        check=True,
    )


def _write_version_file(version: str) -> None:
    VERSION_FILE.write_text(version + "\n", encoding="utf-8")


def migrate_project(
    project_path: Path,
    new_version: str,
    *,
    skip_lock: bool,
    touch_assessed_on: bool,
) -> dict[str, object]:
    from rasa_projects import Project

    project = Project(project_path)
    result: dict[str, object] = {
        "path": project.rel,
        "changed": False,
        "old_version": None,
        "docs": [],
        "locked": False,
        "error": None,
    }
    try:
        text = project.pyproject.read_text(encoding="utf-8")
        updated, old_version, pin_changed = _replace_pin_in_pyproject(text, new_version)
        result["old_version"] = old_version
        if old_version is None:
            raise RuntimeError("no rasa-pro== pin found in pyproject.toml")
        if pin_changed:
            project.pyproject.write_text(updated, encoding="utf-8")
            result["changed"] = True

        docs = _update_docs(
            project.path,
            old_version,
            new_version,
            touch_assessed_on=touch_assessed_on,
            pin_changed=pin_changed or old_version != new_version,
        )
        if docs:
            result["docs"] = docs
            result["changed"] = True

        # Always refresh lock when pin differs from target or lock may be stale.
        if not skip_lock:
            _run_uv_lock(project.path)
            result["locked"] = True
            result["changed"] = True
    except Exception as exc:  # noqa: BLE001 - collect per-project failures
        result["error"] = str(exc)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        default=None,
        help="Target rasa-pro version (default: RASA_PRO_VERSION; also writes that file when set)",
    )
    parser.add_argument(
        "--skip-lock",
        action="store_true",
        help="Rewrite pins/docs only; do not run uv lock",
    )
    parser.add_argument(
        "--no-touch-assessed-on",
        action="store_true",
        help="Do not refresh Assessed on dates when pins change",
    )
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        help="Limit to one or more repo-relative project paths (repeatable)",
    )
    args = parser.parse_args()

    if args.version:
        new_version = args.version.strip()
        _write_version_file(new_version)
    else:
        new_version = read_expected_version()

    projects = discover_projects()
    if args.project:
        wanted = {p.strip().rstrip("/") for p in args.project}
        projects = [p for p in projects if p.rel in wanted]
        missing = wanted - {p.rel for p in projects}
        if missing:
            print(f"Unknown project(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 1

    print(f"Migrating {len(projects)} project(s) → rasa-pro=={new_version}")
    print(f"Repo: {REPO_ROOT}")
    print()

    failed = 0
    changed = 0
    for project in projects:
        before = read_pyproject_pin(project)
        result = migrate_project(
            project.path,
            new_version,
            skip_lock=args.skip_lock,
            touch_assessed_on=not args.no_touch_assessed_on,
        )
        if result["error"]:
            failed += 1
            print(f"[FAIL] {result['path']}: {result['error']}")
            continue
        docs = ", ".join(result["docs"]) if result["docs"] else "—"
        lock_note = "lock refreshed" if result["locked"] else "lock skipped"
        if result["changed"] or before != new_version:
            changed += 1
            print(
                f"[OK]   {result['path']}: {before} → {new_version}  "
                f"(docs: {docs}; {lock_note})"
            )
        else:
            print(f"[SKIP] {result['path']}: already on {new_version}  ({lock_note})")

    # Also refresh the example Verified-with line in the root README if present.
    root_readme = REPO_ROOT / "README.md"
    if root_readme.is_file():
        text = root_readme.read_text(encoding="utf-8")
        rewritten, doc_changed = _rewrite_doc_text(
            text,
            None,
            new_version,
            touch_assessed_on=False,
            pin_changed=False,
        )
        if doc_changed and rewritten != text:
            root_readme.write_text(rewritten, encoding="utf-8")
            print("[OK]   README.md: Verified with example updated")

    print()
    print(f"Done. changed={changed} failed={failed} target={new_version}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
