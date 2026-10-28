#!/usr/bin/env python3
"""Rehearse the masterclass commands in session order, offline, and print each block's time and result.

    uv run python rehearse.py                (from this folder, after `uv sync --frozen`)
    uv run python rehearse.py --self-check   (proves that a wrong exit status or wrong output fails a step)

It runs the commands of FACILITATOR.md that need only this repository: no network, no key, no model.
It writes under runs/ and a temporary folder, both ignored by git. A step passes only if its output contains
the expected text AND the command exits with the expected status (refusals and rejections exit 1 on purpose).
Some steps also check the landing lines the facilitator will say aloud: the six variants that must be REJECTED
and the one that is ACCEPTED, no engine findings, and the reason a silent-gate candidate is rejected.
A FAIL means that block would not behave as FACILITATOR.md says on this machine.
The two online-lesson blocks are not here; their offline stand-in is OFFLINE-OPENING.md, which this script runs.
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


# The steps need no key, token or licence, so they do not get yours: only what a command needs to start.
SAFE_ENV = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "USER")}


def step(block, argv, expect, code=0, cwd=HERE, env=None, run=None, check=None, decision=None):
    """Run one command. It passes only if the output contains every `expect` text, the exit status is `code`,
    `check(output)` (if given) is true, and the decision file (if given) contains its text."""
    started = time.time()
    done = subprocess.run(run or [PY, *argv], cwd=cwd, env=env or SAFE_ENV, capture_output=True, text=True)
    out = (done.stdout + done.stderr).strip()
    texts = (expect,) if isinstance(expect, str) else tuple(expect)
    ok = all(text in out for text in texts) and done.returncode == code
    if ok and check is not None:
        ok = bool(check(out))
    if ok and decision is not None:
        path, text = decision
        try:
            ok = text in (cwd / path).read_text()
        except OSError:
            ok = False
    seconds = time.time() - started
    results.append((block, ok, seconds))
    last = out.splitlines()[-1] if out else ""
    shown = " ".join(run[1:]) if run else "python " + " ".join(argv)
    print(f"{'ok  ' if ok else 'FAIL'} {seconds:5.1f}s  {block}: {shown}\n         -> {last}")
    if not ok:
        print(f"         expected to contain: {', '.join(texts)}; exit status {code}, got {done.returncode}" + ("; a further check failed" if check or decision else ""))
    return ok


VARIANTS = [
    ("baseline", "ACCEPT"),
    ("gate-enabled-false", "REJECT"),
    ("gate-key-omitted", "REJECT"),
    ("gate-constraint-deleted", "REJECT"),
    ("reviewer-gets-the-gate", "REJECT"),
    ("typo-server-id", "REJECT"),
    ("advice-line-removed", "REJECT"),
    ("question-wording-replaced", "ACCEPT"),
]


def variants_ok(out):
    """grade_variants prints one line per variant: exactly six REJECTs, the baseline ACCEPT and the known-gap ACCEPT."""
    got = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] in ("ACCEPT", "REJECT"):
            got[parts[0]] = parts[1]
    return got == dict(VARIANTS)


def experiments_ok(out):
    """The baseline compiles with no findings and the engine raised on nothing."""
    baseline = [line for line in out.splitlines() if line.startswith("baseline")]
    return len(baseline) == 1 and "findings=0" in baseline[0] and "RAISED" not in out


def self_check():
    """Stub commands, not the factory. Right output with the wrong exit status, wrong output with the right status, a variant table with one REJECT turned into ACCEPT, and a RAISED line must each fail."""
    stub = lambda text, status: [PY, "-c", f"import sys; print({text!r}); sys.exit({status})"]
    cases = [
        ("right output, right status", stub("ACCEPT", 0), "ACCEPT", 0, True),
        ("right output, wrong status", stub("ACCEPT", 3), "ACCEPT", 0, False),
        ("wrong output, right status", stub("nothing", 0), "ACCEPT", 0, False),
        ("refusal expected, status 0 given", stub("REFUSED", 0), "REFUSED", 1, False),
        ("refusal expected, status 1 given", stub("REFUSED", 1), "REFUSED", 1, True),
    ]
    table = "\n".join(f"{name:28} {decision}" for name, decision in VARIANTS)
    weakened = "\n".join(f"{name:28} {'ACCEPT' if name == 'gate-key-omitted' else decision}" for name, decision in VARIANTS)
    cases += [
        ("variant table as expected", stub(table, 0), "baseline", 0, True, variants_ok),
        ("one REJECT turned into ACCEPT", stub(weakened, 0), "baseline", 0, False, variants_ok),
        ("baseline RAISED", stub("baseline findings=0\nbaseline RAISED", 0), "baseline", 0, False, experiments_ok),
        ("baseline clean", stub("baseline findings=0", 0), "baseline", 0, True, experiments_ok),
    ]
    good = True
    for case in cases:
        name, run, expect, code, want = case[:5]
        got = step("self-check", [], expect, code, run=run, check=case[5] if len(case) > 5 else None)
        print(f"   {name}: step reported {'pass' if got else 'fail'}, expected {'pass' if want else 'fail'}")
        good = good and got == want
    missing = step("self-check", [], "ACCEPT", 0, run=stub("ACCEPT", 0), decision=("no-such-decision.json", "x"))
    print(f"   decision file missing: step reported {'pass' if missing else 'fail'}, expected fail")
    good = good and not missing
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
        step("15:00 silent gate", ["factory.py", a1, "candidates/block-card-good", f"runs/rh-{TAG}-s-good"], "ACCEPT - protected acceptance passed", 0)
        for name in ("gate-omitted", "gate-false", "gate-deleted"):
            run_dir = f"runs/rh-{TAG}-s-{name}"
            # The rejection must be for the reason the facilitator says aloud: the engine compiled the gate away.
            step("15:00 silent gate", ["factory.py", a1, f"candidates/block-card-{name}", run_dir], "REJECT - the protected acceptance suite failed", 1,
                 decision=(f"{run_dir}/decision.json", "the engine compiled the confirmation gate away"))
        step("15:00 silent gate", ["show_gate.py", "candidates/block-card-gate-omitted"], ("engine findings: 0", "block_card gate: OFF (compiled to None)"), 0)
        # 15:40: the vendor boundary.
        # FACILITATOR.md tells the facilitator to type ../factory/.venv/bin/python from openai-mcp/; run exactly that.
        pack_python = str(HERE / ".venv" / "bin" / "python") if (HERE / ".venv" / "bin" / "python").exists() else PY
        step("15:40 vendor boundary", [], "baseline", 0, cwd=MCP, run=[pack_python, "-I", "experiments.py", "project"], check=experiments_ok)
        step("15:40 vendor boundary", [], "question-wording-replaced", 0, cwd=MCP, run=[pack_python, "grade_variants.py", "project"], check=variants_ok)
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
    args = sys.argv[1:]
    if args not in ([], ["--self-check"]):
        print("usage: python rehearse.py [--self-check]")
        sys.exit(2)
    sys.exit(self_check() if args else main())
