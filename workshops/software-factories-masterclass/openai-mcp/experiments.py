"""Variants of the project's skill.md, checked by the real engine, offline. Prints what Mantle reports."""
import logging
import shutil
import sys
import tempfile
from pathlib import Path

import structlog

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))

from rasa.mantle.skills.markdown_skill_compiler import compile_markdown_skill  # noqa: E402
from rasa.mantle.validation import collect_project_findings  # noqa: E402

SRC = Path(sys.argv[1])
BASE = (SRC / "skills/review_dispute/skill.md").read_text()
GATE = "      requires_confirmation:\n        enabled: true\n        utter_for_confirmation: utter_confirm_block\n"
ASK_GATE = GATE
VARIANTS = {
    "baseline": BASE,
    "typo-server-id": BASE.replace("mcp/reviewer:", "mcp/reviewr:"),
    "typo-tool-name-in-gate": BASE.replace("  - block_card:", "  - block_cards:"),
    "gate-on-mcp-tool": BASE.replace("tool_constraints:\n", "tool_constraints:\n  - ask_reviewer:\n" + ASK_GATE),
    "gate-on-mcp-tool-enabled-false": BASE.replace("tool_constraints:\n", "tool_constraints:\n  - ask_reviewer:\n" + ASK_GATE.replace("true", "false")),
    "local-gate-enabled-false": BASE.replace("enabled: true", "enabled: false"),
    "local-gate-omitted": BASE.replace("        enabled: true\n", ""),
    "local-gate-deleted": BASE.replace(GATE, "").replace("tool_constraints:\n  - block_card:\n", ""),
}
for name, text in VARIANTS.items():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "p"
        shutil.copytree(SRC, project)
        (project / "skills/review_dispute/skill.md").write_text(text)
        try:
            found = [(f.code, f.message[:90]) for f in collect_project_findings(project)]
            skill = compile_markdown_skill(project / "skills/review_dispute/skill.md")
            gates = {t.name: (None if t.requires_confirmation is None else t.requires_confirmation.enabled) for t in skill.tools}
            print(f"{name:34} findings={len(found)} gates={gates}")
            for item in found:
                print("    ", item)
        except Exception as error:  # the engine's own refusal is the result
            print(f"{name:34} RAISED {type(error).__name__}: {str(error)[:140]}")
