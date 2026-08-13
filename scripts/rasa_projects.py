"""Shared helpers for discovering and inspecting Rasa Pro example projects."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "RASA_PRO_VERSION"
SCAN_ROOTS = ("examples", "tutorials")

RASA_PRO_DEP_RE = re.compile(
    r"""(?P<prefix>["']rasa-pro==)(?P<version>[^"']+)(?P<suffix>["'])"""
)
VERSION_TOKEN = r"\d+\.\d+\.\d+(?:\.dev\d+)?"
VERIFIED_WITH_RE = re.compile(
    rf"(Verified with:\s*rasa-pro\s+)(?P<version>{VERSION_TOKEN})",
    re.IGNORECASE,
)
NOTES_HEADING_RE = re.compile(
    rf"(#+\s*Notes for Rasa\s+)(?P<version>{VERSION_TOKEN})",
    re.IGNORECASE,
)
ASSESSED_ON_RE = re.compile(r"(Assessed on:\s*)(?P<date>\d{4}-\d{2}-\d{2})")
LOCK_RASA_PRO_VERSION_RE = re.compile(
    r'(?ms)^name = "rasa-pro"\nversion = "(?P<version>[^"]+)"',
)


@dataclass(frozen=True)
class Project:
    path: Path

    @property
    def rel(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()

    @property
    def pyproject(self) -> Path:
        return self.path / "pyproject.toml"

    @property
    def lockfile(self) -> Path:
        return self.path / "uv.lock"


def read_expected_version(override: str | None = None) -> str:
    if override:
        version = override.strip()
        if not version:
            raise ValueError("VERSION override is empty")
        return version
    if not VERSION_FILE.is_file():
        raise FileNotFoundError(f"Missing {VERSION_FILE}")
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version or version.startswith("#"):
        raise ValueError(f"{VERSION_FILE} does not contain a version")
    # Allow a trailing comment on the same line.
    version = version.split("#", 1)[0].strip()
    if not version:
        raise ValueError(f"{VERSION_FILE} does not contain a version")
    return version


def _declares_rasa_pro(pyproject: Path) -> bool:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    for dep in deps:
        if isinstance(dep, str) and dep.startswith("rasa-pro"):
            return True
    return False


def discover_projects() -> list[Project]:
    projects: list[Project] = []
    for root_name in SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for pyproject in sorted(root.rglob("pyproject.toml")):
            # Only top-level resources: examples/<name>/pyproject.toml
            # or tutorials/<name>/pyproject.toml (skip nested tutorial/snippets copies).
            rel_parts = pyproject.relative_to(root).parts
            if len(rel_parts) != 2:
                continue
            if _declares_rasa_pro(pyproject):
                projects.append(Project(pyproject.parent))
    return projects


def read_pyproject_pin(project: Project) -> str | None:
    text = project.pyproject.read_text(encoding="utf-8")
    match = RASA_PRO_DEP_RE.search(text)
    return match.group("version") if match else None


def read_lock_version(project: Project) -> str | None:
    if not project.lockfile.is_file():
        return None
    match = LOCK_RASA_PRO_VERSION_RE.search(project.lockfile.read_text(encoding="utf-8"))
    return match.group("version") if match else None


def read_readme_verified(project: Project) -> str | None:
    readme = project.path / "README.md"
    if not readme.is_file():
        return None
    match = VERIFIED_WITH_RE.search(readme.read_text(encoding="utf-8"))
    return match.group("version") if match else None


@dataclass
class Drift:
    project: Project
    expected: str
    pyproject: str | None
    lock: str | None
    readme: str | None

    @property
    def ok(self) -> bool:
        return (
            self.pyproject == self.expected
            and self.lock == self.expected
            and (self.readme is None or self.readme == self.expected)
        )

    def issues(self) -> list[str]:
        issues: list[str] = []
        if self.pyproject != self.expected:
            issues.append(f"pyproject={self.pyproject!r}")
        if self.lock != self.expected:
            issues.append(f"lock={self.lock!r}")
        if self.readme is not None and self.readme != self.expected:
            issues.append(f"readme={self.readme!r}")
        return issues


def project_drift(project: Project, expected: str) -> Drift:
    return Drift(
        project=project,
        expected=expected,
        pyproject=read_pyproject_pin(project),
        lock=read_lock_version(project),
        readme=read_readme_verified(project),
    )
