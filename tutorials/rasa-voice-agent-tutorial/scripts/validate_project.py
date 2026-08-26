#!/usr/bin/env python3
"""Validate the Atlas skills, printing every finding the engine reports.

Usage:
    make validate
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

# The engine logs one debug line per skill and tool; only findings matter here.
logging.getLogger().setLevel(logging.ERROR)

_TTY = sys.stdout.isatty()
GREEN = "\033[92m" if _TTY else ""
RED = "\033[91m" if _TTY else ""
RESET = "\033[0m" if _TTY else ""


def main() -> int:
    try:
        from rasa.mantle.validation import validate_project
        from rasa.exceptions import ValidationError
    except ImportError as exc:
        print(f"{RED}Could not import the Rasa validator: {exc}{RESET}")
        print("Run: make install")
        return 1

    try:
        validate_project(PROJECT_ROOT)
    except ValidationError as exc:
        print(f"{RED}{exc}{RESET}")
        return 1

    print(f"{GREEN}✓ Project is valid.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
