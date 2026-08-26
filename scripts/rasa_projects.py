"""Shared helpers for discovering and inspecting Rasa Pro example projects.

Stdlib only — these scripts run under a bare `python3` (see the root Makefile),
so they must not assume the projects' virtualenvs or third-party packages.
"""

from __future__ import annotations

import io
import json
import re
import tomllib
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "RASA_PRO_VERSION"
# Optional guard rail: a version prefix that `--latest` must stay within.
# This catalog runs on the Mantle / Skills engine (`rasa.calm_v2`), which
# ships only on the 3.19.0.devN line — "newest on PyPI" is a stable release
# that does not contain it at all. See docs/MIGRATING.md.
VERSION_LINE_FILE = REPO_ROOT / "RASA_PRO_VERSION_LINE"
# The engine module every resource in this catalog imports. `--check-latest`
# probes candidate releases for it instead of trusting the comment in
# RASA_PRO_VERSION_LINE, so the day it lands on a stable release the tooling
# says so on its own rather than waiting for someone to notice.
REQUIRED_ENGINE_MODULE = "rasa/calm_v2/"

# ------------------------------------------------------------------------------
# Where resources live, and what each root promises
# ------------------------------------------------------------------------------
# Two tiers. The difference is a maintenance promise, not a topic:
#
#   catalog   Maintained material. Every project pins RASA_PRO_VERSION, moves in
#             lockstep under `make migrate`, and is expected to stay green for
#             as long as it is checked in.
#
#   snapshot  Contributed material, frozen at the version its author verified.
#             `make migrate` does not rewrite it and the repo-wide version check
#             skips it, because nobody has undertaken to re-verify a past
#             cohort's project against every future release. It is still held to
#             internal consistency, metadata, secret hygiene, and a real lock.
#
# Freezing is a property of the root, so a contributor never has to remember a
# flag: putting a project under `community/` or `heroes/` *is* the declaration.
#
# `depth` is how many path parts separate the root from `pyproject.toml`. It is
# what stops a nested `tutorial/snippets/pyproject.toml` inside an example from
# being discovered as a resource in its own right.


@dataclass(frozen=True)
class Root:
    name: str
    depth: int
    snapshot: bool


CATALOG_ROOTS = (
    Root("examples", 2, snapshot=False),
    Root("tutorials", 2, snapshot=False),
    Root("patterns", 2, snapshot=False),
    # Contributed work is maintained too. An example pinned to a release the
    # catalog has moved off is one nobody clones — being current is most of
    # what makes it worth checking in. The contributor is not signed up for
    # that; `make migrate` is, and the maintainer who runs it re-stamps
    # `Assessed by`. What a contributor keeps is authorship, permanently.
    Root("community", 2, snapshot=False),    # community/<resource>/
)
SNAPSHOT_ROOTS = (
    # Wave projects are the exception, and deliberately so: a cohort finishes,
    # its participants move on, and the work is a dated record of what that
    # cohort built rather than something anyone undertakes to keep running.
    Root("heroes", 4, snapshot=True),        # heroes/<wave>/projects/<project>/
)
ROOTS = CATALOG_ROOTS + SNAPSHOT_ROOTS

SCOPES = {
    "catalog": CATALOG_ROOTS,
    "snapshots": SNAPSHOT_ROOTS,
    "all": ROOTS,
}

# Names only, for the many callers that just need "is this path frozen?".
SCAN_ROOTS = tuple(root.name for root in CATALOG_ROOTS)
SNAPSHOT_ROOT_NAMES = tuple(root.name for root in SNAPSHOT_ROOTS)

# Contributed resources, flat and author-prefixed: `community/<handle>-<slug>/`.
COMMUNITY_ROOT = "community"

# Rasa Heroes cohorts. `heroes/<wave>/` holds the wave charter and its projects.
HEROES_ROOT = "heroes"
WAVE_DIR = "projects"
# wave-01-voice, wave-12-observability — zero-padded so the directory listing
# and the chronological order are the same thing.
WAVE_SLUG_RE = re.compile(r"^wave-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")

