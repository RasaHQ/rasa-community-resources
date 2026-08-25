#!/usr/bin/env python3
"""Smoke-check (and optionally train) one Rasa Pro community resource project.

Usage:
    python scripts/check_project.py examples/maestro-voice-agent
    python scripts/check_project.py examples/maestro-voice-agent --train
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rasa_projects import (  # noqa: E402
    REPO_ROOT,
    read_expected_version,
    uv_prerelease_args,
)


def _c(code: str) -> str:
    return code if sys.stdout.isatty() else ""


GREEN = _c("\033[92m")
YELLOW = _c("\033[93m")
RED = _c("\033[91m")
BLUE = _c("\033[94m")
RESET = _c("\033[0m")


def ok(msg: str) -> None:
    print(f"{GREEN}  ✓  {msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{YELLOW}  ⚠  {msg}{RESET}")


def fail(msg: str) -> None:
    print(f"{RED}  ✗  {msg}{RESET}")


def info(msg: str) -> None:
    print(f"{BLUE}  ℹ  {msg}{RESET}")


def _load_env_file(env_path: Path) -> int:
    """Fill gaps in os.environ from a dotenv file. Never overrides an export."""
    if not env_path.is_file():
        return 0
    loaded = 0
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


def _load_dotenv(project: Path) -> None:
    """Load the project's .env, then fall back to the repo-root .env.

    Precedence is exported vars > project .env > repo-root .env. The root file
    is what lets a maintainer keep one RASA_LICENSE / provider key set for the
    whole catalog instead of copying credentials into all seven projects.
    """
    _load_env_file(project / ".env")
    root_env = REPO_ROOT / ".env"
    if root_env.is_file() and root_env != (project / ".env"):
        count = _load_env_file(root_env)
        if count:
            info(f"loaded {count} var(s) from repo-root .env")


def _run(cmd: list[str], *, cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def _has_license() -> bool:
    value = os.environ.get("RASA_LICENSE", "").strip()
    return bool(value) and not value.startswith("your-") and value.count(".") == 2


def check_project(
    project: Path,
    expected: str,
    *,
    train: bool,
    skip_sync: bool,
    require_license: bool = False,
) -> int:
    rel = project.relative_to(REPO_ROOT).as_posix() if project.is_relative_to(REPO_ROOT) else str(project)
    print(f"\n{BLUE}═══ {rel} ═══{RESET}")

    uv = shutil.which("uv")
    if not uv:
        fail("uv not found on PATH")
        return 1

    if not (project / "pyproject.toml").is_file():
        fail(f"No pyproject.toml in {project}")
        return 1

    _load_dotenv(project)

    env = os.environ.copy()
    # Keep check-all readable; Rasa validation is otherwise very chatty at DEBUG.
    env.setdefault("LOG_LEVEL", "ERROR")
    env.setdefault("RASA_LOG_LEVEL", "ERROR")

    if not skip_sync:
        # Only allow prereleases when the pin itself is one; a stable pin should
        # not license every other dependency to resolve to a prerelease.
        sync_cmd = [uv, "sync", *uv_prerelease_args(expected), "--quiet"]
        info(" ".join(["uv", "sync", *uv_prerelease_args(expected)]))
        try:
            subprocess.run(
                sync_cmd,
                cwd=project,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            ok("dependencies synced")
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            fail("uv sync failed")
            if detail:
                print(detail, file=sys.stderr)
            return 1

    # Assert installed package version + Maestro import inside the project venv.
    version_probe = f"""
import importlib.metadata
import importlib.util
import sys
expected = {expected!r}
actual = importlib.metadata.version("rasa-pro")
if actual != expected:
    print(f"rasa-pro {{actual}} != expected {{expected}}", file=sys.stderr)
    sys.exit(2)
if importlib.util.find_spec("rasa.calm_v2") is None:
    print("rasa.calm_v2 is not importable", file=sys.stderr)
    sys.exit(3)
print(actual)
"""
    try:
        proc = subprocess.run(
            [uv, "run", "python", "-c", version_probe],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        ok(f"rasa-pro=={proc.stdout.strip()} (matches expected)")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "version check failed"
        fail(detail)
        return 1

    validate_probe = """
import logging
logging.disable(logging.WARNING)
from pathlib import Path
from rasa.calm_v2.validation import validate_project
validate_project(Path("."))
print("validate_project: ok")
"""
    try:
        info("validate_project")
        subprocess.run(
            [uv, "run", "python", "-c", validate_probe],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        ok("validate_project passed")
    except subprocess.CalledProcessError as exc:
        fail("validate_project failed")
        detail = (exc.stderr or exc.stdout or "").strip()
        if detail:
            print(detail, file=sys.stderr)
        return 1

    if train:
        if not _has_license():
            if require_license:
                fail(
                    "RASA_LICENSE missing or placeholder — cannot run rasa train. "
                    "Set it in the environment, the project .env, or the repo-root "
                    ".env (or drop --require-license to skip training)."
                )
                return 1
            # Best-effort by default, but say so loudly: a skipped train must not
            # be mistaken for a passing one.
            warn("RASA_LICENSE missing or placeholder — SKIPPING rasa train (not verified)")
            return 0
        info("rasa train")
        try:
            _run([uv, "run", "rasa", "train"], cwd=project)
            ok("rasa train passed")
        except subprocess.CalledProcessError:
            fail("rasa train failed")
            return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "project",
        help="Repo-relative or absolute path to a resource project",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Expected rasa-pro version (default: RASA_PRO_VERSION)",
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="Also run rasa train when RASA_LICENSE is available",
    )
    parser.add_argument(
        "--require-license",
        action="store_true",
        help="Fail instead of skipping when RASA_LICENSE is missing (CI)",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Skip uv sync (assume install-all already ran)",
    )
    args = parser.parse_args()

    expected = read_expected_version(args.version)
    project = Path(args.project)
    if not project.is_absolute():
        project = (REPO_ROOT / project).resolve()
    else:
        project = project.resolve()

    return check_project(
        project,
        expected,
        train=args.train,
        skip_sync=args.skip_sync,
        require_license=args.require_license,
    )


if __name__ == "__main__":
    raise SystemExit(main())
