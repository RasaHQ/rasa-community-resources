#!/usr/bin/env python3
"""Static correctness checks for one Rasa Mantle project.

Fast and offline: stdlib only, no network, no venv needed — safe as a
pre-commit hook in a repo where nothing is installed yet. Run from the
project root:

    python3 scripts/lint_mantle.py
    python3 scripts/lint_mantle.py --list
    python3 scripts/lint_mantle.py --check agent-top-level-keys --check nested-if
    python3 scripts/lint_mantle.py --json

Every check encodes a failure a real Mantle project has actually hit
(source: RasaHQ/rasa-community-resources, verified 2026-09-02 at
rasa-pro 3.20.0.dev6). This layer answers "is the project internally
consistent?" — only `rasa validate` / `rasa train` in a synced venv answers
"does the engine accept it?". A green lint is necessary, not sufficient.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path.cwd()

# Prompt-tuning keys the engine reads ONLY from the top level of agent.yml.
# `tool_timeout` arrived in 3.20.0.dev6; re-derive this list from the
# installed engine after every version bump.
TOP_LEVEL_AGENT_KEYS = (
    "name",
    "description",
    "rules",
    "conversation",
    "references",
    "before_end",
    "tool_timeout",
)

# Keys that used to live inline under `llm:` and were removed in 3.20.0.dev6.
INLINE_LLM_KEYS = ("provider", "model", "api_key_env", "api_key")

SECRET_PATTERNS = (
    ("OpenAI-style key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("JWT / licence", re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.")),
)

# Retired product names. Spelled in parts so this file passes its own check.
RETIRED_TERMS = {"ma" + "estro": "Mantle"}

SESSION_REF_RE = re.compile(r"(?<![\w.])session\.([\w-]+)\.([\w-]+)")
MEMORY_TOKEN_RE = re.compile(r"@memory(?:\.[\w-]+)*")
ENV_VAR_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
PRERELEASE_RE = re.compile(r"(a|b|rc|\.dev)\d*$")

TEXT_GLOBS = ("*.md", "*.toml", "*.yml", "*.yaml", "*.py", "*.example", "Makefile")


@dataclass
class Finding:
    check: str
    path: str
    line: int | None
    message: str

    def location(self) -> str:
        return f"{self.path}:{self.line}" if self.line else self.path


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


# Directories whose contents are teaching material, not the project's own config.
# A tutorial deliberately shows the OLD shape at step 0 and fixes it by step 3;
# linting those snippets reports the lesson as a defect. The catalog's own
# lint_repo.py never hits this because it reads exactly `<project>/integrations.yml`
# rather than globbing, so this is the price of the recursive glob and has to be
# paid explicitly.
TEACHING_DIRS = {"snippets", "steps", "solutions", "before", "broken"}


def _is_teaching(path: Path) -> bool:
    return bool(set(path.parts) & TEACHING_DIRS)


def _files(*globs: str) -> list[Path]:
    """Tracked files when git is available; a pruned filesystem walk otherwise.

    Teaching snippets are excluded from both paths — see TEACHING_DIRS.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard", *globs],
            capture_output=True, text=True, check=True,
        ).stdout
        return [
            ROOT / p
            for p in out.split("\0")
            if p and (ROOT / p).is_file() and not _is_teaching(Path(p))
        ]
    except (subprocess.CalledProcessError, FileNotFoundError):
        skip = {".git", ".venv", "node_modules", "models", "__pycache__", ".rasa"}
        found: list[Path] = []
        for glob in globs or ("**/*",):
            pattern = glob if "**" in glob or "/" in glob else f"**/{glob}"
            for p in ROOT.glob(pattern):
                if p.is_file() and not (set(p.parts) & skip) and not _is_teaching(p):
                    found.append(p)
        return sorted(set(found))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _numbered(text: str):
    return enumerate(text.splitlines(), start=1)


# ------------------------------------------------------------------------------
# checks
# ------------------------------------------------------------------------------


