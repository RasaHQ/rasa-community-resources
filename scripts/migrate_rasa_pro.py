#!/usr/bin/env python3
"""Bump rasa-pro across every discovered community resource project.

Updates, in order:
  1. each project's pyproject.toml pin (and its `[tool.uv] prerelease` switch)
  2. each project's uv.lock, via `uv lock`, then verifies what resolved
  3. README.md / AGENTS.md version strings, per project and at the repo root
  4. RASA_PRO_VERSION — written last, only once the sweep succeeded

Usage:
    python scripts/migrate_rasa_pro.py                      # to RASA_PRO_VERSION
    python scripts/migrate_rasa_pro.py --latest             # to newest stable on PyPI
    python scripts/migrate_rasa_pro.py --version 3.19.1
    python scripts/migrate_rasa_pro.py --version 3.19.1 --dry-run
    python scripts/migrate_rasa_pro.py --version 3.19.1 --skip-lock
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
    ECHO_PIN_RE,
    MAKE_VERSION_RE,
    NOTES_HEADING_RE,
    PROSE_EQ_RE,
    PROSE_SPACE_RE,
    RASA_PRO_DEP_RE,
    REPO_DOCS,
    REPO_ROOT,
    UV_PRERELEASE_FLAG_RE,
    VERIFIED_WITH_RE,
    REQUIRED_ENGINE_MODULE,
    IndexUnavailable,
    Project,
    discover_projects,
    is_prerelease,
    is_valid_version,
    latest_version,
    release_carries_engine,
    read_expected_version,
    read_lock_version,
    read_version_line,
    read_pyproject_pin,
    uv_prerelease_args,
    version_exists,
    write_version_file,
)


def _c(code: str) -> str:
    return code if sys.stdout.isatty() else ""


GREEN, YELLOW, RED, BLUE, DIM, RESET = (
    _c("\033[92m"),
    _c("\033[93m"),
    _c("\033[91m"),
    _c("\033[94m"),
    _c("\033[2m"),
    _c("\033[0m"),
)


# ------------------------------------------------------------------------------
# pyproject.toml
# ------------------------------------------------------------------------------


def _replace_pin(text: str, new_version: str) -> tuple[str, str | None, bool]:
    match = RASA_PRO_DEP_RE.search(text)
    if not match:
        return text, None, False
    old = match.group("version")
    if old == new_version:
        return text, old, False
    updated = RASA_PRO_DEP_RE.sub(
        lambda m: f"{m.group('prefix')}{new_version}{m.group('suffix')}", text, count=1
    )
    return updated, old, True


def _tool_uv_span(text: str) -> tuple[int, int] | None:
    """Character span of the `[tool.uv]` table body, header included."""
    header = re.search(r"(?m)^\[tool\.uv\][ \t]*\r?\n", text)
    if not header:
        return None
    nxt = re.compile(r"(?m)^\[").search(text, header.end())
    return header.start(), (nxt.start() if nxt else len(text))


def _apply_prerelease_setting(text: str, new_version: str) -> tuple[str, str | None]:
    """Keep `[tool.uv] prerelease` in step with the target pin.

    A stable pin should not carry `prerelease = "allow"`: that flag applies to
    the whole resolution, so it silently lets every *other* dependency resolve
    to a prerelease too. A dev/rc pin cannot resolve without it.
    """
    span = _tool_uv_span(text)
    want_allow = is_prerelease(new_version)
    line_re = re.compile(r"(?m)^[ \t]*prerelease[ \t]*=[ \t]*[\"'][^\"']+[\"'][ \t]*\r?\n")

    if span is None:
        if not want_allow:
            return text, None
        # No [tool.uv] table at all — add one before [build-system] if present.
        block = '[tool.uv]\nprerelease = "allow"\n\n'
        anchor = re.search(r"(?m)^\[build-system\]", text)
        if anchor:
            return text[: anchor.start()] + block + text[anchor.start() :], "added"
        return text.rstrip("\n") + "\n\n" + block, "added"

    start, end = span
    body = text[start:end]
    has_line = bool(line_re.search(body))

    if want_allow and not has_line:
        header_end = body.index("\n") + 1
        body = body[:header_end] + 'prerelease = "allow"\n' + body[header_end:]
        return text[:start] + body + text[end:], "added"

    if not want_allow and has_line:
        body = line_re.sub("", body, count=1)
        # Drop the table entirely if removing that key emptied it.
        remainder = body.split("\n", 1)[1] if "\n" in body else ""
        if not remainder.strip():
            return text[:start] + text[end:], "removed (table dropped)"
        return text[:start] + body + text[end:], "removed"

    return text, None


# ------------------------------------------------------------------------------
# Markdown / Makefile prose
# ------------------------------------------------------------------------------


def rewrite_version_text(
    text: str,
    old_version: str | None,
    new_version: str,
    *,
    touch_assessed_on: bool = False,
) -> tuple[str, bool]:
    changed = False

    def bump(match: re.Match[str]) -> str:
        nonlocal changed
        if match.group("version") != new_version:
            changed = True
        return f"{match.group(1)}{new_version}"

    def bump_notes(match: re.Match[str]) -> str:
        nonlocal changed
        current = match.group("version")
        if current == new_version:
            return match.group(0)
        # Only rewrite headings that look like a pin we manage.
        if old_version and current != old_version:
            return match.group(0)
        changed = True
        return f"{match.group(1)}{new_version}"

    def bump_echo(match: re.Match[str]) -> str:
        nonlocal changed
        if match.group("version") != new_version:
            changed = True
        return f"{match.group(1)}{new_version}{match.group(3)}"

    text = VERIFIED_WITH_RE.sub(bump, text)
    text = NOTES_HEADING_RE.sub(bump_notes, text)
    text = PROSE_EQ_RE.sub(bump, text)
    text = PROSE_SPACE_RE.sub(bump, text)
    text = MAKE_VERSION_RE.sub(bump, text)
    text = ECHO_PIN_RE.sub(bump_echo, text)

    if touch_assessed_on:
        today = date.today().isoformat()

        def bump_date(match: re.Match[str]) -> str:
            nonlocal changed
            if match.group("date") != today:
                changed = True
            return f"{match.group(1)}{today}"

        text = ASSESSED_ON_RE.sub(bump_date, text, count=1)

    return text, changed


def rewrite_prerelease_flags(text: str, new_version: str) -> str:
    """Toggle `uv sync|lock --prerelease=allow` to match the target pin.

    Applied to per-project Makefiles and docs so published install commands stay
    truthful. Deliberately not applied to the root Makefile, which derives the
    flag from the pin at run time.
    """
    want_allow = is_prerelease(new_version)

    def swap(match: re.Match[str]) -> str:
        cmd = match.group("cmd")
        return f"{cmd} --prerelease=allow" if want_allow else cmd

    return UV_PRERELEASE_FLAG_RE.sub(swap, text)


def _rewrite_doc(
    path: Path,
    old_version: str | None,
    new_version: str,
    *,
    touch_assessed_on: bool,
    dry_run: bool,
    prerelease_flags: bool = False,
) -> bool:
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    rewritten, changed = rewrite_version_text(
        original, old_version, new_version, touch_assessed_on=touch_assessed_on
    )
    if prerelease_flags:
        rewritten = rewrite_prerelease_flags(rewritten, new_version)
    if rewritten == original:
        return False
    if not dry_run:
        path.write_text(rewritten, encoding="utf-8")
    return True


# ------------------------------------------------------------------------------
# uv
# ------------------------------------------------------------------------------


def _run_uv_lock(project_path: Path, new_version: str, *, upgrade: bool = False) -> None:
    """Re-resolve `uv.lock`.

    `upgrade=True` forces a full re-resolution rather than the default, which
    keeps any existing pin that still satisfies the constraints. That default is
    wrong when the prerelease allowance is being *removed*: prerelease versions
    locked under the old permission still satisfy their constraints, so they
    survive a plain `uv lock` and a nominally stable project keeps shipping
    release candidates.
    """
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv not found on PATH")
    cmd = [uv, "lock", *(["--upgrade"] if upgrade else []), *uv_prerelease_args(new_version)]
    proc = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = " | ".join(detail[-3:]) if detail else f"exit {proc.returncode}"
        raise RuntimeError(f"uv lock failed: {tail}")


# ------------------------------------------------------------------------------
# Per-project migration
# ------------------------------------------------------------------------------


def migrate_project(
    project: Project,
    new_version: str,
    *,
    skip_lock: bool,
    touch_assessed_on: bool,
    dry_run: bool,
    upgrade: bool = False,
) -> dict[str, object]:
    result: dict[str, object] = {
        "path": project.rel,
        "old_version": None,
        "pin_changed": False,
        "prerelease": None,
        "docs": [],
        "locked": False,
        "upgraded": False,
        "lock_version": None,
        "error": None,
    }
    try:
        text = project.pyproject.read_text(encoding="utf-8")
        updated, old_version, pin_changed = _replace_pin(text, new_version)
        result["old_version"] = old_version
        if old_version is None:
            raise RuntimeError("no rasa-pro== pin found in pyproject.toml")

        updated, prerelease_note = _apply_prerelease_setting(updated, new_version)
        result["prerelease"] = prerelease_note
        result["pin_changed"] = pin_changed

        if (pin_changed or prerelease_note) and not dry_run:
            project.pyproject.write_text(updated, encoding="utf-8")

        # Project docs plus the project's own Makefile: all of these quote the
        # install commands a reader will copy, so the prerelease flag in them
        # has to track the pin too.
        targets = [*project.docs(), project.path / "Makefile"]
        result["docs"] = [
            target.name
            for target in targets
            if _rewrite_doc(
                target,
                old_version,
                new_version,
                touch_assessed_on=touch_assessed_on and old_version != new_version,
                dry_run=dry_run,
                prerelease_flags=True,
            )
        ]

        if not skip_lock and not dry_run:
            # Dropping the allowance requires a full re-resolve; see _run_uv_lock.
            force_upgrade = upgrade or (prerelease_note or "").startswith("removed")
            _run_uv_lock(project.path, new_version, upgrade=force_upgrade)
            result["locked"] = True
            result["upgraded"] = force_upgrade
            resolved = read_lock_version(project)
            result["lock_version"] = resolved
            if resolved != new_version:
                raise RuntimeError(
                    f"uv.lock resolved rasa-pro=={resolved!r}, expected {new_version!r}"
                )
    except Exception as exc:  # noqa: BLE001 — collect per-project failures
        result["error"] = str(exc)
    return result


# ------------------------------------------------------------------------------
# Target resolution
# ------------------------------------------------------------------------------


def _usage_error(message: str) -> "SystemExit":
    """Exit 2 for a bad invocation, matching argparse.

    Exit 1 is reserved for a well-formed request that failed — the release does
    not exist, the index is unreachable, a project would not migrate. Keeping
    those apart lets a caller tell "you typed it wrong" from "it did not work".
    """
    print(f"error: {message}", file=sys.stderr)
    return SystemExit(2)


def resolve_target(args: argparse.Namespace) -> tuple[str, bool]:
    """Return (version, came_from_cli) or raise SystemExit with a clear message."""
    if args.latest:
        if args.version:
            raise _usage_error("pass --latest or --version, not both")
        prefix = args.match if args.match is not None else read_version_line()
        try:
            version = latest_version(
                allow_prerelease=args.allow_prerelease, prefix=prefix
            )
        except IndexUnavailable as exc:
            raise SystemExit(f"error: {exc}") from exc
        kind = "prerelease" if is_prerelease(version) else "stable"
        within = f" within line {prefix!r}" if prefix else ""
        print(f"Resolved newest {kind} rasa-pro on PyPI{within}: {GREEN}{version}{RESET}")
        if prefix:
            print(f"{DIM}  (line pinned by RASA_PRO_VERSION_LINE; --match '' to ignore){RESET}")
        return version, True

    if args.version:
        version = args.version.strip()
        if not is_valid_version(version):
            raise _usage_error(f"{version!r} is not a valid version string")
        return version, True

    return read_expected_version(), False


def verify_on_index(version: str, *, skip: bool) -> None:
    """Fail before mutating anything if the target does not exist upstream."""
    if skip:
        return
    try:
        if not version_exists(version):
            raise SystemExit(
                f"error: rasa-pro=={version} is not on the index.\n"
                f"       Re-run with --no-index-check to bump pins anyway."
            )
    except IndexUnavailable as exc:
        print(f"{YELLOW}warning: index check skipped — {exc}{RESET}", file=sys.stderr)


def verify_engine_support(version: str, *, skip: bool) -> None:
    """Refuse a target that cannot run anything in this catalog.

    `--latest` is fenced in by RASA_PRO_VERSION_LINE, but an explicit
    `--version` used to walk straight past it. Bumping to a release without the
    engine module rewrites every pin, lock and doc to something that fails at
    import, so the target is inspected before any file is touched.
    """
    if skip:
        return
    line = read_version_line()
    if not line or version.startswith(line):
        return

    module = REQUIRED_ENGINE_MODULE.rstrip("/").replace("/", ".")
    try:
        carries = release_carries_engine(version)
    except IndexUnavailable as exc:
        raise SystemExit(
            f"error: could not verify that rasa-pro=={version} ships {module} — {exc}\n"
            f"       It is outside the release line {line!r} in RASA_PRO_VERSION_LINE.\n"
            f"       Re-run with --allow-missing-engine to bump anyway."
        ) from exc

    if carries:
        print(
            f"{GREEN}{version} is outside line {line!r} but does ship {module}.{RESET}"
        )
        print(f"{DIM}  Consider deleting RASA_PRO_VERSION_LINE now that it is unneeded.{RESET}")
        return

    raise SystemExit(
        f"error: rasa-pro=={version} does not ship {module}.\n"
        f"       Every resource in this catalog imports it, so this bump would\n"
        f"       leave all of them failing at import. The pin is held on line\n"
        f"       {line!r} for exactly this reason (see RASA_PRO_VERSION_LINE).\n"
        f"       Run 'make outdated' to see when the line can be lifted, or\n"
        f"       re-run with --allow-missing-engine to override."
    )


# ------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    target = parser.add_argument_group("target version")
    target.add_argument(
        "--version", default=None, help="Target rasa-pro version (e.g. 3.19.1)"
    )
    target.add_argument(
        "--latest",
        action="store_true",
        help="Resolve the newest release from PyPI and migrate to it",
    )
    target.add_argument(
        "--allow-prerelease",
        action="store_true",
        help="With --latest, consider dev/rc releases too",
    )
    target.add_argument(
        "--match",
        default=None,
        metavar="PREFIX",
        help="With --latest, only consider versions starting with PREFIX "
        "(default: RASA_PRO_VERSION_LINE; pass '' to search all releases)",
    )
    target.add_argument(
        "--no-index-check",
        action="store_true",
        help="Do not verify the target exists on PyPI before rewriting files",
    )
    target.add_argument(
        "--allow-missing-engine",
        action="store_true",
        help="Bump even if the target lacks the engine module the catalog imports",
    )

    behaviour = parser.add_argument_group("behaviour")
    behaviour.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change; write nothing and never run uv lock",
    )
    behaviour.add_argument(
        "--skip-lock", action="store_true", help="Rewrite pins/docs only; skip uv lock"
    )
    behaviour.add_argument(
        "--upgrade",
        action="store_true",
        help="Force a full `uv lock --upgrade` re-resolve for every project "
        "(implied when the prerelease allowance is removed)",
    )
    behaviour.add_argument(
        "--no-touch-assessed-on",
        action="store_true",
        help="Do not refresh 'Assessed on' dates when pins change",
    )
    behaviour.add_argument(
        "--project",
        action="append",
        default=[],
        help="Limit to one or more repo-relative project paths (repeatable)",
    )
    args = parser.parse_args()

    new_version, from_cli = resolve_target(args)
    # Read-only, so it runs during a dry run too — previewing a bump to a
    # version that does not exist is exactly the mistake worth catching early.
    verify_on_index(new_version, skip=args.no_index_check)
    verify_engine_support(new_version, skip=args.allow_missing_engine)

    projects = discover_projects()
    if args.project:
        wanted = {p.strip().rstrip("/") for p in args.project}
        missing = wanted - {p.rel for p in projects}
        if missing:
            print(f"Unknown project(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 1
        projects = [p for p in projects if p.rel in wanted]

    mode = f" {YELLOW}[dry run]{RESET}" if args.dry_run else ""
    print(f"Migrating {len(projects)} project(s) → rasa-pro=={new_version}{mode}")
    print(f"{DIM}Repo: {REPO_ROOT}{RESET}")
    if not is_prerelease(new_version):
        print(f"{DIM}Stable target: uv prerelease allowance will be removed.{RESET}")
    print()

    failed = changed = 0
    for project in projects:
        before = read_pyproject_pin(project)
        result = migrate_project(
            project,
            new_version,
            skip_lock=args.skip_lock,
            touch_assessed_on=not args.no_touch_assessed_on,
            dry_run=args.dry_run,
            upgrade=args.upgrade,
        )
        if result["error"]:
            failed += 1
            print(f"{RED}[FAIL]{RESET} {result['path']}: {result['error']}")
            continue

        notes = []
        if result["docs"]:
            notes.append(f"docs: {', '.join(result['docs'])}")
        if result["prerelease"]:
            notes.append(f"prerelease {result['prerelease']}")
        if result["locked"]:
            how = "re-resolved" if result["upgraded"] else "lock"
            notes.append(f"{how} → {result['lock_version']}")
        elif not args.dry_run:
            notes.append("lock skipped")
        detail = f"  ({'; '.join(notes)})" if notes else ""

        touched = bool(result["pin_changed"] or result["docs"] or result["prerelease"])
        if touched or before != new_version:
            changed += 1
            print(f"{GREEN}[OK]{RESET}   {result['path']}: {before} → {new_version}{detail}")
        else:
            print(f"{DIM}[SKIP] {result['path']}: already on {new_version}{detail}{RESET}")

    # Repo-level docs that quote the pin (root README, MIGRATING, Makefile help).
    for rel in REPO_DOCS:
        if _rewrite_doc(
            REPO_ROOT / rel, None, new_version, touch_assessed_on=False, dry_run=args.dry_run
        ):
            print(f"{GREEN}[OK]{RESET}   {rel}: version strings updated")

    if failed:
        print(f"\n{RED}Done with errors. changed={changed} failed={failed}{RESET}")
        print(f"{YELLOW}RASA_PRO_VERSION left untouched — fix the failures and re-run.{RESET}")
        return 1

    if args.dry_run:
        print(f"\n{YELLOW}Dry run — nothing written.{RESET} changed={changed} target={new_version}")
        return 0

    # Written last: the pin file should only advance once the sweep succeeded.
    if from_cli:
        write_version_file(new_version)
        print(f"{GREEN}[OK]{RESET}   RASA_PRO_VERSION → {new_version}")

    print(f"\n{GREEN}Done.{RESET} changed={changed} failed=0 target={new_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
