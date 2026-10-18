#!/usr/bin/env python3
"""Rehearse the masterclass commands in session order, offline, and print each block's time and result.

    uv run python rehearse.py                (from this folder, after `uv sync --frozen`)
    uv run python rehearse.py --self-check   (proves that a wrong exit status or wrong output fails a step)

It runs the commands of FACILITATOR.md that need only this repository: no network, no key, no model.
It writes under runs/ and a temporary folder, both ignored by git. A step passes only if its output contains
the expected text AND the command exits with the expected status (refusals and rejections exit 1 on purpose).
A FAIL means that block would not behave as FACILITATOR.md says on this machine.
The two profrod.ai blocks are not here; their offline stand-in is OFFLINE-OPENING.md, which this script runs.
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


def step(block, argv, expect, code=0, cwd=HERE, env=None, run=None):
    """Run one command. It passes only if the output contains `expect` AND the exit status is `code`."""
    started = time.time()
    done = subprocess.run(run or [PY, *argv], cwd=cwd, env=env, capture_output=True, text=True)
    out = (done.stdout + done.stderr).strip()
    ok = expect in out and done.returncode == code
    seconds = time.time() - started
    results.append((block, ok, seconds))
    last = out.splitlines()[-1] if out else ""
    shown = " ".join(run[1:]) if run else "python " + " ".join(argv)
    print(f"{'ok  ' if ok else 'FAIL'} {seconds:5.1f}s  {block}: {shown}\n         -> {last}")
    if not ok:
        print(f"         expected to contain: {expect}; exit status {code}, got {done.returncode}")
    return ok


def self_check():
    """Four stub commands. Right output with the wrong exit status, and wrong output with the right status, must both fail."""
    stub = lambda text, status: [PY, "-c", f"import sys; print({text!r}); sys.exit({status})"]
    cases = [
        ("right output, right status", stub("ACCEPT", 0), "ACCEPT", 0, True),
        ("right output, wrong status", stub("ACCEPT", 3), "ACCEPT", 0, False),
        ("wrong output, right status", stub("nothing", 0), "ACCEPT", 0, False),
        ("refusal expected, status 0 given", stub("REFUSED", 0), "REFUSED", 1, False),
        ("refusal expected, status 1 given", stub("REFUSED", 1), "REFUSED", 1, True),
    ]
    good = True
    for name, run, expect, code, want in cases:
        got = step("self-check", [], expect, code, run=run)
        print(f"   {name}: step reported {'pass' if got else 'fail'}, expected {'pass' if want else 'fail'}")
        good = good and got == want
    print("self-check:", "ok" if good else "FAILED")
    return 0 if good else 1


def main():
    work = Path(tempfile.mkdtemp(prefix="masterclass-rehearse-"))
    a1 = "tasks/a1-block-card.json"
    try:
        # 14:30 and 14:40: the offline opening, in the order OFFLINE-OPENING.md teaches it.
        step("14:30 offline opening", ["measure.py", "intervals", "4"], "4        1.00 to 1.00    0.51 to 1.00")
        step("14:40 offline opening", ["factory.py", a1, "candidates/block-card-good", f"runs/rh-good-{TAG}"], "ACCEPT - protected acceptance passed", 0)
        step("14:40 offline opening", ["factory.py", a1, "candidates/block-card-tamper", f"runs/rh-tamper-{TAG}"], "REJECT - files outside the allowed paths", 1)
        step("14:40 offline opening", ["factory.py", a1, "candidates/block-card-forges-accept", f"runs/rh-forge1-{TAG}"], "ACCEPT - protected acceptance passed", 0)
        step("14:40 offline opening", ["factory_v2.py", a1, "candidates/block-card-forges-accept", f"runs/rh-forge2-{TAG}"], "exited with status 0 without unittest's OK line", 1)
        # 15:00: the good candidate and three silent-gate candidates, then show_gate.
        for name, expect, code in [("good", "ACCEPT", 0), ("gate-omitted", "REJECT", 1), ("gate-false", "REJECT", 1), ("gate-deleted", "REJECT", 1)]:
            step("15:00 silent gate", ["factory.py", a1, f"candidates/block-card-{name}", f"runs/rh-{TAG}-s-{name}"], expect, code)
        step("15:00 silent gate", ["show_gate.py", "candidates/block-card-gate-omitted"], "block_card gate: OFF (compiled to None)", 0)
        # 15:40: the vendor boundary.
        env = {**os.environ, "PYTHONPATH": str(HERE), "MANTLE_PROJECT": str(MCP / "project")}
        step("15:40 vendor boundary", ["-I", "experiments.py", "project"], "baseline", 0, cwd=MCP, env=env)
        step("15:40 vendor boundary", ["grade_variants.py", "project"], "question-wording-replaced  ACCEPT", 0, cwd=MCP, env=env)
        # 16:50: integration, then release.
        for task, cand, run in [("a2-rule-digits", "rule-digits-good", "rh-digits"), ("a3-rule-confirm", "rule-confirm-on-baseline", "rh-confirm-alone"), ("a3-rule-confirm", "rule-confirm-on-digits", "rh-confirm-rebased")]:
            step("16:50 integrate", ["factory.py", f"tasks/{task}.json", f"candidates/{cand}", f"runs/{run}-{TAG}"], "ACCEPT", 0)
        # The manifests name runs/digits-01 etc.; rewrite them to this rehearsal's runs in a temporary copy.
        manifests = work / "integration"
        shutil.copytree(HERE / "integration", manifests)
        for path in manifests.glob("*.json"):
            text = path.read_text().replace("runs/digits-01", f"runs/rh-digits-{TAG}").replace("runs/confirm-alone", f"runs/rh-confirm-alone-{TAG}").replace("runs/confirm-rebased", f"runs/rh-confirm-rebased-{TAG}")
            path.write_text(text)
        trunk = str(work / "trunk")
        step("16:50 integrate", ["integrate.py", trunk, str(manifests / "m1-digits.json")], "MERGED", 0)
        step("16:50 integrate", ["integrate.py", trunk, str(manifests / "m2-confirm-on-baseline.json")], "STALE_BASE", 1)
        step("16:50 integrate", ["integrate.py", trunk, str(manifests / "m3-confirm-on-digits.json")], "MERGED", 0)
        rel, appr = str(work / "releases"), work / "approvals"
        appr.mkdir()
        good = f"runs/rh-good-{TAG}/decision.json"
        step("16:50 release", ["approve.py", "allow", rel, "reviewer"], "approvers: reviewer", 0)
        step("16:50 release", ["approve.py", "sign", "candidates/block-card-good", "codex", str(appr / "by-codex.json")], "codex approves", 0)
        step("16:50 release", ["release.py", "publish", good, "candidates/block-card-good", str(appr / "by-codex.json"), rel], "'codex' is not on the list", 1)
        step("16:50 release", ["approve.py", "sign", "candidates/block-card-good", "reviewer", str(appr / "by-reviewer.json")], "reviewer approves", 0)
        step("16:50 release", ["release.py", "publish", good, "candidates/block-card-good", str(appr / "by-reviewer.json"), rel], "PUBLISHED", 0)
        step("16:50 release", ["release.py", "verify", rel], "SERVING", 0)
        # 17:10: report and decide.
        step("17:10 report", ["measure.py", "report", "agent-runs/claude-code-2026-10-15", "agent-runs/codex-2026-10-15"], "accepted: 18 of 18 = 1.00", 0)
        step("17:10 report", ["measure.py", "needed", "0.9"], "35 runs, 0 of them failing", 0)
        step("17:10 report", ["policy.py", "what-if", "policy.json", "35", "35"], "ELIGIBLE for promotion", 0)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("\nper block (seconds):")
    blocks = {}
    for block, ok, seconds in results:
        total, all_ok = blocks.get(block, (0.0, True))
        blocks[block] = (total + seconds, all_ok and ok)
    for block, (total, all_ok) in blocks.items():
        print(f"  {'ok  ' if all_ok else 'FAIL'} {total:6.1f}  {block}")
    failed = [b for b, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} steps matched." + ("" if not failed else " FAILED: " + ", ".join(sorted(set(failed)))))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(self_check() if "--self-check" in sys.argv[1:] else main())
