#!/usr/bin/env python3
"""List Rasa Pro projects and report pin drift against RASA_PRO_VERSION.

Usage:
    python scripts/list_projects.py
    python scripts/list_projects.py --status
    python scripts/list_projects.py --paths-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rasa_projects import (  # noqa: E402
    discover_projects,
    project_drift,
    read_expected_version,
)


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
        "--version",
        default=None,
        help="Expected version override (default: RASA_PRO_VERSION)",
    )
    args = parser.parse_args()

    expected = read_expected_version(args.version)
    projects = discover_projects()

    if args.paths_only:
        for project in projects:
            print(project.rel)
        return 0

    print(f"Expected rasa-pro: {expected}")
    print(f"Projects: {len(projects)}")
    print()

    drifted = 0
    for project in projects:
        drift = project_drift(project, expected)
        if drift.ok:
            mark = "ok"
            detail = f"pyproject={drift.pyproject} lock={drift.lock}"
            if drift.readme is not None:
                detail += f" readme={drift.readme}"
        else:
            drifted += 1
            mark = "DRIFT"
            detail = ", ".join(drift.issues())
        print(f"[{mark}] {project.rel}  {detail}")

    if args.status:
        if drifted:
            print(f"\n{drifted} project(s) out of sync with {expected}")
            return 1
        print("\nAll projects match RASA_PRO_VERSION")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
