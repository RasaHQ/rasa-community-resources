#!/usr/bin/env python3
"""Turn an agent's finished working copy into a candidate and a review packet.

    python collect.py <agent-workspace> <out-candidate> <out-review> [--prefix DIR] [--only a.py,b.py] [--claim FILE]

--prefix places the workspace's files under DIR (a saved run keeps its files flat; the repository keeps
them under product/). --only keeps just the named files. --claim stores the agent's own account.

The agent worked in its own copy of the repository. This script keeps only the files that differ
from the baseline, lays them out as a candidate the factory accepts, and writes the change as a
unified diff plus a small record. The agent's own account of what it did is stored beside the
diff, labelled as a claim. Nothing here decides ACCEPT or REJECT. That is the factory's job.
"""
import argparse
import difflib
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(workspace, out_candidate, out_review, prefix="", only=None, stdout_file=None, pack_root=None):
    workspace, out_candidate, out_review = Path(workspace), Path(out_candidate), Path(out_review)
    for target in (out_candidate, out_review):
        if target.exists():
            print("refusing to reuse %s; choose a new folder" % target, file=sys.stderr)
            return 2
    root = Path(pack_root).resolve() if pack_root is not None else ROOT
    baseline = root / "product"
    changed, patch = [], []
    # Files scratch.py wrote outside product/ are skipped only while they are byte for byte what it wrote.
    manifest_file = workspace / ".scratch.json"
    untouched = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
    if manifest_file.exists():
        untouched[".scratch.json"] = sha(manifest_file)
    for path in sorted(p for p in workspace.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        if only and path.name not in only:
            continue
        if untouched.get(path.relative_to(workspace).as_posix()) == sha(path):
            continue
        rel = (Path(prefix) / path.relative_to(workspace)).as_posix()
        old = root / rel
        before = old.read_text().splitlines(keepends=True) if old.exists() else []
        after = path.read_text().splitlines(keepends=True)
        if before == after:
            continue
        changed.append(rel)
        patch.extend(difflib.unified_diff(before, after, "a/" + rel, "b/" + rel))
        target = out_candidate / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    out_review.mkdir(parents=True)
    (out_review / "change.patch").write_text("".join(patch))
    record = {
        "files_changed": changed,
        "lines_added": sum(1 for l in patch if l.startswith("+") and not l.startswith("+++")),
        "lines_removed": sum(1 for l in patch if l.startswith("-") and not l.startswith("---")),
        "patch_sha256": sha(out_review / "change.patch"),
        "agent_account": None,
    }
    if stdout_file:
        shutil.copyfile(stdout_file, out_review / "agent-claim.txt")
        record["agent_account"] = {"file": "agent-claim.txt", "sha256": sha(out_review / "agent-claim.txt"),
                                   "status": "a claim by the builder, not evidence"}
    (out_review / "review.json").write_text(json.dumps(record, indent=2) + "\n")
    print("collected %d changed file(s): %s" % (len(changed), ", ".join(changed) or "none"))
    return 0 if changed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(usage=__doc__)
    parser.add_argument("workspace")
    parser.add_argument("out_candidate")
    parser.add_argument("out_review")
    parser.add_argument("--prefix", default="")
    parser.add_argument("--only", default="")
    parser.add_argument("--claim")
    a = parser.parse_args()
    raise SystemExit(main(a.workspace, a.out_candidate, a.out_review, a.prefix, set(filter(None, a.only.split(","))), a.claim))
