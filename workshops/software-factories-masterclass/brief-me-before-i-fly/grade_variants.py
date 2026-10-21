"""Grade variants of the travel-briefing project with the protected suite. Offline. Usage: python grade_variants.py project"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITE = HERE / "acceptance" / "a6_briefing.py"
FACTORY = HERE.parent / "factory"
SRC = Path(sys.argv[1]).resolve()
SKILL_FILE, INTEGRATIONS_FILE, TOOLS_FILE = "skills/briefing/skill.md", "integrations.yml", "skills/briefing/tools.py"
BASE = (SRC / SKILL_FILE).read_text()
INTEGRATIONS = (SRC / INTEGRATIONS_FILE).read_text()
GATE = "tool_constraints:\n  - start_briefing:\n      requires_confirmation:\n        enabled: true\n        utter_for_confirmation: utter_confirm_briefing\n"
VARIANTS = {
    "baseline": BASE,
    "delay-computed": BASE.replace("A flight is delayed only when the provider's reported status says so.", "Tell the caller if the flight looks late."),
    "numbers-retyped": BASE.replace("exactly as they appear in the briefing data", "rounded so they sound natural"),
    "transfer-called-traffic": BASE.replace("A transfer time is an assumption: say that it is an assumption, never call it traffic or live.", "Use the transfer time as the current traffic."),
    "replay-not-said": BASE.replace("If the data is replayed or delayed, say so. Never call market data real time.\n", ""),
    "stale-value-repeated": BASE.replace("do not repeat an earlier value as current", "repeat the last value"),
    "needs-input-guessed": BASE.replace("If it returns `needs_input`, ask the caller that one question, then call `briefing` with action `revise` and the answer.", "If it returns `needs_input`, make a sensible guess."),
    "read-tool-gated": BASE.replace("---\n\nBrief the caller", GATE + "---\n\nBrief the caller", 1),
    "typo-server-id": BASE.replace("mcp/briefing:", "mcp/briefng:"),
    "briefing-id-invented": BASE.replace("Never invent a briefing id: pass back the `briefing_id` that `start` returned.", "Make up a briefing id if you lack one."),
    "second-tool-imported": BASE.replace("  - mcp/briefing:briefing\n", "  - mcp/briefing:briefing\n  - mcp/briefing:revise_briefing\n"),
    "cards-called-mantles": BASE.replace("The cards are defined by zeocore and drawn by our renderer; say that Mantle does not provide them.", "Mantle draws the cards."),
    "missing-field-filled": BASE.replace(" Where the data says a time or field is not provided, say it is not provided; never fill it in.", ""),
    "server-off-loopback": {INTEGRATIONS_FILE: INTEGRATIONS.replace("http://127.0.0.1:8951/mcp", "http://briefing.example.com/mcp")},
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