PACKAGE = "rasa-pro"
PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"

# Docs at the repo root that carry version strings and must stay current.
REPO_DOCS = (
    "README.md",
    "CONTRIBUTING.md",
    "Makefile",
    "docs/MIGRATING.md",
    "docs/RESOURCE_TEMPLATE.md",
)
# Per-project docs rewritten during a migration.
PROJECT_DOCS = ("README.md", "AGENTS.md")

# ------------------------------------------------------------------------------
# Version tokens
# ------------------------------------------------------------------------------
# PEP 440-ish: 3.19.1, 3.19.0.dev5, 3.19.0rc1, 3.19.0b2, 3.19.1.post1.
VERSION_TOKEN = r"\d+\.\d+(?:\.\d+)?(?:(?:a|b|rc)\d+)?(?:\.(?:dev|post)\d+)?"
_VERSION_FULLMATCH = re.compile(rf"^{VERSION_TOKEN}$")
_PRERELEASE_RE = re.compile(r"(?:(?:a|b|rc)\d+|\.dev\d+)$")

RASA_PRO_DEP_RE = re.compile(
    r"""(?P<prefix>["']rasa-pro==)(?P<version>[^"']+)(?P<suffix>["'])"""
)
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

# Prose forms. `[ \t]` rather than `\s` so a match can never span a newline and
# glue an unrelated version from the following line onto a trailing "rasa-pro".
PROSE_EQ_RE = re.compile(rf"(rasa-pro==)(?P<version>{VERSION_TOKEN})")
PROSE_SPACE_RE = re.compile(rf"(rasa-pro[ \t]+)(?P<version>{VERSION_TOKEN})")
# Documented invocations that embed the target version, e.g.
#   make migrate VERSION=3.19.1
#   echo '3.19.1' > RASA_PRO_VERSION
MAKE_VERSION_RE = re.compile(rf"(VERSION=)(?P<version>{VERSION_TOKEN})")
ECHO_PIN_RE = re.compile(
    rf"""(echo\s+["']?)(?P<version>{VERSION_TOKEN})(["']?\s*>\s*RASA_PRO_VERSION)"""
)

# `uv sync|lock --prerelease=allow` as written in project Makefiles and docs.
# The flag is toggled to track the pin, so published install instructions never
# tell a reader to allow prereleases for a stable release (or omit it for a dev
# build, where resolution would simply fail).
UV_PRERELEASE_FLAG_RE = re.compile(
    r"(?P<cmd>(?:\$\(UV\)|uv)[ \t]+(?:sync|lock))(?P<flag>[ \t]+--prerelease=allow)?"
)

# `[tool.uv]` prerelease switch, managed so it tracks the target version.
UV_PRERELEASE_RE = re.compile(
    r"""(?m)^(?P<indent>[ \t]*)prerelease[ \t]*=[ \t]*["'](?P<mode>[^"']+)["'][ \t]*\r?\n"""
)
TOOL_UV_TABLE_RE = re.compile(r"(?m)^\[tool\.uv\][ \t]*\r?\n")


def is_valid_version(version: str) -> bool:
    return bool(_VERSION_FULLMATCH.match(version.strip()))


def is_prerelease(version: str) -> bool:
    """True for dev/alpha/beta/rc pins, which need `uv --prerelease=allow`."""
    return bool(_PRERELEASE_RE.search(version.strip()))


def uv_prerelease_args(version: str) -> list[str]:
    """uv flags appropriate for `version`.

    Only opt into prereleases when the pin itself is one. Passing
    `--prerelease=allow` for a stable pin needlessly lets *every other*
    dependency resolve to a prerelease.
    """
    return ["--prerelease=allow"] if is_prerelease(version) else []


