#!/usr/bin/env python3
"""Render a spec file's missing caller lines into caller-audio/, once.

    python3 shared/spec/render_caller_audio.py shared/spec/conversations-adversarial-2.json --dry-run
    python3 shared/spec/render_caller_audio.py shared/spec/conversations-adversarial-2.json --budget-usd 0.1

The 17 headline calls' audio was copied from the case build. New calls are
rendered here with the case-build renderer's own Deepgram request
(``scripts/case_builds/render_caller_audio.py``, ``render_deepgram``), the
same voice and rate, into the same folder and ``manifest.json``. Files that
already exist are never rendered again. Each file's cost is in the manifest;
the key loads from ``.env`` into this process only and is never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TUTORIAL = HERE.parents[1]
sys.path.insert(0, str(TUTORIAL.parents[1] / "scripts" / "case_builds"))

from harness import agent_env  # noqa: E402
from render_caller_audio import caller_lines, render_deepgram  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spec_file")
    parser.add_argument("--budget-usd", type=float, help="cap on this render's cost")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    spec = json.loads(Path(args.spec_file).read_text())
    caller = spec["voice"]["caller"]
    if caller["vendor"] != "deepgram":
        parser.error("only the deepgram caller voice is supported here")
    out_dir = HERE / spec["voice"]["caller_audio_dir"]
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())

    todo = {n: line for n, line in caller_lines(spec).items() if not (out_dir / n).is_file()}
    chars = sum(len(line["text"]) for line in todo.values())
    estimate = round(chars * caller["usd_per_1m_characters"] / 1e6, 6)
    print(f"{len(todo)} caller lines to render, {chars} characters, estimated {estimate} USD")
    if args.dry_run or not todo:
        return 0
    if args.budget_usd is None or estimate > args.budget_usd:
        print("pass --budget-usd at or above the estimate; nothing rendered")
        return 2

    env = agent_env(TUTORIAL)
    total = 0.0
    try:
        for name, line in sorted(todo.items()):
            out = out_dir / name
            billed = render_deepgram(line["text"], line["voice"], caller["sample_rate"], out, env)
            cost = round(billed * caller["usd_per_1m_characters"] / 1e6, 8)
            total += cost
            with wave.open(str(out), "rb") as w:
                duration = w.getnframes() / w.getframerate()
            manifest["files"][name] = {
                "text": line["text"], "vendor": caller["vendor"], "model": caller.get("model"),
                "voice": line["voice"], "sample_rate": caller["sample_rate"], "duration_s": round(duration, 3),
                "characters": len(line["text"]), "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "characters_billed": billed, "cost_usd": cost, "spec": spec["spec"],
            }
            print(f"rendered {name} ({duration:.2f} s)")
    finally:
        manifest["files"] = dict(sorted(manifest["files"].items()))
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"spent {round(total, 6)} USD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
