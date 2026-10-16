#!/usr/bin/env python3
"""A stand-in for a person's approval, so the release unit can run on one laptop.

    python approve.py allow <releases-dir> <name>                    put a person on the approvers list
    python approve.py sign  <candidate-dir> <name> <approval.json>   write that person's approval of these exact files

In a real factory the list lives somewhere the builder cannot write, and a signature is a person's act in a
system that knows who they are. Here both are plain files, so this unit teaches the shape of the check and
proves nothing about identity.
"""
import json
import sys
from pathlib import Path

from factory import digest_tree


def allow(releases_dir, name):
    releases = Path(releases_dir)
    releases.mkdir(parents=True, exist_ok=True)
    path = releases / "approvers.json"
    people = json.loads(path.read_text()) if path.exists() else []
    path.write_text(json.dumps(sorted(set(people + [name]))) + "\n")
    print("approvers:", ", ".join(json.loads(path.read_text())))
    return 0


def sign(candidate_dir, name, out):
    record = {"action": "publish", "digest": digest_tree(candidate_dir), "approver": name}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(record, indent=2) + "\n")
    print("%s approves publishing %s" % (name, record["digest"][:12]))
    return 0


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else (None, [])
    table = {"allow": (allow, 2), "sign": (sign, 3)}
    if cmd not in table or len(args) != table[cmd][1]:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(table[cmd][0](*args))