def _version_sort_key(version: str) -> tuple:
    """Order releases without depending on `packaging`.

    Release segment first, then a stage rank so that dev < a < b < rc < final,
    matching PEP 440 precedence closely enough to pick a maximum.
    """
    match = re.match(
        r"^(?P<rel>\d+(?:\.\d+)*)"
        r"(?:(?P<stage>a|b|rc)(?P<stage_n>\d+))?"
        r"(?:\.dev(?P<dev>\d+))?"
        r"(?:\.post(?P<post>\d+))?$",
        version,
    )
    if not match:
        return ((), 0, 0, 0, 0)
    release = tuple(int(p) for p in match.group("rel").split("."))
    stage_rank = {"a": 1, "b": 2, "rc": 3}.get(match.group("stage") or "", 4)
    stage_n = int(match.group("stage_n") or 0)
    # A `.dev` marker sorts below every non-dev form of the same release.
    dev = match.group("dev")
    dev_rank = (0, int(dev)) if dev is not None else (1, 0)
    post = int(match.group("post") or 0)
    if dev is not None and match.group("stage") is None:
        stage_rank = 0
    return (release, stage_rank, stage_n, dev_rank, post)


# ------------------------------------------------------------------------------
# Package index
# ------------------------------------------------------------------------------


class IndexUnavailable(RuntimeError):
    """Raised when the package index cannot be reached or parsed."""


def fetch_release_versions(package: str = PACKAGE, *, timeout: float = 30.0) -> list[str]:
    """All non-yanked versions of `package` on PyPI, newest last."""
    url = PYPI_JSON_URL.format(package=package)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise IndexUnavailable(f"could not query {url}: {exc}") from exc

    releases = payload.get("releases", {})
    usable = [
        version
        for version, files in releases.items()
        if files and not all(f.get("yanked") for f in files)
    ]
    return sorted(usable, key=_version_sort_key)


def read_version_line() -> str | None:
    """The version prefix `--latest` must stay within, if one is configured."""
    if not VERSION_LINE_FILE.is_file():
        return None
    for raw in VERSION_LINE_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            return line
    return None


def latest_version(
    package: str = PACKAGE,
    *,
    allow_prerelease: bool = False,
    prefix: str | None = None,
    timeout: float = 30.0,
) -> str:
    """Newest version on the index.

    `prefix` restricts the search to one release line (e.g. `3.19.0.dev`), which
    is what keeps `--latest` from jumping to a newer release that does not carry
    the engine this catalog depends on. A prefixed search implies prereleases
    are acceptable — that is the whole point of pinning to a dev line.
    """
    versions = fetch_release_versions(package, timeout=timeout)
    if prefix:
        versions = [v for v in versions if v.startswith(prefix)]
        if not versions:
            raise IndexUnavailable(
                f"no {package} releases match the configured line {prefix!r}"
            )
    elif not allow_prerelease:
        stable = [v for v in versions if not is_prerelease(v)]
        versions = stable or versions
    if not versions:
        raise IndexUnavailable(f"no releases found for {package}")
    return versions[-1]


def version_exists(
    version: str, package: str = PACKAGE, *, timeout: float = 30.0
) -> bool:
    return version in set(fetch_release_versions(package, timeout=timeout))


# A wheel is a zip: its central directory sits at the end, so the file list can
# be read from the tail alone. rasa-pro wheels are ~100MB; this keeps the
# capability probe to a few MB per release checked.
_ZIP_TAIL_BYTES = 4_000_000


def _smallest_wheel(
    version: str, package: str = PACKAGE, *, timeout: float = 30.0
) -> dict:
    url = f"https://pypi.org/pypi/{package}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise IndexUnavailable(f"could not query {url}: {exc}") from exc

    wheels = [
        u
        for u in payload.get("urls", [])
        if u.get("filename", "").endswith(".whl") and not u.get("yanked")
    ]
    if not wheels:
        raise IndexUnavailable(f"{package} {version} publishes no wheel to inspect")
    return min(wheels, key=lambda u: u.get("size") or 0)


