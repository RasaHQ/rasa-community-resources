#!/usr/bin/env python3
"""List Rasa Pro projects and report pin drift against RASA_PRO_VERSION.

Usage:
    python scripts/list_projects.py
    python scripts/list_projects.py --status
    python scripts/list_projects.py --paths-only
    python scripts/list_projects.py --check-latest
    python scripts/list_projects.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rasa_projects import (  # noqa: E402
    REQUIRED_ENGINE_MODULE,
    IndexUnavailable,
    discover_projects,
    is_prerelease,
    latest_version,
    project_drift,
    read_expected_version,
    read_version_line,
    release_carries_engine,
    uv_prerelease_args,
)


def _c(code: str) -> str:
    return code if sys.stdout.isatty() else ""


GREEN, YELLOW, RED, DIM, RESET = (
    _c("\033[92m"),
    _c("\033[93m"),
    _c("\033[91m"),
    _c("\033[2m"),
    _c("\033[0m"),
)


def _report_line_gap(newest_on_line: str, allow_prerelease: bool) -> None:
    """Compare the pinned release line against the newest release overall.

    The line exists because the catalog needs an engine module that has not
    reached the stable line yet. That is a temporary state, so the newest
    release is probed for the module directly: when it finally carries it, this
    says so instead of quietly holding the catalog back forever.
    """
    try:
        overall = latest_version(allow_prerelease=allow_prerelease)
    except IndexUnavailable as exc:
        print(f"{YELLOW}Could not check the newest release overall: {exc}{RESET}")
        return

    if overall == newest_on_line:
        return

    print()
    print(f"{DIM}Newest rasa-pro on PyPI overall: {overall}{RESET}")
    module = REQUIRED_ENGINE_MODULE.rstrip("/").replace("/", ".")
    try:
        carries = release_carries_engine(overall)
    except IndexUnavailable as exc:
        print(f"{YELLOW}  Could not inspect {overall} for {module}: {exc}{RESET}")
        print(f"{DIM}  Holding at {newest_on_line} until it can be verified.{RESET}")
        return

    if carries:
        print(
            f"{GREEN}  {overall} now ships {module} — the release line in "
            f"RASA_PRO_VERSION_LINE can be lifted.{RESET}"
        )
        print(
            f"{DIM}  Delete RASA_PRO_VERSION_LINE, then: "
            f"make migrate VERSION={overall} && make ci{RESET}"
        )
    else:
        print(
            f"{DIM}  Held back on purpose: {overall} does not ship {module}, "
            f"which every resource here imports.{RESET}"
        )
        print(f"{DIM}  See RASA_PRO_VERSION_LINE and docs/MIGRATING.md.{RESET}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--status",
        action="store_true",
        help="Exit 1 if any project drifts from RASA_PRO_VERSION",
    )
    parser.add_argument(
        "--paths-only",
        action="store_true",
        help="Print one project path per line (repo-relative)",
    )
    parser.add_argument(
        "--check-latest",
        action="store_true",
        help="Also report whether a newer rasa-pro exists on PyPI",
    )
    parser.add_argument(
        "--allow-prerelease",
        action="store_true",
        help="With --check-latest, consider dev/rc releases too",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--uv-prerelease-args",
        action="store_true",
        help="Print the uv prerelease flags implied by the pin (empty when stable)",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Expected version override (default: RASA_PRO_VERSION)",
    )
    args = parser.parse_args()

    expected = read_expected_version(args.version)

    if args.uv_prerelease_args:
        print(" ".join(uv_prerelease_args(expected)))
        return 0

    projects = discover_projects()

    if args.paths_only:
        for project in projects:
            print(project.rel)
        return 0

    drifts = [project_drift(project, expected) for project in projects]
    drifted = [d for d in drifts if not d.ok]

    if args.json:
        print(
            json.dumps(
                {
                    "expected": expected,
                    "prerelease": is_prerelease(expected),
                    "projects": [
                        {
                            "path": d.project.rel,
                            "ok": d.ok,
                            "pyproject": d.pyproject,
                            "lock": d.lock,
                            "readme": d.readme,
                            "stale_docs": d.docs,
                            "uv_prerelease": d.prerelease_setting,
                            "issues": d.issues(),
                        }
                        for d in drifts
                    ],
                    "drifted": len(drifted),
                },
                indent=2,
            )
        )
        return 1 if (args.status and drifted) else 0

    kind = "prerelease" if is_prerelease(expected) else "stable"
    print(f"Expected rasa-pro: {expected} ({kind})")
    print(f"Projects: {len(projects)}")
    print()

    for drift in drifts:
        if drift.ok:
            detail = f"pyproject={drift.pyproject} lock={drift.lock}"
            if drift.readme is not None:
                detail += f" readme={drift.readme}"
            print(f"{GREEN}[ok]{RESET} {drift.project.rel}  {DIM}{detail}{RESET}")
        else:
            print(f"{RED}[DRIFT]{RESET} {drift.project.rel}  {', '.join(drift.issues())}")

    if args.check_latest:
        print()
        line = read_version_line()
        try:
            newest = latest_version(
                allow_prerelease=args.allow_prerelease, prefix=line
            )
        except IndexUnavailable as exc:
            print(f"{YELLOW}Could not check PyPI: {exc}{RESET}")
        else:
            if newest == expected:
                scope = f" on line {line}" if line else " on PyPI"
                print(f"{GREEN}RASA_PRO_VERSION is the newest release{scope}.{RESET}")
            else:
                print(
                    f"{YELLOW}Newer release available: {newest} "
                    f"(pinned: {expected}){RESET}"
                )
                print(f"{DIM}  Bump with: make migrate VERSION={newest}{RESET}")

            # A release line deliberately holds the pin below the newest thing on
            # PyPI. Report that gap rather than hiding it — "newest on our line"
            # reads as "fully up to date" and silently buries a real release.
            if line:
                _report_line_gap(newest, args.allow_prerelease)

    if args.status:
        if drifted:
            print(f"\n{len(drifted)} project(s) out of sync with {expected}")
            return 1
        print(f"\n{GREEN}All projects match RASA_PRO_VERSION{RESET}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
