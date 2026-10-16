#!/usr/bin/env python3
"""Show what Mantle makes of a candidate: its own authoring findings, and the compiled confirmation gate.

    python show_gate.py candidates/block-card-gate-omitted

Lays the candidate over the baseline in a throwaway folder, asks the engine's project validation what it objects
to, and compiles the block_card skill. Prints the gate as Mantle compiled it. This is a viewer, not a judge:
the factory decides, from the protected acceptance, not from this output.
"""
import logging
import shutil
import sys
import tempfile
from pathlib import Path

import structlog

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
from rasa.mantle.skills.markdown_skill_compiler import compile_markdown_skill  # noqa: E402
from rasa.mantle.validation import collect_project_findings  # noqa: E402

ROOT = Path(__file__).resolve().parent


def main(candidate):
    candidate = Path(candidate)
    with tempfile.TemporaryDirectory(prefix="show-gate-") as scratch:
        project = Path(scratch) / "product"
        shutil.copytree(ROOT / "product", project)
        (project / "skills").mkdir(exist_ok=True)
        for path in sorted(p for p in candidate.rglob("*") if p.is_file()):
            target = Path(scratch) / path.relative_to(candidate)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        findings = collect_project_findings(project)
        print("engine findings: %d" % len(findings))
        for finding in findings:
            print("  " + finding.code)
        skill_file = project / "skills" / "block_card" / "skill.md"
        if not skill_file.exists():
            print("no block_card skill in this candidate")
            return 0
        skill = compile_markdown_skill(skill_file)
        gates = {tool.name: tool.requires_confirmation for tool in skill.tools}
        gate = gates.get("block_card")
        if gate is not None and gate.enabled:
            print("block_card gate: ON, waits for the caller (prompt: %s)" % gate.utter_for_confirmation)
        else:
            print("block_card gate: OFF (compiled to %r)" % (gate,))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
