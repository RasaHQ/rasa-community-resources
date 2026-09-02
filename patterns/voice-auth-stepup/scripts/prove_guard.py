#!/usr/bin/env python3
"""Delete the tier guard, prove the suite goes red, put it back.

    make prove

A negative test that has never been watched fail is indistinguishable from a
negative test that asserts nothing. This repository has shipped that exact
defect before — a "licence-clean" test whose assertions were vacuous, under
which encumbered audio passed every run — so the pattern that claims a security
property ships the check for its own check.

What this does, in order:

1. Copy `tools/banking.py` aside.
2. Remove the four-line guard from `reissue_card` — the exact block, matched
   verbatim, so a refactor that moves it makes this script fail loudly instead
   of silently removing nothing and reporting success.
3. Run the suite. It MUST fail. If it passes, the guard tests are decorative and
   this script exits non-zero saying so.
4. Restore the file (in a `finally`, so an interrupt cannot leave the guard out).
5. Run the suite again. It MUST pass, proving the restore was clean.

Exit code 0 means: the guard is load-bearing, and it is back in place.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent.parent
TARGET = HERE / "tools" / "banking.py"

# Matched verbatim on purpose. A fuzzy match could "remove" nothing and let this
# script report a pass it did not earn.
GUARD = (
    '    try:\n'
    '        require_tier("reissue_card", context)\n'
    '    except StepUpRequired as exc:\n'
    '        return _step_up(exc, context)\n'
    '\n'
)

GREEN, RED, YELLOW, BLUE, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[34m", "\033[0m"
)


def run_suite() -> bool:
    """True when the eval suite passes."""
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
        cwd=HERE,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def main() -> int:
    source = TARGET.read_text()

    if GUARD not in source:
        print(f"{RED}Guard block not found verbatim in {TARGET.name}.{RESET}")
        print("The guard moved or was reformatted. Update scripts/prove_guard.py")
        print("to match — do NOT loosen the match to make this pass.")
        return 2

    backup = pathlib.Path(tempfile.mkdtemp()) / "banking.py"
    shutil.copy2(TARGET, backup)

    try:
        print(f"{BLUE}1. removing the tier guard from reissue_card…{RESET}")
        TARGET.write_text(source.replace(GUARD, "", 1))

        print(f"{BLUE}2. running the eval suite without it…{RESET}")
        if run_suite():
            print()
            print(f"{RED}FAIL: the suite PASSED with the guard removed.{RESET}")
            print(f"{RED}The negative tests assert nothing. They are a docstring,{RESET}")
            print(f"{RED}not a guard. Fix the tests before trusting this pattern.{RESET}")
            return 1
        print(f"{GREEN}   red, as it must be.{RESET}")
    finally:
        # Restore in a finally: an interrupted run must never leave the guard out.
        shutil.copy2(backup, TARGET)
        print(f"{BLUE}3. guard restored.{RESET}")

    print(f"{BLUE}4. re-running to prove the restore was clean…{RESET}")
    if not run_suite():
        print(f"{RED}FAIL: suite is still red after restoring. Check git diff.{RESET}")
        return 1

    print()
    print(f"{GREEN}The guard is load-bearing:{RESET}")
    print(f"{GREEN}  without it the suite fails; with it the suite passes.{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