def check_agent_top_level_keys() -> list[Finding]:
    """Prompt-tuning keys must sit beside `agent:`, never inside it.

    The most expensive kind of regression: silent. Keys nested under `agent:`
    parse without error and are then discarded — a real catalog carried 39
    declared rules the engine never applied, found only by reading the built
    prompt. The indent is derived from the file, so 4-space YAML can't slip
    past a 2-space assumption.
    """
    findings: list[Finding] = []
    for path in _files("agent.yml", "**/agent.yml"):
        lines = _read(path).splitlines()
        try:
            start = next(i for i, l in enumerate(lines) if l.rstrip() == "agent:")
        except StopIteration:
            continue
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
            if ":" not in line or len(line) - len(line.lstrip()) != child_indent:
                continue
            key = line.strip().split(":", 1)[0]
            if key in TOP_LEVEL_AGENT_KEYS:
                findings.append(Finding(
                    "agent-top-level-keys", _rel(path), i + 1,
                    f"{key!r} is nested inside 'agent:', where the engine parses "
                    f"it and then silently discards it. Move it to the top level "
                    f"of agent.yml, as a sibling of 'agent:'.",
                ))
    return findings


def check_llm_model_group() -> list[Finding]:
    """`llm:` names a model group; provider settings live on the group.

    3.20.0.dev6 made the LLM config extra="forbid" with a required
    model_group. The inline form fails validate with
    "'provider': Extra inputs are not permitted" — and every pre-dev6
    example on the internet still shows the inline form.
    """
    findings: list[Finding] = []
    for path in _files("integrations.yml", "**/integrations.yml"):
        lines = _read(path).splitlines()
        try:
            start = next(i for i, l in enumerate(lines) if l.rstrip() == "llm:")
        except StopIteration:
            continue
        saw_model_group = False
        for i in range(start + 1, len(lines)):
            line = lines[i]
            if line.strip() and not line[0].isspace():
                break
            stripped = line.strip()
            if stripped.startswith("#") or ":" not in stripped:
                continue
            key = stripped.split(":", 1)[0]
            if key == "model_group":
                saw_model_group = True
            elif key in INLINE_LLM_KEYS:
                findings.append(Finding(
                    "llm-model-group", _rel(path), i + 1,
                    f"{key!r} is set inline under 'llm:'. Since 3.20.0.dev6 the "
                    f"orchestrator LLM is a model-group reference: use "
                    f"'llm: {{model_group: <id>}}' and declare the provider under "
                    f"a matching 'model_groups' entry.",
                ))
        if not saw_model_group:
            findings.append(Finding(
                "llm-model-group", _rel(path), start + 1,
                "'llm:' does not name a model_group; validate will reject it "
                "with \"'model_group': Field required\"",
            ))
    return findings


def check_project_memory_writes() -> list[Finding]:
    """Project-level memory is tool-written; the LLM may not set it.

    3.20.0.dev6 rejects `llm_settable: true` on a root memory.yml field
    outright. Skill-scoped memory (skills/<id>/memory.yml) is where the flag
    belongs, so only root files are checked.
    """
    findings: list[Finding] = []
    for path in _files("memory.yml"):
        if path.parent != ROOT:
            continue
        for lineno, line in _numbered(_read(path)):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.match(r"^llm_settable:\s*true\b", stripped):
                findings.append(Finding(
                    "project-memory-writes", _rel(path), lineno,
                    "project memory cannot be llm_settable — the engine rejects "
                    "it. Have a tool write the field, or move it into "
                    "skills/<id>/memory.yml.",
                ))
    return findings


def _prose_lines(text: str):
    """Yield (lineno, line) for skill.md text the LLM reads as prose.

    Skips YAML frontmatter and `:::block ... :::` regions (those are YAML,
    not prose). Top-level `if:` lines are conditions, also skipped.
    """
    lines = text.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                i = j + 1
                break
    in_block = False
    while i < len(lines):
        line = lines[i]
        i += 1
        stripped = line.strip()
        if stripped.startswith(":::"):
            in_block = not in_block and stripped != ":::"
            continue
        if in_block:
            continue
        if re.match(r"^if:\s*\S", line):
            continue
        yield i, line


