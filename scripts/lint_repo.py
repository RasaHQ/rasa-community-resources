#!/usr/bin/env python3
"""Static correctness checks for the whole catalog.

Fast and offline: no network, no virtualenvs, no `uv`. This is the layer that
answers "is the repository internally consistent?" — `check_project.py` answers
the separate question "does it actually install and validate?".

Every check here encodes a failure this repository has actually hit.

Usage:
    python scripts/lint_repo.py
    python scripts/lint_repo.py --json
    python scripts/lint_repo.py --check skill-prose --check lock-sync
    python scripts/lint_repo.py --list
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rasa_projects import (  # noqa: E402
    COMMUNITY_ROOT,
    HEROES_ROOT,
    NOTES_HEADING_RE,
    PROSE_EQ_RE,
    PROSE_SPACE_RE,
    REPO_ROOT,
    VERIFIED_WITH_RE,
    VERSION_LINE_FILE,
    WAVE_DIR,
    WAVE_SLUG_RE,
    Project,
    discover_projects,
    discover_waves,
    is_prerelease,
    is_snapshot_path,
    read_expected_version,
    read_lock_version,
    read_pyproject_pin,
    read_readme_verified,
    read_required_secrets,
    read_uv_prerelease_setting,
    read_version_line,
)

# Packages whose *entire* release history is pre-release-numbered, so a
# prerelease pin in a lock is normal rather than a leftover.
PRERELEASE_DEP_ALLOWLIST = {"opentelemetry-semantic-conventions"}

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


@dataclass
class Finding:
    check: str
    path: str
    line: int | None
    message: str
    severity: str = SEVERITY_ERROR

    def location(self) -> str:
        return f"{self.path}:{self.line}" if self.line else self.path


# ------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _tracked_files(*globs: str) -> list[Path]:
    """Only lint what git actually tracks — never .venv, models, or caches."""
    cmd = ["git", "-C", str(REPO_ROOT), "ls-files", "-z", *globs]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [REPO_ROOT / p for p in out.split("\0") if p]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _numbered(text: str):
    return enumerate(text.splitlines(), start=1)


# ------------------------------------------------------------------------------
# checks
# ------------------------------------------------------------------------------


def check_version_consistency(expected: str) -> list[Finding]:
    """Every rasa-pro version string in committed prose matches the pin."""
    findings: list[Finding] = []
    patterns = (PROSE_EQ_RE, PROSE_SPACE_RE, VERIFIED_WITH_RE, NOTES_HEADING_RE)
    targets = _tracked_files("*.md", "*.toml", "Makefile", "*/Makefile", "**/Makefile")
    for path in targets:
        if path.name == "uv.lock":
            continue
        # Frozen snapshots record the version they were verified against, which
        # is deliberately not the catalog pin. Holding them to it would either
        # rewrite a contributor's verified claim into a lie, or fail the build
        # for every past cohort on every bump. Their own internal consistency
        # is checked by `snapshot-pin` instead.
        if is_snapshot_path(_rel(path)):
            continue
        for lineno, line in _numbered(_read(path)):
            for pattern in patterns:
                for match in pattern.finditer(line):
                    found = match.group("version")
                    if found != expected:
                        findings.append(
                            Finding(
                                "version-consistency",
                                _rel(path),
                                lineno,
                                f"mentions rasa-pro {found}, expected {expected}",
                            )
                        )
    return findings


def check_version_line(expected: str) -> list[Finding]:
    """The pin stays on the release line this catalog is known to work on."""
    prefix = read_version_line()
    if not prefix:
        return []
    if not expected.startswith(prefix):
        return [
            Finding(
                "version-line",
                _rel(VERSION_LINE_FILE),
                None,
                f"RASA_PRO_VERSION is {expected}, which is not on the required "
                f"line {prefix!r}. The Maestro engine (rasa.calm_v2) ships only "
                f"on that line; widen or remove this file if that has changed.",
            )
        ]
    return []


def check_lock_sync(projects: list[Project], expected: str) -> list[Finding]:
    """pyproject pin and uv.lock both resolve to the pinned version."""
    findings: list[Finding] = []
    for project in projects:
        pin = read_pyproject_pin(project)
        if pin != expected:
            findings.append(
                Finding(
                    "lock-sync",
                    _rel(project.pyproject),
                    None,
                    f"pins rasa-pro=={pin}, expected {expected}",
                )
            )
        if not project.lockfile.is_file():
            findings.append(
                Finding("lock-sync", _rel(project.path), None, "missing uv.lock")
            )
            continue
        locked = read_lock_version(project)
        if locked != expected:
            findings.append(
                Finding(
                    "lock-sync",
                    _rel(project.lockfile),
                    None,
                    f"resolved rasa-pro=={locked}, expected {expected} "
                    f"(run: make migrate)",
                )
            )
    return findings


def check_prerelease_consistency(projects: list[Project], expected: str) -> list[Finding]:
    """uv prerelease opt-in matches whether the pin is actually a prerelease."""
    findings: list[Finding] = []
    want = is_prerelease(expected)

    for project in projects:
        setting = read_uv_prerelease_setting(project)
        if want and setting != "allow":
            findings.append(
                Finding(
                    "prerelease-consistency",
                    _rel(project.pyproject),
                    None,
                    f'pin {expected} is a prerelease but [tool.uv] prerelease is '
                    f"{setting!r}; resolution will fail",
                )
            )
        elif not want and setting == "allow":
            findings.append(
                Finding(
                    "prerelease-consistency",
                    _rel(project.pyproject),
                    None,
                    f'pin {expected} is stable but [tool.uv] prerelease = "allow" '
                    f"remains; that lets every other dependency resolve to a "
                    f"prerelease too",
                )
            )

    # The same switch as written into per-project Makefiles and install docs.
    flag_re = re.compile(r"(?:\$\(UV\)|uv)[ \t]+(?:sync|lock)(?P<flag>[ \t]+--prerelease=allow)?")
    for project in projects:
        for name in ("Makefile", "README.md", "AGENTS.md"):
            path = project.path / name
            if not path.is_file():
                continue
            for lineno, line in _numbered(_read(path)):
                for match in flag_re.finditer(line):
                    has = bool(match.group("flag"))
                    if has != want:
                        verb = "is missing" if want else "still carries"
                        findings.append(
                            Finding(
                                "prerelease-consistency",
                                _rel(path),
                                lineno,
                                f"install command {verb} --prerelease=allow for "
                                f"pin {expected} (run: make migrate)",
                            )
                        )
    return findings


def check_lock_prereleases(expected: str) -> list[Finding]:
    """Stable pins should not carry prerelease dependencies left over from a bump.

    A plain `uv lock` keeps any existing pin that still satisfies constraints, so
    prereleases locked under a previous `--prerelease=allow` survive the move to
    a stable pin; `uv lock --upgrade` is what clears them.

    Only meaningful for a stable pin. When the pin is itself a prerelease the
    allowance is deliberately on, and prerelease dependencies (rasa-sdk tracking
    the rasa-pro dev line, for instance) are the correct resolution.
    """
    if is_prerelease(expected):
        return []
    findings: list[Finding] = []
    package_re = re.compile(r'(?ms)^name = "(?P<name>[^"]+)"\nversion = "(?P<version>[^"]+)"')
    for lock in _tracked_files("*/uv.lock", "**/uv.lock"):
        # A frozen lock is a record of what the author installed, not something
        # `make migrate ARGS=--upgrade` is ever going to be run against.
        if is_snapshot_path(_rel(lock)):
            continue
        for match in package_re.finditer(_read(lock)):
            name, version = match.group("name"), match.group("version")
            if name in PRERELEASE_DEP_ALLOWLIST or name == "rasa-pro":
                continue
            if is_prerelease(version):
                findings.append(
                    Finding(
                        "lock-prereleases",
                        _rel(lock),
                        None,
                        f"{name}=={version} is a prerelease "
                        f"(run: make migrate ARGS=--upgrade)",
                        SEVERITY_WARNING,
                    )
                )
    return findings


# --- skill authoring rules ----------------------------------------------------

SESSION_REF_RE = re.compile(r"(?<![\w.])session\.([\w-]+)\.([\w-]+)")
MEMORY_TOKEN_RE = re.compile(r"@memory(?:\.[\w-]+)*")
def _prose_lines(text: str):
    """Yield (lineno, line) for text an LLM will read as instruction prose.

    A skill.md is three different languages stacked:

      * YAML frontmatter                      -> structured, never prose
      * markdown body                         -> prose, except top-level `if:`
      * `:::block ... :::` regions            -> YAML; only the bodies of
                                                 `instructions:` scalars are prose

    Modelling the block regions as YAML is what keeps `complete_when: >`
    continuation lines and `parameters:` bindings from being mistaken for prose,
    while still catching an `if:` nested inside an `instructions:` scalar — which
    the engine does treat as prose.
    """
    lines = text.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":  # skip YAML frontmatter
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                i = j + 1
                break

    in_block = False
    instr_indent: int | None = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        if instr_indent is not None:
            # Inside an instructions scalar: prose until indentation unwinds.
            if stripped and indent <= instr_indent:
                instr_indent = None
            else:
                yield i + 1, line
                i += 1
                continue

        if stripped.startswith(":::"):
            in_block = stripped != ":::"
            i += 1
            continue

        if re.match(r"^\s*instructions:\s*[|>]", line):
            instr_indent = indent
            i += 1
            continue

        if in_block:
            # Everything else inside a block region is evaluated YAML.
            i += 1
            continue

        # Markdown body: `if:` at the top level is a real condition.
        if stripped.startswith("if:") and indent == 0:
            i += 1
            continue

        yield i + 1, line
        i += 1


def check_skill_prose() -> list[Finding]:
    """Skill instructions must not contain raw `session.*` or partial @memory."""
    findings: list[Finding] = []
    for skill in _tracked_files("**/skill.md"):
        text = _read(skill)
        for lineno, line in _prose_lines(text):
            for match in SESSION_REF_RE.finditer(line):
                ref = f"session.{match.group(1)}.{match.group(2)}"
                findings.append(
                    Finding(
                        "skill-prose",
                        _rel(skill),
                        lineno,
                        f"{ref} appears in instruction prose; it is not "
                        f"substituted there. Use @memory.{match.group(1)}."
                        f"{match.group(2)} or move it into a top-level 'if:'.",
                    )
                )
            for match in MEMORY_TOKEN_RE.finditer(line):
                token = match.group(0)
                if len(token.split(".")) != 3:
                    findings.append(
                        Finding(
                            "skill-prose",
                            _rel(skill),
                            lineno,
                            f"{token!r} is not a substitutable token; live values "
                            f"require @memory.<namespace>.<entry>",
                        )
                    )
    return findings


def check_nested_if() -> list[Finding]:
    """`if:` only works at the top level of a skill body, never nested."""
    findings: list[Finding] = []
    for skill in _tracked_files("**/skill.md"):
        for lineno, line in _numbered(_read(skill)):
            if re.match(r"^[ \t]+if:\s*\S", line):
                findings.append(
                    Finding(
                        "nested-if",
                        _rel(skill),
                        lineno,
                        "indented 'if:' is not parsed as a condition; it stays "
                        "instruction prose. Move the branch to the top level of "
                        "the skill body, or express it in natural language.",
                    )
                )
    return findings


# --- repository hygiene -------------------------------------------------------

METADATA_KEYS = ("Author:", "Assessed on:", "Assessed by:", "Verified with:")
# `community/` is flat on purpose, so the resource states in metadata which
# category folder it would otherwise have lived in.
COMMUNITY_METADATA_KEYS = METADATA_KEYS + ("Kind:",)
# A wave project is a cohort deliverable, so it also records which cohort. That
# keeps it self-describing if it is ever moved, archived, or linked from outside.
HEROES_METADATA_KEYS = METADATA_KEYS + ("Wave:",)
ASSESSED_ON_RE = re.compile(r"Assessed on:\s*(\d{4}-\d{2}-\d{2})")


def check_resource_metadata(projects: list[Project]) -> list[Finding]:
    """Each runnable resource states who verified it, when, and against what."""
    findings: list[Finding] = []
    today = date.today()
    for project in projects:
        readme = project.path / "README.md"
        if not readme.is_file():
            findings.append(
                Finding("resource-metadata", _rel(project.path), None, "missing README.md")
            )
            continue
        text = _read(readme)
        head = "\n".join(text.splitlines()[:40])
        # _rel rather than project.rel: this runs against synthetic Projects in
        # the unit tests, whose paths are not under REPO_ROOT.
        rel = _rel(project.path)
        keys = METADATA_KEYS
        if rel.startswith(f"{HEROES_ROOT}/"):
            keys = HEROES_METADATA_KEYS
        elif rel.startswith(f"{COMMUNITY_ROOT}/"):
            keys = COMMUNITY_METADATA_KEYS
        for key in keys:
            if key not in head:
                findings.append(
                    Finding(
                        "resource-metadata",
                        _rel(readme),
                        None,
                        f"metadata block is missing {key!r}",
                    )
                )
        match = ASSESSED_ON_RE.search(head)
        if match:
            try:
                assessed = date.fromisoformat(match.group(1))
            except ValueError:
                findings.append(
                    Finding(
                        "resource-metadata", _rel(readme), None,
                        f"'Assessed on: {match.group(1)}' is not a valid date",
                    )
                )
            else:
                # `Assessed on` is a bare date with no timezone, so "today"
                # depends on where the check runs. An author west-to-east of a
                # CI runner legitimately stamps a date the runner still calls
                # tomorrow — that is calendar skew, not a bad value. One day of
                # slack absorbs every real offset (max ±14h) while still
                # catching a genuinely wrong date.
                if assessed > today + timedelta(days=1):
                    findings.append(
                        Finding(
                            "resource-metadata", _rel(readme), None,
                            f"'Assessed on: {assessed}' is in the future "
                            f"(today is {today}; one day of timezone slack allowed)",
                        )
                    )
    return findings


SECRET_PATTERNS = (
    ("OpenAI key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("JWT / licence", re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.")),
)


def check_secret_hygiene() -> list[Finding]:
    """No credentials committed, and no .env tracked."""
    findings: list[Finding] = []
    for path in _tracked_files(".env", "**/.env"):
        findings.append(
            Finding("secret-hygiene", _rel(path), None, ".env is tracked by git")
        )
    for path in _tracked_files("*.md", "*.toml", "*.yml", "*.py", "*.example", "Makefile"):
        if path.name == "uv.lock":
            continue
        for lineno, line in _numbered(_read(path)):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            "secret-hygiene",
                            _rel(path),
                            lineno,
                            f"looks like a committed {label}",
                        )
                    )
    return findings


USES_RE = re.compile(r"^\s*-?\s*uses:\s*(?P<ref>\S+)")
SHA_PINNED_RE = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def check_workflow_pins() -> list[Finding]:
    """Every GitHub Action must be pinned to a full-length commit SHA.

    RasaHQ enforces this org-wide, so an unpinned `uses:` fails the run before
    a single step executes. Catching it here turns a red CI run into a local
    lint finding. It is also the correct supply-chain posture: a mutable tag
    like `@v4` can be repointed at arbitrary code after review.
    """
    findings: list[Finding] = []
    for workflow in _tracked_files(".github/workflows/*.yml", ".github/workflows/*.yaml"):
        for lineno, line in _numbered(_read(workflow)):
            match = USES_RE.match(line)
            if not match:
                continue
            ref = match.group("ref").strip("'\"")
            # Local (./path) and container (docker://) refs are not tag-pinned.
            if ref.startswith((".", "docker://")):
                continue
            if not SHA_PINNED_RE.match(ref):
                findings.append(
                    Finding(
                        "workflow-pins",
                        _rel(workflow),
                        lineno,
                        f"{ref!r} is not pinned to a full 40-character commit SHA; "
                        f"org policy rejects the run. Resolve with: "
                        f"gh api repos/<owner>/<repo>/git/ref/tags/<tag>",
                    )
                )
    return findings


# Keys `agent.yml` carries at the TOP level, as siblings of `agent:`.
# `rasa.calm_v2.config.agent_spec._agent_spec_payload` reads them from the root
# mapping, and `AgentSpec` is declared `extra="ignore"` — so nesting one inside
# `agent:` parses without error, is discarded, and nothing ever says so.
TOP_LEVEL_AGENT_KEYS = (
    "name",
    "description",
    "rules",
    "prompts",
    "conversation",
    "references",
    "before_end",
)


def check_agent_config_keys() -> list[Finding]:
    """Prompt-tuning keys must sit beside `agent:`, never inside it.

    Regression, and the most expensive kind: silent. Every resource in this
    catalog nested `rules:` under `agent:`, and most nested `references:` too.
    39 rules were declared across the catalog and the engine applied none of
    them — no warning at train time, no error at load, just an agent quietly
    running without its guardrails.

    Found independently by Samrudha Kelkar (#1) and Daksh Varshneya (#2).
    """
    findings: list[Finding] = []
    seen: set[Path] = set()
    for path in _tracked_files("agent.yml", "*/agent.yml", "**/agent.yml"):
        if path in seen:
            continue
        seen.add(path)
        lines = _read(path).splitlines()
        try:
            start = next(i for i, l in enumerate(lines) if l.rstrip() == "agent:")
        except StopIteration:
            continue

        # Derive the block's own indent rather than assuming two spaces, so a
        # four-space file cannot slip past the check that exists for it.
        child_indent = None
        for i in range(start + 1, len(lines)):
            line = lines[i]
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if indent == 0:
                break
            child_indent = indent
            break
        if child_indent is None:
            continue

        for i in range(start + 1, len(lines)):
            line = lines[i]
            if line.strip() and not line[0].isspace():
                break  # a column-0 key ends the agent block
            if ":" not in line:
                continue
            if len(line) - len(line.lstrip()) != child_indent:
                continue
            key = line.strip().split(":", 1)[0]
            if key in TOP_LEVEL_AGENT_KEYS:
                findings.append(
                    Finding(
                        "agent-config-keys",
                        _rel(path),
                        i + 1,
                        f"{key!r} is nested inside 'agent:', where the engine "
                        f"parses it and then discards it. Move it to the top "
                        f"level of agent.yml, as a sibling of 'agent:'.",
                    )
                )
    return findings


def check_env_examples(projects: list[Project]) -> list[Finding]:
    """Every resource ships a .env.example that names the keys it actually needs."""
    findings: list[Finding] = []
    for project in projects:
        example = project.path / ".env.example"
        if not example.is_file():
            findings.append(
                Finding(
                    "env-example",
                    _rel(project.path),
                    None,
                    "missing .env.example (make env cannot bootstrap credentials)",
                )
            )
            continue
        # A declared provider key that the template never mentions is one a
        # reader has no way to discover: `make env` writes them a .env that is
        # silently incomplete, and the failure surfaces later as a broken train.
        body = _read(example)
        for secret in read_required_secrets(project):
            if secret not in body:
                findings.append(
                    Finding(
                        "env-example",
                        _rel(example),
                        None,
                        f"does not mention {secret}, which this resource declares "
                        f"in [tool.rasa-catalog] required-secrets",
                    )
                )
    return findings


# --- frozen snapshots ---------------------------------------------------------


def check_snapshot_pins(snapshots: list[Project]) -> list[Finding]:
    """A frozen resource is internally consistent and actually reproducible.

    Nothing here compares a snapshot to RASA_PRO_VERSION — being exempt from
    that is the whole point of freezing it. What is checked is that the three
    places a project records its version agree with each other, and that a lock
    exists. A frozen project without a lock is not frozen; it is just a project
    with a date written on it, and `uv sync` will resolve it to something the
    author never ran.
    """
    findings: list[Finding] = []
    for project in snapshots:
        pin = read_pyproject_pin(project)
        if not pin:
            findings.append(
                Finding(
                    "snapshot-pin",
                    _rel(project.pyproject),
                    None,
                    "declares no rasa-pro==<version> pin; a frozen resource must "
                    "state the exact version it was verified against",
                )
            )
            continue

        if not project.lockfile.is_file():
            findings.append(
                Finding(
                    "snapshot-pin",
                    _rel(project.path),
                    None,
                    f"missing uv.lock; pinning rasa-pro=={pin} without one does "
                    f"not reproduce what was verified (run: uv lock"
                    f"{' --prerelease=allow' if is_prerelease(pin) else ''})",
                )
            )
        else:
            locked = read_lock_version(project)
            if locked != pin:
                findings.append(
                    Finding(
                        "snapshot-pin",
                        _rel(project.lockfile),
                        None,
                        f"resolved rasa-pro=={locked} but pyproject pins {pin}",
                    )
                )

        verified = read_readme_verified(project)
        if verified is None:
            findings.append(
                Finding(
                    "snapshot-pin",
                    _rel(project.path / "README.md"),
                    None,
                    "no 'Verified with: rasa-pro <version>' line; a frozen "
                    "resource is only as good as the claim it carries",
                )
            )
        elif verified != pin:
            findings.append(
                Finding(
                    "snapshot-pin",
                    _rel(project.path / "README.md"),
                    None,
                    f"claims it was verified with rasa-pro {verified} but pins "
                    f"{pin}; one of the two is wrong",
                )
            )

        setting = read_uv_prerelease_setting(project)
        if is_prerelease(pin) and setting != "allow":
            findings.append(
                Finding(
                    "snapshot-pin",
                    _rel(project.pyproject),
                    None,
                    f'pin {pin} is a prerelease but [tool.uv] prerelease is '
                    f"{setting!r}; resolution will fail on a clean clone",
                )
            )
    return findings


def _index_for(project: Project) -> Path:
    """The README that is supposed to list `project`.

    Community resources are indexed once, at the root of their tier. Wave
    projects are indexed by their own cohort, because a wave charter is the
    thing a reader arrives at — not a repo-wide list of every project ever.
    """
    parts = project.rel.split("/")
    if parts[0] == HEROES_ROOT:
        return REPO_ROOT / HEROES_ROOT / parts[1] / "README.md"
    return REPO_ROOT / parts[0] / "README.md"


def check_index_rows(projects: list[Project]) -> list[Finding]:
    """Every contributed resource is reachable from its index.

    An unlisted directory is invisible: nobody browsing the repository finds it,
    and the author gets no credit for work they did. The typed category folders
    keep their inventory by review convention, because a reader can at least
    guess where to look. `community/` is flat and `heroes/` is keyed by cohort,
    so there is nothing to guess from — enforced there.
    """
    findings: list[Finding] = []
    for project in projects:
        root = _rel(project.path).split("/", 1)[0]
        if root not in (COMMUNITY_ROOT, HEROES_ROOT):
            continue
        index = _index_for(project)
        if not index.is_file():
            findings.append(
                Finding(
                    "index-rows",
                    _rel(index),
                    None,
                    f"missing index README; {project.rel} has nowhere to be listed",
                )
            )
            continue
        if project.path.name not in _read(index):
            findings.append(
                Finding(
                    "index-rows",
                    _rel(index),
                    None,
                    f"does not mention {project.path.name!r}; add its catalog row "
                    f"in the same pull request that adds the directory",
                )
            )
    return findings


def check_heroes_layout() -> list[Finding]:
    """Rasa Heroes cohorts follow one shape, so a wave is never half-filed."""
    findings: list[Finding] = []
    programme = REPO_ROOT / HEROES_ROOT / "README.md"
    waves = discover_waves()
    if waves and not programme.is_file():
        return [
            Finding(
                "heroes-layout",
                f"{HEROES_ROOT}/README.md",
                None,
                "missing programme README; it is the index every wave links from",
            )
        ]

    programme_text = _read(programme) if programme.is_file() else ""
    for wave in waves:
        rel = _rel(wave)
        if not WAVE_SLUG_RE.match(wave.name):
            findings.append(
                Finding(
                    "heroes-layout",
                    rel,
                    None,
                    f"{wave.name!r} is not a wave slug; use wave-NN-<theme>, "
                    f"zero-padded so directory order is cohort order "
                    f"(e.g. wave-01-voice)",
                )
            )
        if not (wave / "README.md").is_file():
            findings.append(
                Finding(
                    "heroes-layout",
                    f"{rel}/README.md",
                    None,
                    "missing wave charter (dates, theme, stewards, participants)",
                )
            )
        elif wave.name not in programme_text:
            findings.append(
                Finding(
                    "heroes-layout",
                    f"{HEROES_ROOT}/README.md",
                    None,
                    f"does not list the {wave.name!r} wave",
                )
            )

        # Projects belong under `projects/`. A pyproject anywhere else in the
        # wave is invisible to discovery, so it would silently skip every check.
        for pyproject in sorted(wave.rglob("pyproject.toml")):
            parts = pyproject.relative_to(wave).parts
            if parts[0] != WAVE_DIR or len(parts) != 3:
                findings.append(
                    Finding(
                        "heroes-layout",
                        _rel(pyproject),
                        None,
                        f"project is not at {rel}/{WAVE_DIR}/<project>/ and is "
                        f"therefore skipped by every check",
                    )
                )
    return findings


# ------------------------------------------------------------------------------

# Every check takes (catalog, snapshots, expected) so the registry states, for
# each one, which tier it actually governs. `p` is the maintained catalog; `s`
# is the frozen tier. Checks that read the tree directly ignore both.
CHECKS = {
    "version-consistency": lambda p, s, e: check_version_consistency(e),
    "version-line": lambda p, s, e: check_version_line(e),
    "lock-sync": lambda p, s, e: check_lock_sync(p, e),
    "prerelease-consistency": lambda p, s, e: check_prerelease_consistency(p, e),
    "lock-prereleases": lambda p, s, e: check_lock_prereleases(e),
    "skill-prose": lambda p, s, e: check_skill_prose(),
    "nested-if": lambda p, s, e: check_nested_if(),
    # Both tiers: a frozen resource still has to say who verified it and when.
    "resource-metadata": lambda p, s, e: check_resource_metadata(p + s),
    "secret-hygiene": lambda p, s, e: check_secret_hygiene(),
    "workflow-pins": lambda p, s, e: check_workflow_pins(),
    "agent-config-keys": lambda p, s, e: check_agent_config_keys(),
    "env-example": lambda p, s, e: check_env_examples(p + s),
    "snapshot-pin": lambda p, s, e: check_snapshot_pins(s),
    # Both tiers: `community/` is maintained, `heroes/` is frozen, and a
    # resource in either is unreachable if its index does not list it.
    "index-rows": lambda p, s, e: check_index_rows(p + s),
    "heroes-layout": lambda p, s, e: check_heroes_layout(),
}


def _c(code: str) -> str:
    return code if sys.stdout.isatty() else ""


GREEN, RED, YELLOW, DIM, RESET = (
    _c("\033[92m"), _c("\033[91m"), _c("\033[93m"), _c("\033[2m"), _c("\033[0m")
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument(
        "--check", action="append", default=[], metavar="NAME",
        help="Run only these checks (repeatable)",
    )
    parser.add_argument("--list", action="store_true", help="List check names and exit")
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as failures"
    )
    parser.add_argument("--version", default=None, help="Expected version override")
    args = parser.parse_args()

    if args.list:
        for name in CHECKS:
            print(name)
        return 0

    selected = args.check or list(CHECKS)
    unknown = [c for c in selected if c not in CHECKS]
    if unknown:
        print(f"Unknown check(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    expected = read_expected_version(args.version)
    projects = discover_projects()
    snapshots = discover_projects("snapshots")

    findings: list[Finding] = []
    for name in selected:
        findings.extend(CHECKS[name](projects, snapshots, expected))

    errors = [f for f in findings if f.severity == SEVERITY_ERROR]
    warnings = [f for f in findings if f.severity == SEVERITY_WARNING]

    if args.json:
        print(json.dumps({
            "expected": expected,
            "projects": len(projects),
            "snapshots": len(snapshots),
            "checks": selected,
            "errors": len(errors),
            "warnings": len(warnings),
            "findings": [asdict(f) for f in findings],
        }, indent=2))
        return 1 if errors or (args.strict and warnings) else 0

    print(f"Linting {len(projects)} catalog project(s) against rasa-pro=={expected}")
    if snapshots:
        print(f"{DIM}Plus {len(snapshots)} frozen snapshot(s), held to their own "
              f"pins (see docs/SNAPSHOTS.md){RESET}")
    print(f"{DIM}Checks: {', '.join(selected)}{RESET}\n")

    if not findings:
        print(f"{GREEN}✓ All {len(selected)} checks passed.{RESET}")
        return 0

    by_check: dict[str, list[Finding]] = {}
    for finding in findings:
        by_check.setdefault(finding.check, []).append(finding)

    for name, group in by_check.items():
        print(f"{RED if any(f.severity == SEVERITY_ERROR for f in group) else YELLOW}"
              f"{name}{RESET} ({len(group)})")
        for finding in group:
            mark = "✗" if finding.severity == SEVERITY_ERROR else "⚠"
            colour = RED if finding.severity == SEVERITY_ERROR else YELLOW
            print(f"  {colour}{mark}{RESET} {finding.location()}\n      {finding.message}")
        print()

    passed = len(selected) - len(by_check)
    print(f"{len(errors)} error(s), {len(warnings)} warning(s); {passed} check(s) clean")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
