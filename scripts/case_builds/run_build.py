#!/usr/bin/env python3
"""Run a case build's scripted conversations against its live agent.

    python3 scripts/case_builds/run_build.py examples/<build> --budget-usd 4
    python3 scripts/case_builds/run_build.py examples/<build> --only normal-policy-active --label estimate

Trains the project, starts `rasa run --enable-api` through the usage launcher,
drives every conversation in <build>/case-build/conversations.json, and writes
results.json, summary.md, usage.jsonl and one tracker per conversation under
<build>/case-build/results/<label or timestamp>/. Every run is added to
<build>/case-build/results/spend-ledger.json, and --budget-usd caps the
ledger total: a conversation whose projected cost would cross it is skipped.

This makes live, billed model calls. Keys come from the environment or the
project/repo .env, and are never printed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import REPO_ROOT, ledger_total, run_spec  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project", help="build project, e.g. examples/mantle-text-insurance-policy-status-gemini")
    parser.add_argument("--budget-usd", type=float, required=True, help="cap on this build's total recorded spend")
    parser.add_argument("--only", help="comma-separated conversation ids")
    parser.add_argument("--label", help="results folder name (default: UTC timestamp)")
    parser.add_argument("--skip-train", action="store_true", help="reuse the newest model in models/")
    args = parser.parse_args()

    project = Path(args.project)
    if not project.is_absolute():
        project = REPO_ROOT / project
    spent = ledger_total(project)
    if spent >= args.budget_usd:
        print(f"Recorded spend {spent} USD already meets the {args.budget_usd} USD cap; nothing run.")
        return 2
    report = run_spec(
        project,
        only=args.only.split(",") if args.only else None,
        budget_usd=args.budget_usd,
        train=not args.skip_train,
        label=args.label,
    )
    s = report["summary"]
    print(json.dumps({k: s[k] for k in ("conversations_run", "passed", "failed", "turn_latency_ms",
                                        "cost_usd", "spent_before_usd")}, indent=1))
    print(f"results: {report['out_dir']}")
    return 0 if s["failed"] == 0 and not s["skipped"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