def check_nested_if() -> list[Finding]:
    """`if:` only works at the top level of a skill body, never indented."""
    findings: list[Finding] = []
    for skill in _files("**/skill.md"):
        for lineno, line in _numbered(_read(skill)):
            if re.match(r"^[ \t]+if:\s*\S", line):
                findings.append(Finding(
                    "nested-if", _rel(skill), lineno,
                    "indented 'if:' is not parsed as a condition; it stays "
                    "instruction prose. Move the branch to the top level of the "
                    "skill body, or express it in natural language.",
                ))
    return findings


def check_skill_prose() -> list[Finding]:
    """Skill prose must not contain raw `session.*` or partial @memory tokens."""
    findings: list[Finding] = []
    for skill in _files("**/skill.md"):
        for lineno, line in _prose_lines(_read(skill)):
            for match in SESSION_REF_RE.finditer(line):
                findings.append(Finding(
                    "skill-prose", _rel(skill), lineno,
                    f"session.{match.group(1)}.{match.group(2)} appears in "
                    f"instruction prose; it is not substituted there. Use "
                    f"@memory.{match.group(1)}.{match.group(2)} or move it into "
                    f"a top-level 'if:'.",
                ))
            for match in MEMORY_TOKEN_RE.finditer(line):
                if len(match.group(0).split(".")) != 3:
                    findings.append(Finding(
                        "skill-prose", _rel(skill), lineno,
                        f"{match.group(0)!r} is not a substitutable token; live "
                        f"values require @memory.<namespace>.<entry>",
                    ))
    return findings


def check_engine_version_pin() -> list[Finding]:
    """The pin must be a pre-release the engine actually ships on.

    The Mantle engine exists ONLY on the 3.20.0.dev line; the newest stable
    rasa-pro ships no engine package at all. And 3.20 raised the Python floor
    to 3.11 — a lower floor fails `uv lock` with a resolver error that never
    mentions Python.
    """
    findings: list[Finding] = []
    path = ROOT / "pyproject.toml"
    if not path.is_file():
        return [Finding("engine-version-pin", "pyproject.toml", None,
                        "missing pyproject.toml")]
    text = _read(path)
    pin = re.search(r'"rasa-pro==([^"]+)"', text)
    if not pin:
        findings.append(Finding(
            "engine-version-pin", _rel(path), None,
            "no exact 'rasa-pro==<version>' pin found; an unpinned or ranged "
            "dependency can resolve to a stable release with no engine package",
        ))
    elif not PRERELEASE_RE.search(pin.group(1)):
        findings.append(Finding(
            "engine-version-pin", _rel(path), None,
            f"rasa-pro=={pin.group(1)} is a stable pin — stable releases ship "
            f"no Mantle engine (verified against published wheels). Pin a "
            f"3.20.0.dev release. Delete this check only when a stable release "
            f"ships rasa.mantle.",
        ))
    if pin and PRERELEASE_RE.search(pin.group(1)):
        if not re.search(r'prerelease\s*=\s*"allow"', text):
            findings.append(Finding(
                "engine-version-pin", _rel(path), None,
                "pre-release pin without '[tool.uv] prerelease = \"allow\"' — "
                "uv will refuse to resolve it",
            ))
    floor = re.search(r'requires-python\s*=\s*">=(\d+)\.(\d+)', text)
    if floor and (int(floor.group(1)), int(floor.group(2))) < (3, 11):
        findings.append(Finding(
            "engine-version-pin", _rel(path), None,
            f"requires-python floor {floor.group(1)}.{floor.group(2)} is below "
            f"3.11; rasa-pro 3.20 needs >=3.11 and uv's resolver error will not "
            f"mention Python",
        ))
    return findings