def wheel_contents(
    version: str, package: str = PACKAGE, *, timeout: float = 60.0
) -> list[str]:
    """File names inside the wheel for `version`, read via a ranged request."""
    meta = _smallest_wheel(version, package, timeout=timeout)
    size = int(meta.get("size") or 0)
    start = max(0, size - _ZIP_TAIL_BYTES) if size else 0

    request = urllib.request.Request(meta["url"])
    if start:
        request.add_header("Range", f"bytes={start}-{size - 1}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            partial = response.status == 206
            data = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise IndexUnavailable(f"could not fetch {meta['filename']}: {exc}") from exc

    # Pad only when the server honoured the range, so central-directory offsets
    # line up. A server that ignores Range hands back the whole file instead.
    blob = (b"\0" * start + data) if (partial and start) else data
    try:
        return zipfile.ZipFile(io.BytesIO(blob)).namelist()
    except (zipfile.BadZipFile, EOFError) as exc:
        raise IndexUnavailable(
            f"could not read the archive index of {meta['filename']}: {exc}"
        ) from exc


def release_carries_engine(
    version: str,
    *,
    module: str = REQUIRED_ENGINE_MODULE,
    package: str = PACKAGE,
    timeout: float = 60.0,
) -> bool:
    """Whether `version` actually ships the engine this catalog imports."""
    prefix = module if module.endswith("/") else f"{module}/"
    return any(
        name.startswith(prefix)
        for name in wheel_contents(version, package, timeout=timeout)
    )


# ------------------------------------------------------------------------------
# Project discovery
# ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Project:
    path: Path
    # Frozen at the version its author verified; excluded from migration and
    # from the repo-wide pin assertion. See the root table above.
    snapshot: bool = False

    @property
    def rel(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()

    @property
    def pyproject(self) -> Path:
        return self.path / "pyproject.toml"

    @property
    def lockfile(self) -> Path:
        return self.path / "uv.lock"

    def docs(self) -> list[Path]:
        return [self.path / name for name in PROJECT_DOCS if (self.path / name).is_file()]


def read_expected_version(override: str | None = None) -> str:
    if override:
        version = override.strip()
        if not version:
            raise ValueError("VERSION override is empty")
        return version
    if not VERSION_FILE.is_file():
        raise FileNotFoundError(f"Missing {VERSION_FILE}")
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    # Allow a trailing comment on the same line.
    version = version.split("#", 1)[0].strip()
    if not version:
        raise ValueError(f"{VERSION_FILE} does not contain a version")
    return version


def write_version_file(version: str) -> None:
    VERSION_FILE.write_text(version + "\n", encoding="utf-8")


def _declares_rasa_pro(pyproject: Path) -> bool:
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return False
    deps = data.get("project", {}).get("dependencies", [])
    return any(isinstance(dep, str) and dep.startswith("rasa-pro") for dep in deps)


def discover_projects(scope: str = "catalog") -> list[Project]:
    """Rasa Pro resources under the roots selected by `scope`.

    The default is the maintained catalog, deliberately: every caller that
    migrates pins or asserts RASA_PRO_VERSION means that tier and only that
    tier. Frozen snapshots have to be asked for by name, so no future caller
    picks them up by accident and starts rewriting a past cohort's work.
    """
    try:
        roots = SCOPES[scope]
    except KeyError:
        raise ValueError(
            f"unknown scope {scope!r}; expected one of {', '.join(SCOPES)}"
        ) from None

    projects: list[Project] = []
    for root in roots:
        base = REPO_ROOT / root.name
        if not base.is_dir():
            continue
        for pyproject in sorted(base.rglob("pyproject.toml")):
            # Depth pins the resource level for this root, which is what skips
            # nested copies such as an example's own tutorial/snippets tree.
            if len(pyproject.relative_to(base).parts) != root.depth:
                continue
            if _declares_rasa_pro(pyproject):
                projects.append(Project(pyproject.parent, snapshot=root.snapshot))
    return projects


def is_snapshot_path(rel_path: str) -> bool:
    """True for a repo-relative path inside a frozen-snapshot root."""
    return rel_path.split("/", 1)[0] in SNAPSHOT_ROOT_NAMES


def discover_waves() -> list[Path]:
    """Every `heroes/<wave>/` directory, in cohort order."""
    base = REPO_ROOT / HEROES_ROOT
    if not base.is_dir():
        return []
    return sorted(
        path
        for path in base.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def read_pyproject_pin(project: Project) -> str | None:
    match = RASA_PRO_DEP_RE.search(project.pyproject.read_text(encoding="utf-8"))
    return match.group("version") if match else None


def read_lock_version(project: Project) -> str | None:
    if not project.lockfile.is_file():
        return None
    match = LOCK_RASA_PRO_VERSION_RE.search(project.lockfile.read_text(encoding="utf-8"))
    return match.group("version") if match else None


def read_uv_prerelease_setting(project: Project) -> str | None:
    """The `[tool.uv] prerelease` mode declared by the project, if any."""
    try:
        data = tomllib.loads(project.pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return None
    value = data.get("tool", {}).get("uv", {}).get("prerelease")
    return value if isinstance(value, str) else None


def read_required_secrets(project: Project) -> list[str]:
    """Provider keys this resource needs before `rasa train` can run.

    Declared as `[tool.rasa-catalog] required-secrets` in the project's
    pyproject. Most resources need nothing here: RASA_LICENSE, OPENAI_API_KEY
    and DEEPGRAM_API_KEY are the catalog defaults and CI carries all three. A
    resource built on a different provider does not, and without a declaration
    its train step fails on a missing environment variable and reads as a
    broken resource rather than an unconfigured runner.
    """
    try:
        data = tomllib.loads(project.pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return []
    declared = data.get("tool", {}).get("rasa-catalog", {}).get("required-secrets", [])
    return [item for item in declared if isinstance(item, str)]


def read_readme_verified(project: Project) -> str | None:
    readme = project.path / "README.md"
    if not readme.is_file():
        return None
    match = VERIFIED_WITH_RE.search(readme.read_text(encoding="utf-8"))
    return match.group("version") if match else None


def stale_doc_versions(project: Project, expected: str) -> dict[str, list[str]]:
    """Version strings still pointing somewhere other than `expected`.

    Catches the drift `read_readme_verified` misses: a header bumped but a
    `rasa-pro==…` left behind further down, or a stale pin in AGENTS.md.
    """
    stale: dict[str, list[str]] = {}
    for doc in project.docs():
        text = doc.read_text(encoding="utf-8")
        found = {
            m.group("version")
            for pattern in (PROSE_EQ_RE, PROSE_SPACE_RE, VERIFIED_WITH_RE, NOTES_HEADING_RE)
            for m in pattern.finditer(text)
        }
        wrong = sorted(v for v in found if v != expected)
        if wrong:
            stale[doc.name] = wrong
    return stale


@dataclass
class Drift:
    project: Project
    expected: str
    pyproject: str | None
    lock: str | None
    readme: str | None
    docs: dict[str, list[str]] = field(default_factory=dict)
    prerelease_setting: str | None = None

    @property
    def prerelease_mismatch(self) -> bool:
        """`[tool.uv] prerelease = "allow"` left behind on a stable pin."""
        return self.prerelease_setting == "allow" and not is_prerelease(self.expected)

    @property
    def ok(self) -> bool:
        return (
            self.pyproject == self.expected
            and self.lock == self.expected
            and (self.readme is None or self.readme == self.expected)
            and not self.docs
            and not self.prerelease_mismatch
        )

    def issues(self) -> list[str]:
        issues: list[str] = []
        if self.pyproject != self.expected:
            issues.append(f"pyproject={self.pyproject!r}")
        if self.lock != self.expected:
            issues.append(f"lock={self.lock!r}")
        if self.readme is not None and self.readme != self.expected:
            issues.append(f"readme={self.readme!r}")
        for name, versions in sorted(self.docs.items()):
            issues.append(f"{name} mentions {', '.join(versions)}")
        if self.prerelease_mismatch:
            issues.append('prerelease="allow" on a stable pin')
        return issues


def project_drift(project: Project, expected: str) -> Drift:
    return Drift(
        project=project,
        expected=expected,
        pyproject=read_pyproject_pin(project),
        lock=read_lock_version(project),
        readme=read_readme_verified(project),
        docs=stale_doc_versions(project, expected),
        prerelease_setting=read_uv_prerelease_setting(project),
    )
