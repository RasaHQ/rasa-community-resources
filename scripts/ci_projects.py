#!/usr/bin/env python3
"""Select both project tiers from the PR merge-base diff, or all otherwise."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from rasa_projects import REPO_ROOT, discover_projects


def changed_paths(root: Path, base_ref: str) -> list[str]:
    if not base_ref:
        raise ValueError("pull_request requires BASE_REF")
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", "-z",
         f"origin/{base_ref}...HEAD", "--"],
        cwd=root, check=True, capture_output=True,
    )
    return [os.fsdecode(path) for path in result.stdout.split(b"\0") if path]


def select_projects(projects: list[str], changed: list[str] | None) -> list[str]:
    if changed is None:
        return projects
    return [project for project in projects
            if any(path.startswith(project + "/") for path in changed)]


def outputs(event: str, base_ref: str) -> dict[str, list[str]]:
    changed = changed_paths(REPO_ROOT, base_ref) if event == "pull_request" else None
    return {
        name: select_projects([project.rel for project in discover_projects(scope)], changed)
        for name, scope in [("projects", "catalog"), ("snapshots", "snapshots")]
    }


def main() -> None:
    for name, paths in outputs(os.environ["GITHUB_EVENT_NAME"], os.environ.get("BASE_REF", "")).items():
        print(f"{name}={json.dumps(paths)}")


if __name__ == "__main__":
    main()