def check_secret_hygiene() -> list[Finding]:
    """No credentials committed, no .env tracked, .env gitignored."""
    findings: list[Finding] = []
    try:
        tracked = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", ".env", "**/.env"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        tracked = []
    for p in tracked:
        findings.append(Finding("secret-hygiene", p, None, ".env is tracked by git"))
    gitignore = ROOT / ".gitignore"
    if not gitignore.is_file() or ".env" not in _read(gitignore):
        findings.append(Finding(
            "secret-hygiene", ".gitignore", None,
            "'.env' is not gitignored — one 'git add -A' away from publishing "
            "credentials",
        ))
    for path in _files(*TEXT_GLOBS):
        if path.name == "uv.lock":
            continue
        for lineno, line in _numbered(_read(path)):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(
                        "secret-hygiene", _rel(path), lineno,
                        f"looks like a committed {label}",
                    ))
    return findings


def check_env_example() -> list[Finding]:
    """.env.example exists and names every key the config actually reads."""
    findings: list[Finding] = []
    example = ROOT / ".env.example"
    if not example.is_file():
        return [Finding(
            "env-example", ".env.example", None,
            "missing .env.example — a new user has no way to discover which "
            "credentials this project needs",
        )]
    body = _read(example)
    used: dict[str, str] = {}
    for path in _files("*.yml", "**/*.yml", "*.yaml", "**/*.yaml"):
        for match in ENV_VAR_RE.finditer(_read(path)):
            used.setdefault(match.group(1), _rel(path))
    pyproject = ROOT / "pyproject.toml"
    if pyproject.is_file():
        block = re.search(
            r"required-secrets\s*=\s*\[([^\]]*)\]", _read(pyproject))
        if block:
            for name in re.findall(r'"([A-Z][A-Z0-9_]*)"', block.group(1)):
                used.setdefault(name, "pyproject.toml required-secrets")
    for var, where in sorted(used.items()):
        if var not in body:
            findings.append(Finding(
                "env-example", ".env.example", None,
                f"does not mention {var}, which is read by {where}; `cp "
                f".env.example .env` produces a silently incomplete file and "
                f"the failure surfaces later as an unexpanded ${{{var}}}",
            ))
    return findings


def check_retired_brand() -> list[Finding]:
    """Retired product names appear nowhere in content or paths.

    Not cosmetics: `rasa init --engine <old-name>` sat in READMEs as a
    copy-paste instruction after the CLI had narrowed to {calm,mantle} and
    rejected it. A stale brand in a runnable command is a broken command.
    """
    findings: list[Finding] = []
    for retired, replacement in RETIRED_TERMS.items():
        pattern = re.compile(re.escape(retired), re.IGNORECASE)
        for path in _files(*TEXT_GLOBS):
            if path.name == "uv.lock":
                continue
            for lineno, line in _numbered(_read(path)):
                if pattern.search(line):
                    findings.append(Finding(
                        "retired-brand", _rel(path), lineno,
                        f"{retired!r} is retired; use {replacement!r}",
                    ))
            if pattern.search(_rel(path)):
                findings.append(Finding(
                    "retired-brand", _rel(path), None,
                    f"path contains the retired name {retired!r}",
                ))
    return findings


CHECKS = {
    "agent-top-level-keys": check_agent_top_level_keys,
    "llm-model-group": check_llm_model_group,
    "project-memory-writes": check_project_memory_writes,
    "nested-if": check_nested_if,
    "skill-prose": check_skill_prose,
    "engine-version-pin": check_engine_version_pin,
    "secret-hygiene": check_secret_hygiene,
    "env-example": check_env_example,
    "retired-brand": check_retired_brand,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--check", action="append", default=[], metavar="NAME",
                        help="Run only these checks (repeatable)")
    parser.add_argument("--list", action="store_true", help="List check names and exit")
    args = parser.parse_args()

    if args.list:
        print("\n".join(CHECKS))
        return 0

    selected = args.check or list(CHECKS)
    unknown = [c for c in selected if c not in CHECKS]
    if unknown:
        print(f"Unknown check(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for name in selected:
        findings.extend(CHECKS[name]())

    if args.json:
        print(json.dumps({"findings": [asdict(f) for f in findings]}, indent=2))
    else:
        for f in findings:
            print(f"[{f.check}] {f.location()}: {f.message}")
        n = len(findings)
        print(f"\n{'FAILED' if n else 'ok'} — {n} finding(s) "
              f"across {len(selected)} check(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
