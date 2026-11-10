#!/usr/bin/env python3
"""factory v2: the same Mantle factory with a stricter verdict. factory.py (v1) is left as it was.

    python factory_v2.py tasks/a1-block-card.json candidates/block-card-forges-accept runs/forges-v2

v1 records ACCEPT when the acceptance process exits with status 0. The engine imports a candidate's tools.py
inside that process, so a candidate can end it early with status 0 and be accepted
(candidates/block-card-forges-accept does). v2 requires unittest's own closing lines: "Ran N tests" with N above
zero, and "OK" last. Code that prints those lines itself would still pass; the full fix keeps candidate code
out of the process that decides.

Everything else is v1's: this file only replaces factory.run_tests and calls factory.main. integrate.py and
recover.py import and run v1 and keep v1's verdict until they are pointed here.
Exit status 0 ACCEPT, 1 REJECT, 2 the factory could not run, 3 NOT_READY.
"""
import re
import subprocess
import sys
from pathlib import Path

import factory

def verdict(result):
    """A pass needs more than exit status 0: unittest's own closing lines, with at least one test counted.

    A candidate's code runs inside the grading process, so a bare exit status can be forged by ending
    the process early. Printing the two closing lines instead takes deliberate effort.
    """
    lines = result.stderr.strip().splitlines() or [""]
    ran = re.search(r"^Ran (\d+) tests? in ", result.stderr, re.M)
    ok = result.returncode == 0 and lines[-1] == "OK" and ran is not None and int(ran.group(1)) > 0
    summary = lines[-1] if (ok or result.returncode != 0) else "exited with status 0 without unittest's OK line and a test count"
    return {"passed": ok, "summary": summary, "output": result.stderr[-2000:]}


def run_tests(test_path, project, scratch, discover=False):
    """v1's run_tests, with v2's verdict."""
    home = Path(scratch) / "home"
    home.mkdir(exist_ok=True)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home), "MANTLE_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
    args = [sys.executable, "-s", "-m", "unittest", "discover", "-s", str(test_path)] if discover else [sys.executable, "-s", str(test_path)]
    result = subprocess.run(args, cwd=Path(test_path if discover else Path(test_path).parent), env=env, capture_output=True, text=True, timeout=180)
    return verdict(result)


factory.run_tests = run_tests

if __name__ == "__main__":
    args = sys.argv[1:]
    environment = None
    if "--environment" in args:
        i = args.index("--environment")
        environment = args[i + 1]
        del args[i:i + 2]
    if len(args) != 3:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(factory.main(*args, environment_path=environment))
