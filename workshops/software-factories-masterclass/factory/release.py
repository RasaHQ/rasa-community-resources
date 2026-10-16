#!/usr/bin/env python3
"""Release exactly what was tested, behind an approval the builder cannot give itself.

    python release.py publish <decision.json> <candidate-dir> <approval.json> <releases-dir>
    python release.py verify  <releases-dir>
    python release.py rollback <releases-dir>

publish refuses unless: the decision is ACCEPT; the candidate in hand has the digest the factory tested;
the approval names that same digest, the action "publish", and a person listed in approvers.json,
a file the builder has no write access to.
verify re-hashes what is being served. rollback moves to the release published before the one being served, and stops at the oldest.
Exit 0 ok, 1 refused or drifted, 2 could not run.
"""
import json
import shutil
import sys
from pathlib import Path

from factory import ROOT, digest_tree


def read(path):
    return json.loads(Path(path).read_text())


def publish(decision_path, candidate_dir, approval_path, releases_dir):
    decision, approval = read(decision_path), read(approval_path)
    releases = Path(releases_dir)
    digest = digest_tree(candidate_dir)
    reasons = []
    if decision["decision"] != "ACCEPT":
        reasons.append("the factory did not accept this candidate")
    if digest != decision["candidate_digest"]:
        reasons.append("these files are not the ones the factory tested (digest %s, tested %s)" % (digest[:12], decision["candidate_digest"][:12]))
    if approval.get("action") != "publish":
        reasons.append("the approval is not for the action 'publish'")
    if approval.get("digest") != digest:
        reasons.append("the approval names a different digest (%s)" % str(approval.get("digest"))[:12])
    people = read(releases / "approvers.json") if (releases / "approvers.json").exists() else []
    if approval.get("approver") not in people:
        reasons.append("%r is not on the list of people who may approve (approvers.json in the releases folder)" % approval.get("approver"))
    if reasons:
        print("REFUSED -", "; ".join(reasons))
        return 1
    target = releases / digest[:12]
    shutil.copytree(Path(candidate_dir), target / "files")
    log = releases / "history.json"
    history = read(log) if log.exists() else []
    history.append({"event": "publish", "release": digest, "approved_by": approval["approver"]})
    (releases / "current").write_text(digest + "\n")
    log.write_text(json.dumps(history, indent=2) + "\n")
    print("PUBLISHED", digest[:12], "approved by", approval["approver"])
    return verify(releases_dir)


def verify(releases_dir):
    releases = Path(releases_dir)
    current = (releases / "current").read_text().strip()
    served = digest_tree(releases / current[:12] / "files")
    ok = served == current
    print(("SERVING " if ok else "DRIFT ") + current[:12] + ("" if ok else " (files on disk hash to %s)" % served[:12]))
    return 0 if ok else 1


def rollback(releases_dir):
    releases = Path(releases_dir)
    log = releases / "history.json"
    history = read(log)
    published = []
    for entry in history:
        if entry["event"] == "publish" and entry["release"] not in published:
            published.append(entry["release"])
    current = (releases / "current").read_text().strip()
    position = published.index(current)
    if position == 0:
        print("REFUSED - %s is the oldest release; there is nothing earlier to return to" % current[:12])
        return 1
    previous = published[position - 1]
    (releases / "current").write_text(previous + "\n")
    history.append({"event": "rollback", "release": previous, "from": current})
    log.write_text(json.dumps(history, indent=2) + "\n")
    print("ROLLED BACK to", previous[:12])
    return verify(releases_dir)


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else (None, [])
    table = {"publish": (publish, 4), "verify": (verify, 1), "rollback": (rollback, 1)}
    if cmd not in table or len(args) != table[cmd][1]:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(table[cmd][0](*args))
