#!/usr/bin/env python3
"""Integrate accepted Mantle candidates one at a time into a trunk, and keep every earlier promise.

    python integrate.py trunk/ <manifest.json> [--ignore-base]

A manifest names a candidate, its task, the factory's decision record for it, and the digest of the project it
was BUILT ON. Three checks, in this order of cheapness:
  1. the factory's decision for exactly these files is ACCEPT,
  2. its base is the trunk as it stands now (otherwise STALE_BASE: rebuild it on the current trunk),
  3. with the change laid over a trial copy of the trunk, the protected acceptance of EVERY task merged so far,
     plus its own, passes against the real engine.
Exit 0 MERGED, 1 REFUSED, 2 could not run.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from factory import ROOT, digest_tree, files_in, run_tests


def main(trunk_dir, manifest_path, ignore_base=False):
    trunk = Path(trunk_dir)
    ledger = trunk / "ledger.json"
    if not (trunk / "product").exists():
        shutil.copytree(ROOT / "product", trunk / "product")
        (trunk / "product" / "skills").mkdir(exist_ok=True)
        ledger.write_text(json.dumps({"merged": []}, indent=2) + "\n")
    state = json.loads(ledger.read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    candidate = ROOT / manifest["candidate"]
    now = digest_tree(trunk / "product")
    reasons = []
    decision_file = ROOT / manifest["decision"]
    decision = json.loads(decision_file.read_text()) if decision_file.exists() else None
    if not decision or decision["decision"] != "ACCEPT":
        reasons.append("NO_ACCEPT: no accepted factory decision at %s" % manifest["decision"])
    elif decision["candidate_digest"] != digest_tree(candidate):
        reasons.append("NOT_THE_TESTED_FILES: the candidate changed after the factory judged it")
    if manifest["base_digest"] != now and not ignore_base:
        reasons.append("STALE_BASE: built on %s, the trunk is now %s; rebuild it on the current trunk" % (manifest["base_digest"][:12], now[:12]))
    if not reasons or ignore_base:
        with tempfile.TemporaryDirectory(prefix="mantle-integrate-") as scratch:
            trial = Path(scratch) / "product"
            shutil.copytree(trunk / "product", trial)
            for path in files_in(candidate):
                target = Path(scratch) / path.relative_to(candidate)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
            for item in state["merged"] + [{"task": manifest["task"]}]:
                task = json.loads((ROOT / item["task"]).read_text())
                protected = Path(scratch) / "protected"
                protected.mkdir(exist_ok=True)
                for path in [ROOT / task["acceptance"]["path"], *[ROOT / s["path"] for s in task["support"]]]:
                    shutil.copyfile(path, protected / path.name)
                result = run_tests(protected / Path(task["acceptance"]["path"]).name, trial, scratch)
                if not result["passed"]:
                    reasons.append("promise broken: %s fails (%s)" % (Path(task["acceptance"]["path"]).name, result["summary"]))
            if not reasons:
                shutil.rmtree(trunk / "product")
                shutil.copytree(trial, trunk / "product")
                state["merged"].append({"task": manifest["task"], "candidate": candidate.name, "trunk_after": digest_tree(trunk / "product")})
                ledger.write_text(json.dumps(state, indent=2) + "\n")
    print("MERGED" if not reasons else "REFUSED", "-", "; ".join(reasons) if reasons else candidate.name)
    return 1 if reasons else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--ignore-base"]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(*args, ignore_base="--ignore-base" in sys.argv))
