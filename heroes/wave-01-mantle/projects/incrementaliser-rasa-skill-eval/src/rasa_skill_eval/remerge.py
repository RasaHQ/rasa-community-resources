"""Write improved Agent Skills prose back onto native Mantle ``skill.md``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from rasa_skill_eval.skill_io import (
    MANTLE_EXTRA_KEYS,
    discover_skill_dirs,
    dump_skill_markdown,
    find_skill_file,
    split_frontmatter,
    write_text_utf8,
)

REMERGE_SCHEMA = "v1"
MANTLE_STEP_KEYS: frozenset[str] = frozenset(
    {"id", "execute_tool", "action", "instructions", "complete_when", "if"}
)

_SESSION_TOKEN_RE = re.compile(r"(?<!@memory\.)(?<!`)\bsession\.[A-Za-z0-9_.]+")
_STRUCTURED_PREFIXES = ("if:", "#", "complete_when:")
_ORDERED_BLOCK_RE = re.compile(
    r"(:::ordered_block[^\n]*\n)(.*?)(^:::)",
    re.DOTALL | re.MULTILINE,
)

SESSION_PROSE_ASK = (
    "Mantle `validate_project` rejects `session.*` in instruction prose while allowing "
    "it in `if:` and `tool_constraints.requires`. Reverse-merging improved `SKILL.md` "
    "that mentions those keys makes a previously valid agent fail `rasa train`. Either "
    "substitute `session.*` in prose like `if:`, or document/enforce `@memory.*` at "
    "authoring time so LLM rewrites cannot untrain the project."
)

AGENT_SKILLS_HEADING_ASK = (
    "Reverse-merged Agent Skills headings (`# Title`, `## Instructions`, `## Examples`) "
    "into native Mantle `skill.md` may be rejected by `validate_project`. Dual format: "
    "NVIDIA SkillEvaluator wants those headings; Mantle `skill.md` may not. "
    "Report this to Rasa."
)

UNKNOWN_STEP_ASK = (
    "Reverse-merged Agent Skills YAML invented step keys such as `done_when` that "
    "Mantle ExecuteStep rejects (`extra_forbidden`). Dual format: coding-agent "
    "completion criteria stay on the projected `SKILL.md`; native `skill.md` keeps "
    "only Mantle step keys (`id`, `execute_tool`, `action`, `instructions`, "
    "`complete_when`, `if`). Do not rename `done_when` prose to `complete_when` — "
    "that field is a memory slot. Report this to Rasa if `validate_project` still "
    "fails after stripping unknown keys."
)


def remerge_prose(native_skill_dir: Path, improved_projected_dir: Path) -> Path:
    """Copy description and body from improved ``SKILL.md`` onto native ``skill.md``.

    Mantle-only frontmatter keys on the native file are kept. ``tools.py``,
    ``memory.yml``, and ``responses.yml`` are not touched.
    """
    native_file = find_skill_file(native_skill_dir)
    if native_file is None:
        raise FileNotFoundError(f"No native skill file in {native_skill_dir}")
    improved_file = improved_projected_dir / "SKILL.md"
    if not improved_file.is_file():
        raise FileNotFoundError(f"Improved SKILL.md missing: {improved_file}")

    native_fm, _native_body = split_frontmatter(native_file.read_text(encoding="utf-8"))
    improved_fm, improved_body = split_frontmatter(improved_file.read_text(encoding="utf-8"))
    sanitized_body, dropped = strip_unknown_step_keys(improved_body)
    if dropped:
        logger.info(
            "Stripped {} unknown ordered_block step key(s) while reverse-merging {}",
            dropped,
            native_skill_dir.name,
        )

    merged = _merge_frontmatter(native_fm, improved_fm)
    target = native_skill_dir / "skill.md"
    target.write_text(dump_skill_markdown(merged, sanitized_body), encoding="utf-8")
    if native_file.resolve() != target.resolve() and native_file.name == "SKILL.md":
        native_file.unlink()
    return target


def _merge_frontmatter(
    native: dict[str, Any],
    improved: dict[str, Any],
) -> dict[str, Any]:
    """Keep Mantle keys from native; take portable authoring fields from improved."""
    out = dict(native)
    for key in ("description", "license", "compatibility"):
        if key in improved and improved[key] not in (None, ""):
            out[key] = improved[key]
    native_meta = native.get("metadata") if isinstance(native.get("metadata"), dict) else {}
    improved_meta = improved.get("metadata") if isinstance(improved.get("metadata"), dict) else {}
    if native_meta or improved_meta:
        merged_meta = {str(k): str(v) for k, v in native_meta.items()}
        for key, value in improved_meta.items():
            merged_meta.setdefault(str(key), str(value))
        out["metadata"] = merged_meta
    for key in MANTLE_EXTRA_KEYS:
        if key in native:
            out[key] = native[key]
    return out


def rewrite_session_prose(body: str) -> tuple[str, int]:
    """Replace bare ``session.*`` in instruction prose with ``@memory.session.*``.

    Lines whose stripped text starts with ``if:``, ``#``, or ``complete_when:``
    are left unchanged. Existing ``@memory.session.*`` tokens are not doubled.
    Returns the rewritten body and the number of replacements.
    """

    def _repl(_match: re.Match[str]) -> str:
        return f"@memory.{_match.group(0)}"

    count = 0
    out: list[str] = []
    for line in body.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(_STRUCTURED_PREFIXES):
            out.append(line)
            continue
        rewritten, n = _SESSION_TOKEN_RE.subn(_repl, line)
        count += n
        out.append(rewritten)
    return "".join(out), count


def apply_session_prose_workaround(agent_root: Path) -> int:
    """Rewrite session keys in instruction prose under ``skills/``.

    Returns the number of ``session.*`` tokens replaced across skill files.
    """
    skills = agent_root / "skills"
    if not skills.is_dir():
        return 0
    total = 0
    for skill_dir in discover_skill_dirs(skills):
        skill_file = find_skill_file(skill_dir)
        if skill_file is None:
            continue
        frontmatter, body = split_frontmatter(skill_file.read_text(encoding="utf-8"))
        new_body, n = rewrite_session_prose(body)
        if n == 0:
            continue
        write_text_utf8(skill_file, dump_skill_markdown(frontmatter, new_body))
        total += n
    return total


def strip_unknown_step_keys(body: str) -> tuple[str, int]:
    """Drop non-Mantle keys from ``:::ordered_block`` step maps.

    Returns the rewritten body and the number of keys removed. ``done_when`` is
    discarded rather than renamed to ``complete_when`` (that field is a memory
    slot, not free prose).
    """
    removed = 0

    def _repl(match: re.Match[str]) -> str:
        nonlocal removed
        prefix, inner, suffix = match.group(1), match.group(2), match.group(3)
        try:
            data = yaml.safe_load(inner)
        except yaml.YAMLError:
            return match.group(0)
        if not isinstance(data, dict):
            return match.group(0)
        steps = data.get("steps")
        if not isinstance(steps, list):
            return match.group(0)
        new_steps: list[Any] = []
        dropped = 0
        for step in steps:
            if not isinstance(step, dict):
                new_steps.append(step)
                continue
            cleaned: dict[str, Any] = {}
            for key, value in step.items():
                if str(key) in MANTLE_STEP_KEYS:
                    cleaned[str(key)] = value
                else:
                    dropped += 1
            new_steps.append(cleaned)
        if dropped == 0:
            return match.group(0)
        removed += dropped
        data["steps"] = new_steps
        dumped = yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
        return f"{prefix}{dumped}{suffix}"

    rewritten = _ORDERED_BLOCK_RE.sub(_repl, body)
    return rewritten, removed


def apply_unknown_step_workaround(agent_root: Path) -> int:
    """Strip illegal ordered_block step keys under ``skills/``.

    Returns the number of unknown keys removed across skill files.
    """
    skills = agent_root / "skills"
    if not skills.is_dir():
        return 0
    total = 0
    for skill_dir in discover_skill_dirs(skills):
        skill_file = find_skill_file(skill_dir)
        if skill_file is None:
            continue
        frontmatter, body = split_frontmatter(skill_file.read_text(encoding="utf-8"))
        new_body, n = strip_unknown_step_keys(body)
        if n == 0:
            continue
        write_text_utf8(skill_file, dump_skill_markdown(frontmatter, new_body))
        total += n
    return total
