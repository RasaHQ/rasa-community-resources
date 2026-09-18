"""Where the demo data lives.

This is fiddlier than it looks, and getting it wrong fails in a way that gives
no hint at all — a `FileNotFoundError` on `wards.json` and an `OperationalError`
from SQLite, from a project where both files are plainly present.

The reason: `rasa train` packages `tools/` and `skills/*/tools.py` into the
model archive, and at run time the server extracts that archive to a temporary
directory and imports the tools from *there*. A tool that locates its data
relative to its own `__file__` therefore looks inside the temp directory, which
contains the code and none of the data.

So the working directory is the anchor — `rasa run` and `rasa inspect` are both
started from the project root. `CIVICO_PROJECT_ROOT` covers anything that is
not, and the module location is the last resort so the test suite and the
scripts still work when they are run from elsewhere.
"""

from __future__ import annotations

import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent

#: Present in a real project root and nowhere else.
_MARKER = Path("data") / "wards.json"


def _looks_like_root(candidate: Path) -> bool:
    return (candidate / _MARKER).is_file()


def project_root() -> Path:
    override = os.getenv("CIVICO_PROJECT_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if _looks_like_root(candidate):
            return candidate

    if _looks_like_root(_HERE.parent):
        return _HERE.parent

    raise FileNotFoundError(
        f"Cannot find the Civico project data. Looked for {_MARKER} under "
        f"{cwd} and its parents, and under {_HERE.parent}. Run from the "
        f"project root, or set CIVICO_PROJECT_ROOT."
    )


def data_dir() -> Path:
    return project_root() / "data"


def db_path() -> Path:
    override = os.getenv("CIVICO_DB_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return data_dir() / "civico.db"
