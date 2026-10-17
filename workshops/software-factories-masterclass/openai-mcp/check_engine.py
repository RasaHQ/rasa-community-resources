"""Offline engine checks on the project folder given as the first argument. No model, licence or network."""
import logging
import sys
from pathlib import Path

import structlog

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))

from rasa.mantle.skills.markdown_skill_compiler import compile_markdown_skill  # noqa: E402
from rasa.mantle.validation import collect_project_findings  # noqa: E402

project = Path(sys.argv[1])
print("findings:", [(f.code, f.message[:120]) for f in collect_project_findings(project)])
skill = compile_markdown_skill(project / "skills" / "review_dispute" / "skill.md")
print("skill id:", skill.id)
for tool in skill.tools:
    gate = tool.requires_confirmation
    print("tool", tool.name, "gate:", None if gate is None else (gate.enabled, getattr(gate, "utter_for_confirmation", None)))
print("imports:", list(getattr(skill, "import_tool_names", [])))
