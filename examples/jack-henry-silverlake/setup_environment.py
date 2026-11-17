# SPDX-License-Identifier: MIT
"""Sync the existing locked environment without removing or replacing it."""
from pathlib import Path
import subprocess


def ensure(project, runner=None):
    runner = subprocess.run if runner is None else runner
    project = Path(project).resolve()
    env = project / ".venv"
    if env.is_symlink():
        raise ValueError("environment link")
    if env.exists():
        config = env / "pyvenv.cfg"
        if not (env / "bin/python").is_file() or not config.is_file():
            raise ValueError("incomplete environment")
        lines = dict(line.split(" = ", 1) for line in config.read_text().splitlines() if " = " in line)
        if not lines.get("version", lines.get("version_info", "")).startswith("3.12."):
            raise ValueError("different Python version")
    runner(["uv", "sync", "--locked", "--python", "3.12", "--project", str(project)], check=True)
    print("Locked SilverLake environment is ready. Repeating make setup reuses .venv; vendor inputs and transfer state are preserved.")


def main():
    try:
        ensure(Path(__file__).resolve().parent)
        return 0
    except ValueError:
        print("Setup stopped (ValueError). Existing .venv is incomplete, linked or uses a different Python version. Preserve this folder and open a fresh README-button Codespace; setup will not remove it.")
    except (OSError, subprocess.CalledProcessError) as error:
        kind = "CalledProcessError" if isinstance(error, subprocess.CalledProcessError) else "OSError"
        print("Setup stopped (" + kind + "). Check the installation output and network, then run make setup again. No vendor file or transfer journal was reset.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
