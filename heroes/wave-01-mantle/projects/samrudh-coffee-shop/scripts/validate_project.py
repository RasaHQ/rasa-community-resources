#!/usr/bin/env python3
"""Validate the Artisan Roast skills and project configuration for Rasa Mantle."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

# Silence noisy debug logs, only findings matter
logging.getLogger().setLevel(logging.ERROR)

_TTY = sys.stdout.isatty()
GREEN = "\033[92m" if _TTY else ""
RED = "\033[91m" if _TTY else ""
RESET = "\033[0m" if _TTY else ""


def main() -> int:
    try:
        try:
            from rasa.mantle.validation import validate_project
        except ImportError:
            from rasa.calm_v2.validation import validate_project
        from rasa.exceptions import ValidationError
    except ImportError as exc:
        print(f"{RED}Could not import the Rasa Mantle validator: {exc}{RESET}")
        print("Run: make install")
        return 1

    try:
        validate_project(PROJECT_ROOT)
    except ValidationError as exc:
        print(f"{RED}{exc}{RESET}")
        return 1

    print(f"{GREEN}✓ Artisan Roast project structure and skills are valid.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
