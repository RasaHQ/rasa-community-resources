"""Grade variants of the travel-desk project with the protected suite. Offline. Usage: python grade_variants.py project"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITE = HERE / "acceptance" / "a6_desk_widgets.py"
FACTORY = HERE.parent / "factory"
SRC = Path(sys.argv[1]).resolve()
SKILL_FILE, INTEGRATIONS_FILE, TOOLS_FILE = "skills/desk/skill.md", "integrations.yml", "skills/desk/tools.py"
BASE = (SRC / SKILL_FILE).read_text()
INTEGRATIONS = (SRC / INTEGRATIONS_FILE).read_text()
GATE = "tool_constraints:\n  - ask_desk_agent:\n      requires_confirmation:\n        enabled: true\n        utter_for_confirmation: utter_confirm_desk\n"
VARIANTS = {
    "baseline": BASE,
    "delay-claimed": BASE.replace("Never say a flight is delayed or on time.", "Say whether the flight is on time."),
    "numbers-retyped": BASE.replace("Say the numbers it returns exactly as they appear in its data.", "Round the numbers so they sound natural."),
    "read-only-tool-gated": BASE.replace("import_tools:", GATE + "import_tools:", 1) if False else BASE.replace("---\n\nAnswer", GATE + "---\n\nAnswer", 1),
    "typo-server-id": BASE.replace("mcp/desk:", "mcp/dsk:"),
    "rate-date-dropped": BASE.replace("An exchange rate is a daily reference rate: say its date.\n", ""),
    "stale-answer-allowed": BASE.replace("If the tool returns no data, say so and do not repeat an earlier answer.\n", ""),
    "server-off-loopback": {INTEGRATIONS_FILE: INTEGRATIONS.replace("http://127.0.0.1:8951/mcp", "http://desk.example.com/mcp")},
    "local-tool-code-added": {TOOLS_FILE: "async def noop():\n    return {}\n"},
}


def grade(edit):
    files = edit if isinstance(edit, dict) else {SKILL_FILE: edit}
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        shutil.copytree(SRC, project)
        for name, text in files.items():
            (project / name).write_text(text)
        env = {**os.environ, "MANTLE_PROJECT": str(project), "PYTHONPATH": str(FACTORY), "PYTHONDONTWRITEBYTECODE": "1"}
        done = subprocess.run([sys.executable, str(SUITE)], env=env, capture_output=True, text=True)
        return done.returncode, [line for line in done.stderr.splitlines() if line.startswith(("FAIL:", "ERROR:"))]


for name, text in VARIANTS.items():
    code, failed = grade(text)
    print(f"{name:26} {'ACCEPT' if code == 0 else 'REJECT'}  {'; '.join(f.split(' (')[0] for f in failed)}")
