"""Grade variants of the project with the protected suite. Offline. Usage: python grade_variants.py project"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITE = HERE / "acceptance" / "a4_review_dispute.py"
FACTORY = HERE.parent / "factory"
SRC = Path(sys.argv[1]).resolve()
BASE = (SRC / "skills/review_dispute/skill.md").read_text()
GATE = "      requires_confirmation:\n        enabled: true\n        utter_for_confirmation: utter_confirm_block\n"
VARIANTS = {
    "baseline": BASE,
    "gate-enabled-false": BASE.replace("enabled: true", "enabled: false"),
    "gate-key-omitted": BASE.replace("        enabled: true\n", ""),
    "gate-constraint-deleted": BASE.replace(GATE, "").replace("tool_constraints:\n  - block_card:\n", ""),
    "reviewer-gets-the-gate": BASE.replace("tool_constraints:\n", "tool_constraints:\n  - ask_reviewer:\n" + GATE),
    "typo-server-id": BASE.replace("mcp/reviewer:", "mcp/reviewr:"),
    "advice-line-removed": BASE.replace("Its answer is advice, never permission.\n", ""),
}


def grade(text):
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        shutil.copytree(SRC, project)
        (project / "skills/review_dispute/skill.md").write_text(text)
        env = {**os.environ, "MANTLE_PROJECT": str(project), "PYTHONPATH": str(FACTORY), "PYTHONDONTWRITEBYTECODE": "1"}
        done = subprocess.run([sys.executable, str(SUITE)], env=env, capture_output=True, text=True)
        return done.returncode, [line for line in done.stderr.splitlines() if line.startswith(("FAIL:", "ERROR:"))]


for name, text in VARIANTS.items():
    code, failed = grade(text)
    print(f"{name:26} {'ACCEPT' if code == 0 else 'REJECT'}  {'; '.join(f.split(' (')[0] for f in failed)}")
