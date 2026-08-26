#!/usr/bin/env python3
"""Pre-flight check: credentials, project shape, and the voice configuration.

Runs before `make train` so a missing key is a named finding rather than a
stack trace forty seconds into a training run. Deliberately dependency-light so
it works before `uv sync` has finished.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (variable, what it is for, where to get it, needed to train?)
SECRETS = [
    ("RASA_LICENSE", "Rasa Pro Developer Edition licence", 
     "https://rasa.com/rasa-pro-developer-edition-license-key-request/", True),
    ("OPENAI_API_KEY", "LLM for routing and conversation",
     "https://platform.openai.com/api-keys", True),
    ("DEEPGRAM_API_KEY", "Speech-to-text (Flux)",
     "https://console.deepgram.com/", False),
    ("RIME_API_KEY", "Text-to-speech (Mist v2)",
     "https://rime.ai/", False),
]

REQUIRED_FILES = [
    "agent.yml", "integrations.yml", "memory.yml", "responses.yml",
    "skills/check_balance/skill.md", "skills/transfer_money/skill.md",
    "skills/report_lost_card/skill.md", "skills/transaction_history/skill.md",
    "lib/bank.py", "tools/profile.py",
]

GREEN, RED, YELLOW, DIM, RESET = (
    ("\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m")
    if sys.stdout.isatty() else ("", "", "", "", "")
)


def _load_env() -> None:
    """Read .env without requiring python-dotenv to be installed yet."""
    for candidate in (ROOT / ".env", ROOT.parent.parent / ".env"):
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    _load_env()
    failures = 0

    print(f"\n{DIM}Vela — pre-flight{RESET}\n")

    print("Credentials")
    for name, purpose, url, needed_to_train in SECRETS:
        value = os.environ.get(name, "").strip()
        if value:
            print(f"  {GREEN}OK{RESET}    {name:<18} {DIM}{purpose}{RESET}")
        elif needed_to_train:
            print(f"  {RED}MISSING{RESET} {name:<18} {purpose}")
            print(f"          {DIM}get one: {url}{RESET}")
            failures += 1
        else:
            # Voice keys are runtime-only: training succeeds without them, and
            # saying so is more useful than a blanket red cross.
            print(f"  {YELLOW}unset{RESET} {name:<18} {purpose}")
            print(f"          {DIM}needed for `make inspect`, not `make train` — {url}{RESET}")

    print("\nProject")
    for rel in REQUIRED_FILES:
        if (ROOT / rel).is_file():
            print(f"  {GREEN}OK{RESET}    {rel}")
        else:
            print(f"  {RED}MISSING{RESET} {rel}")
            failures += 1

    print("\nVoice configuration")
    try:
        import yaml  # noqa: PLC0415

        integrations = yaml.safe_load((ROOT / "integrations.yml").read_text())
        inspector = (integrations.get("channels") or {}).get("inspector") or {}
        asr = (inspector.get("asr") or {}).get("name", "?")
        tts = (inspector.get("tts") or {}).get("name", "?")
        print(f"  {GREEN}OK{RESET}    asr={asr}  tts={tts}")
        if tts != "rime":
            print(f"  {YELLOW}note{RESET}  this resource is about Rime TTS; tts is {tts!r}")
    except ImportError:
        print(f"  {DIM}skipped (pyyaml not installed yet — run `make install`){RESET}")

    if failures:
        print(f"\n{RED}{failures} problem(s) to fix before training.{RESET}\n")
        return 1
    print(f"\n{GREEN}Ready. Next: make train{RESET}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
