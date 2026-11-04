#!/usr/bin/env python3
"""Pre-flight check for the TerraEnergy agent project.

Run from the project root:  make verify   (or: uv run python scripts/verify_setup.py)

Checks, without needing a license or network:
  1. a .env file exists next to this project;
  2. the mandatory keys (RASA_LICENSE, MISTRAL_API_KEY) are non-empty;
  3. every key declared in [tool.rasa-catalog] required-secrets is present;
  4. the Mantle engine (``rasa.mantle``) is importable in the active environment;
  5. the agent project validates (rasa.mantle.validation.validate_project).
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK = "  \u2713"
BAD = "  \u2717"


def fail(msg: str) -> None:
    print(f"{BAD} {msg}")
    sys.exit(1)


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> None:
    print("TerraEnergy — pre-flight check\n")

    env_file = ROOT / ".env"
    if not env_file.is_file():
        fail("no .env file. Run: make env")
    env = parse_env(env_file)
    print(f"{OK} .env found")

    required = ["RASA_LICENSE", "MISTRAL_API_KEY"]
    try:
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        declared = data.get("tool", {}).get("rasa-catalog", {}).get("required-secrets", [])
        required = list(dict.fromkeys(required + declared))
    except (OSError, tomllib.TOMLDecodeError) as exc:  # pragma: no cover
        fail(f"cannot read pyproject.toml: {exc}")

    missing = [key for key in required if not env.get(key)]
    if missing:
        fail("missing required value(s) in .env: " + ", ".join(missing))
    print(f"{OK} required values set: {', '.join(required)}")

    try:
        import rasa.mantle  # noqa: F401
    except ImportError:
        fail("rasa.mantle is not importable — run: make install (rasa-pro==3.20.0.dev6)")
    print(f"{OK} rasa.mantle importable")

    try:
        from rasa.mantle.validation import validate_project

        validate_project(ROOT)
    except Exception as exc:  # noqa: BLE001 — surface the real validation error
        fail(f"agent project did not validate: {exc}")
    print(f"{OK} agent project validates")

    print("\n\u2713 Setup looks good. Next: make train && make run")


if __name__ == "__main__":
    main()