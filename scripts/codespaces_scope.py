"""Select affected resources for pull requests and pushes; scheduled/manual runs are full.

PR comparisons use the merge base of the explicit base and head commits. Missing
history or shared inputs select every resource. Local path dependencies are part
of a resource's affected source tree, including transitive shared packages.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ZERO = "0" * 40


def every_resource() -> list[dict]:
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts/generate_codespaces.py"), "--list-json"],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


SHARED = ("scripts/", ".github/workflows/", "Makefile", "RASA_PRO_VERSION",
          "RASA_PRO_VERSION_LINE", "RASA_RELEASE.json")


# The casebook scaffold check reads starter templates and runs lint controls
# directly; these inputs are not represented by a uv package dependency.
SOURCE_INPUTS = {"tutorials/rasa-ai-team-casebook": ("starter-pack",)}


def dependency_roots(resource: str) -> set[str]:
    """Local uv and explicit source inputs, without installing any project."""
    pending = [ROOT / resource, *(ROOT / name for name in SOURCE_INPUTS.get(resource, ()))]
    roots = set()
    while pending:
        path = pending.pop().resolve()
        rel = path.relative_to(ROOT.resolve()).as_posix()
        if rel in roots:
            continue
        roots.add(rel)
        manifest = path / 'pyproject.toml'
        if not manifest.is_file():
            continue
        data = tomllib.loads(manifest.read_text())
        for source in data.get('tool', {}).get('uv', {}).get('sources', {}).values():
            for item in source if isinstance(source, list) else [source]:
                if isinstance(item, dict) and 'path' in item:
                    pending.append(path / item['path'])
    return roots


def changed_slugs(before: str, sha: str, resources=None, *, pull_request=False) -> set[str] | None:
    if not before or before == ZERO:
        return None
    try:
        if pull_request:
            before = subprocess.check_output(['git', 'merge-base', before, sha],
                cwd=ROOT, text=True).strip()
        names = subprocess.run(
            ['git', 'diff', '--name-only', '-z', before, sha],
            check=True, capture_output=True, text=True, cwd=ROOT,
        ).stdout.split('\0')
        names = [name for name in names if name]
        if any(name == prefix or name.startswith(prefix) for name in names for prefix in SHARED):
            return None
        slugs = set()
        sources = []
        for name in names:
            parts = name.split('/')
            if parts[0] == '.devcontainer':
                if len(parts) < 3 or parts[1] == 'resource-base':
                    return None
                slugs.add(parts[1])
            else:
                sources.append(name)
        if sources:
            for resource in every_resource() if resources is None else resources:
                roots = dependency_roots(resource['path'])
                if any(name == root or name.startswith(root + '/') for name in sources for root in roots):
                    slugs.add(resource['slug'])
        return slugs
    except (subprocess.CalledProcessError, ValueError, OSError):
        # Unknown history or an unresolvable dependency is never a narrow pass.
        return None


def choose(event: str, resources: list[dict], changed: set[str] | None, only: str = "") -> list[dict]:
    if event in ("push", "pull_request"):
        return resources if changed is None else [r for r in resources if r["slug"] in changed]
    wanted = set(only.split())
    if wanted:
        return [r for r in resources if r["slug"] in wanted]
    return resources


def main(argv: list[str]) -> int:
    event, before, sha = argv[1:4]
    only = argv[4] if len(argv) > 4 else ""
    if len(argv) > 5 and argv[5] in ('catalog', 'snapshots'):
        from rasa_projects import discover_projects
        resources = [{'path': p.rel, 'slug': p.rel} for p in discover_projects(argv[5])]
    else:
        resources = every_resource()
    changed = changed_slugs(before, sha, resources, pull_request=event == 'pull_request') if event in ('push', 'pull_request') else None
    print(json.dumps(choose(event, resources, changed, only)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
