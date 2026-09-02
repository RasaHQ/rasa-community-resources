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
    ("DEEPGRAM_API_KEY", "First in the ASR chain, second in the TTS chain",
     "https://console.deepgram.com/", False),
    ("RIME_API_KEY", "Vela's own voice — she still speaks without it",
     "https://rime.ai/", False),
]

# Built-in Rasa engines are not in the router's CATALOGUE, so their keys are
# named here. Anything absent from both is reported as unknown rather than as
# configured, because guessing would turn a missing key into a silent skip.
BUILTIN_KEYS = {
    "deepgram": "DEEPGRAM_API_KEY",
    "rime": "RIME_API_KEY",
    "azure": "AZURE_SPEECH_API_KEY",
    "cartesia": "CARTESIA_API_KEY",
}

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


def _key_for(name: str) -> str | None:
    """The environment variable a provider entry needs, if one is known."""
    if name in BUILTIN_KEYS:
        return BUILTIN_KEYS[name]
    try:
        from voicerouter.providers import CATALOGUE  # noqa: PLC0415
    except ImportError:
        return None
    for entry in CATALOGUE:
        if entry.dotted_path == name:
            # Local models and credential-chain vendors have no single variable.
            return entry.env_var if entry.env_var.endswith("_KEY") else ""
    return None


def _report_chains(inspector: dict) -> int:
    """Print each chain and say which links this environment can actually use.

    The router skips a provider whose credentials are absent rather than failing
    the call. That is the right behaviour on a live call and a terrible surprise
    at setup time, so it is spelled out here instead.
    """
    problems = 0
    for half in ("asr", "tts"):
        config = inspector.get(half) or {}
        name = config.get("name", "?")
        if not str(name).startswith("voicerouter."):
            print(f"  {YELLOW}note{RESET}  {half} is {name!r}, not routed — "
                  f"this resource is about the routed stack")
            continue

        usable = 0
        print(f"  {half}:")
        for raw in config.get("providers") or []:
            label = raw.get("label") or str(raw.get("name", "?")).split(".")[-1]
            key = _key_for(raw.get("name", ""))
            if key is None:
                print(f"    {YELLOW}?{RESET}      {label} — no known credential; "
                      f"run `make probe` in the pattern to check it")
                usable += 1
            elif key == "":
                print(f"    {GREEN}OK{RESET}     {label} — local or credential chain")
                usable += 1
            elif os.environ.get(key):
                print(f"    {GREEN}OK{RESET}     {label} — {key} is set")
                usable += 1
            else:
                print(f"    {DIM}skip{RESET}   {label} — {key} is not set")

        if usable == 0:
            print(f"    {RED}none of the {half} chain is usable{RESET} — "
                  f"the agent has no {half} at all")
            problems += 1
        elif usable == 1:
            print(f"    {YELLOW}only one link is usable — there is nothing to "
                  f"fail over to{RESET}")
    return problems


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

    print("\nVoice chains")
    try:
        import yaml  # noqa: PLC0415

        integrations = yaml.safe_load((ROOT / "integrations.yml").read_text())
        inspector = (integrations.get("channels") or {}).get("inspector") or {}
        failures += _report_chains(inspector)
    except ImportError:
        print(f"  {DIM}skipped (pyyaml not installed yet — run `make install`){RESET}")

    if failures:
        print(f"\n{RED}{failures} problem(s) to fix before training.{RESET}\n")
        return 1
    print(f"\n{GREEN}Ready. Next: make train{RESET}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
