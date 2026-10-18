#!/usr/bin/env python3
"""Rehearse the masterclass commands in order, offline, and print each block's time and result.

    uv run python rehearse.py            (from this folder, after `uv sync --frozen`)

It runs the commands of FACILITATOR.md that need only this repository: no network, no key, no model.
It writes under runs/ and a temporary folder, both ignored by git. Each line says ok or FAIL against the
text the script expects. A FAIL means that block would not behave as FACILITATOR.md says on this machine.
The two profrod.ai blocks are not here; their offline stand-in is the toy loop in OFFLINE-OPENING.md.
Exit 0 only if every step matched.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MCP = HERE.parent / "openai-mcp"
PY = sys.executable
results = []
TAG = time.strftime("%m%d%H%M%S")  # a fresh run folder name each time: the factory refuses to reuse one


def step(block, argv, expect, cwd=HERE, env=None):
    started = time.time()
    done = subprocess.run([PY, *argv], cwd=cwd, env=env, capture_output=True, text=True)
    out = (done.stdout + done.stderr).strip()
    ok = expect in out
    seconds = time.time() - started
    results.append((block, ok, seconds))
    last = out.splitlines()[-1] if out else ""
    print(f"{'ok  ' if ok else 'FAIL'} {seconds:5.1f}s  {block}: python {' '.join(argv)}\n         -> {last}")
    if not ok:
        print(f"         expected to contain: {expect}")


def main():
    work = Path(tempfile.mkdtemp(prefix="masterclass-rehearse-"))
    try:
        a1 = "tasks/a1-block-card.json"
        loop = [
            ("14:40 toy loop", [a1, "candidates/block-card-good", f"runs/rh-good-{TAG}"], "ACCEPT - protected acceptance passed", "factory.py"),
            ("14:40 toy loop", [a1, "candidates/block-card-forges-accept", f"runs/rh-forge1-{TAG}"], "ACCEPT - protected acceptance passed", "factory.py"),
            ("14:40 toy loop", [a1, "candidates/block-card-forges-accept", f"runs/rh-forge2-{TAG}"], "exited with status 0 without unittest's OK line", "factory_v2.py"),
            ("14:40 toy loop", [a1, "candidates/block-card-tamper", f"runs/rh-tamper-{TAG}"], "REJECT - files outside the allowed paths", "factory.py"),
        ]
        for block, args, expect, script in loop:
            step(block, [script, *args], expect)
        step("14:30 interval", ["measure.py", "intervals", "4"], "4        1.00 to 1.00    0.51 to 1.00")
        for name, expect in [("good", "ACCEPT"), ("gate-omitted", "REJECT"), ("gate-false", "REJECT"), ("gate-deleted", "REJECT")]:
            step("15:00 silent gate", ["factory.py", a1, f"candidates/block-card-{name}", f"runs/rh-{TAG}-s-{name}"], expect)
        step("15:00 silent gate", ["show_gate.py", "candidates/block-card-gate-omitted"], "block_card gate: OFF (compiled to None)")
        env = {**os.environ, "PYTHONPATH": str(HERE), "MANTLE_PROJECT": str(MCP / "project")}
        step("15:40 vendor boundary", ["-I", "experiments.py", "project"], "baseline", cwd=MCP, env=env)
        step("15:40 vendor boundary", ["grade_variants.py", "project"], "question-wording-replaced  ACCEPT", cwd=MCP, env=env)
        for task, cand, run in [("a2-rule-digits", "rule-digits-good", "rh-digits"), ("a3-rule-confirm", "rule-confirm-on-baseline", "rh-confirm-alone"), ("a3-rule-confirm", "rule-confirm-on-digits", "rh-confirm-rebased")]:
            step("16:50 integrate", ["factory.py", f"tasks/{task}.json", f"candidates/{cand}", f"runs/{run}-{TAG}"], "ACCEPT")
        # The manifests name runs/digits-01 etc.; rewrite them to this rehearsal's runs in a temporary copy.
        manifests = work / "integration"
        shutil.copytree(HERE / "integration", manifests)
        for path in manifests.glob("*.json"):
            text = path.read_text().replace("runs/digits-01", f"runs/rh-digits-{TAG}").replace("runs/confirm-alone", f"runs/rh-confirm-alone-{TAG}").replace("runs/confirm-rebased", f"runs/rh-confirm-rebased-{TAG}")
            path.write_text(text)
        trunk = str(work / "trunk")
        step("16:50 integrate", ["integrate.py", trunk, str(manifests / "m1-digits.json")], "MERGED")
        step("16:50 integrate", ["integrate.py", trunk, str(manifests / "m2-confirm-on-baseline.json")], "STALE_BASE")
        step("16:50 integrate", ["integrate.py", trunk, str(manifests / "m3-confirm-on-digits.json")], "MERGED")
        rel, appr = str(work / "releases"), work / "approvals"
        appr.mkdir()
        step("16:50 release", ["approve.py", "allow", rel, "reviewer"], "approvers: reviewer")
        step("16:50 release", ["approve.py", "sign", "candidates/block-card-good", "codex", str(appr / "by-codex.json")], "codex approves")
        step("16:50 release", ["release.py", "publish", f"runs/rh-good-{TAG}/decision.json", "candidates/block-card-good", str(appr / "by-codex.json"), rel], "'codex' is not on the list")
        step("16:50 release", ["approve.py", "sign", "candidates/block-card-good", "reviewer", str(appr / "by-reviewer.json")], "reviewer approves")
        step("16:50 release", ["release.py", "publish", f"runs/rh-good-{TAG}/decision.json", "candidates/block-card-good", str(appr / "by-reviewer.json"), rel], "PUBLISHED")
        step("16:50 release", ["release.py", "verify", rel], "SERVING")
        step("17:10 report", ["measure.py", "report", "agent-runs/claude-code-2026-10-15", "agent-runs/codex-2026-10-15"], "accepted: 18 of 18 = 1.00")
        step("17:10 report", ["measure.py", "needed", "0.9"], "35 runs, 0 of them failing")
        step("17:10 report", ["policy.py", "what-if", "policy.json", "35", "35"], "ELIGIBLE for promotion")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("\nper block (seconds):")
    blocks = {}
    for block, ok, seconds in results:
        total, good = blocks.get(block, (0.0, True))
        blocks[block] = (total + seconds, good and ok)
    for block, (total, good) in blocks.items():
        print(f"  {'ok  ' if good else 'FAIL'} {total:6.1f}  {block}")
    failed = [b for b, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} steps matched." + ("" if not failed else " FAILED: " + ", ".join(sorted(set(failed)))))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
