#!/usr/bin/env python3
"""Reject vendor definition bytes tracked in the three direct banking examples.

Inspect index blobs rather than ignored files or local downloaded inputs. This
is a source hygiene check; passing it does not qualify a vendor contract/mock.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BANNED_HASHES = frozenset({
    "ea8fa652705d2c5531f3dcea4d18c5797797423e8a51a4a2a0403f471615228f",
    "bc18c382889a9de6f2d244e033d223981bfb77ceb85cbfee96cb603354a53399",  # Symitar accounts.yaml as republished 2026-11-12 19:31Z
    "c1659b038b1d7bd9c89a63ad2e688a27d89cbc1d18477627d9e0105d87f10d96",
    "050962d37b56c1a35eddb7795b3fa9e4c1c6db10b01f4f5b2b46a9f4537092a5",
    "bd5ec66744b21cb3632d37e2cbdb53bbf7f3bd79cb7047cafafa9caca186de95",
    # Symitar accounts, transactions and loans as republished 2026-11-13 (optional
    # memberNumbers filter; documented 404 responses). transfers.yaml unchanged.
    "d6370f663f53973dfc52d931333bdc350dc39f6c2680998a9054030668b4820f",
    "9662089e4943dea29e8d109419388bb971301890f0ca07a4a2eff55cee19fe8d",
    "2631ee0b97790009624ca3f9c8d233855d0ecf06556a8f0134770a831801c914",
    "a433a01b05925bd9af2bb12184046443574eba98c4fbf65b716b73cad6ff7900",
    "f2ff471b945b938ae0173ba2174eeb9fbb30c678c3232f177566bb27143b5108",
    "559ce0113d96260ce4f7437c0dfd3a6ad49c0d976fc29abfdfaa31680dafbd22",
    "65404b27b99d12bedc5cddf5d714dc6117d2d4fb3896e7d18d3067e324f4f7a8",
})
SCHEMA_MARKERS = (
    rb'(?m)^\s*[\'\"]?(?:openapi|swagger)[\'\"]?\s*:',
    rb'[\'\"](?:openapi|swagger)[\'\"]\s*:\s*[\'\"][23]\.',
    rb'[\'\"]\$schema[\'\"]\s*:',
    rb'<(?:[\w.-]+:)?(?:schema|definitions)\b',
)
MAX_BLOB = 16 * 1024 * 1024


def git(root: Path, *args: str) -> bytes:
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
    return subprocess.run(["git", *args], cwd=root, env=env, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def in_scope(path: PurePosixPath) -> bool:
    return (len(path.parts) > 2 and path.parts[0] == "examples"
            and (path.parts[1].startswith("jack-henry-")
                 or path.parts[1] == "fiserv-premier-11.0.0-prm"))


def findings(root: Path) -> list[tuple[str, str]]:
    problems = []
    for record in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, oid, stage = metadata.split()
        path = raw_path.decode("utf-8", errors="surrogateescape")
        relative = PurePosixPath(path)
        if not in_scope(relative):
            continue
        if "vendor-inputs" in relative.parts[2:]:
            problems.append((path, "tracked vendor-inputs file"))
            continue
        if stage != b"0":
            problems.append((path, "unresolved index entry"))
            continue
        if mode not in (b"100644", b"100755"):
            problems.append((path, "non-regular tracked source requires review"))
            continue
        object_id = oid.decode("ascii")
        if int(git(root, "cat-file", "-s", object_id)) > MAX_BLOB:
            problems.append((path, "oversized source blob requires review"))
            continue
        raw = git(root, "cat-file", "blob", object_id)
        if hashlib.sha256(raw).hexdigest() in BANNED_HASHES:
            problems.append((path, "pinned vendor artifact"))
        elif raw.startswith(b"PK\x03\x04"):
            problems.append((path, "tracked archive requires source review"))
        elif any(re.search(marker, raw, re.IGNORECASE) for marker in SCHEMA_MARKERS):
            problems.append((path, "schema document or embedded schema requires review"))
    return problems


def main() -> int:
    try:
        problems = findings(ROOT)
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("FAIL: unable to inspect tracked banking source blobs", file=sys.stderr)
        return 1
    for path, reason in problems:
        print(f"FAIL {json.dumps(path, ensure_ascii=True)}: {reason}")
    if problems:
        return 1
    print("PASS: no tracked vendor inputs or detected schemas in direct banking source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
