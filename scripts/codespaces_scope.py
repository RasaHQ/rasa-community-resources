"""Choose which Codespace configurations the CI build covers.

    python3 scripts/codespaces_scope.py EVENT BEFORE SHA [ONLY]

Prints the resources to build as a JSON list of {"path", "slug"}, the same shape as
`generate_codespaces.py --list-json`. On a push, only resources whose own
`.devcontainer/<slug>/` directory changed between BEFORE and SHA are built. Every other
event (schedule, pull request, a manual run) builds all of them, or only the slugs
named in ONLY (space separated) on a manual run.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ZERO = "0" * 40


def every_resource() -> list[dict]:
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts/generate_codespaces.py"), "--list-json"],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def changed_slugs(before: str, sha: str) -> set[str]:
    """Slugs whose `.devcontainer/<slug>/` directory differs between the two commits."""
    if not before or before == ZERO:
        return set()
    names = subprocess.run(
        ["git", "diff", "--name-only", before, sha, "--", ".devcontainer"],
        check=True, capture_output=True, text=True, cwd=ROOT,
    ).stdout.split()
    parts = (name.split("/") for name in names)
    return {p[1] for p in parts if len(p) > 2 and p[0] == ".devcontainer" and p[1] != "resource-base"}


def choose(event: str, resources: list[dict], changed: set[str], only: str = "") -> list[dict]:
    if event == "push":
        return [r for r in resources if r["slug"] in changed]
    wanted = set(only.split())
    if wanted:
        return [r for r in resources if r["slug"] in wanted]
    return resources


def main(argv: list[str]) -> int:
    event, before, sha = argv[1:4]
    only = argv[4] if len(argv) > 4 else ""
    changed = changed_slugs(before, sha) if event == "push" else set()
    print(json.dumps(choose(event, every_resource(), changed, only)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
