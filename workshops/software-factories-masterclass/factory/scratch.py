#!/usr/bin/env python3
"""Make a working folder for a builder agent: the project, one task, instructions and validate.py. Nothing protected.

    python scratch.py <task.json> <new-folder>

The folder holds no acceptance suite, no accept_lib.py and no factory. The agent works there; collect.py then
turns what it changed into a candidate.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(task_path, target, pack_root=None, instructions="AGENTS.md"):
    target = Path(target)
    if target.exists():
        print("refusing to reuse a folder; choose a new one", file=sys.stderr)
        return 2
    root = Path(pack_root).resolve() if pack_root is not None else ROOT
    task = json.loads(Path(task_path).read_text())
    shutil.copytree(root / "product", target / "product")
    (target / "product" / "skills").mkdir(exist_ok=True)
    (target / "tasks").mkdir()
    # The builder sees the request and the paths it may touch. It does not see which suite will judge it.
    visible = {k: task[k] for k in ("id", "request", "allowed_paths", "excluded")}
    task_name = Path(task_path).name if pack_root is not None else task["id"] + ".json"
    (target / "tasks" / task_name).write_text(json.dumps(visible, indent=2) + "\n")
    shutil.copyfile(root / "builder" / instructions, target / "AGENTS.md")
    for name in ("CLAUDE.md", "validate.py"):
        if (root / "builder" / name).is_file():
            shutil.copyfile(root / "builder" / name, target / name)
    # What this script wrote outside product/, with hashes, so collect.py can tell an untouched copy from an edited one.
    made = sorted(p for p in target.rglob("*") if p.is_file() and "product" not in p.relative_to(target).parts)
    manifest = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in made}
    (target / ".scratch.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("ready:", target)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(*sys.argv[1:]))
