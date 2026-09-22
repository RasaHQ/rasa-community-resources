"""Rewrite projected SKILL.md files using writing-for-agents, then unslop."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from loguru import logger

from rasa_skill_eval.config import ProjectionSettings
from rasa_skill_eval.llm.types import ChatClient, ChatMessage
from rasa_skill_eval.models import ImproverDelta
from rasa_skill_eval.projector import has_agent_skills_template, heading_names
from rasa_skill_eval.skill_io import (
    dump_skill_markdown,
    find_skill_file,
    read_text_utf8,
    split_frontmatter,
    write_text_utf8,
)

LEADING_VERBS = (
    "Help",
    "Block",
    "Transfer",
    "Check",
    "List",
    "Add",
    "Remove",
    "Answer",
    "Create",
    "Greet",
    "Close",
    "Load",
    "Look",
    "Write",
    "Evaluate",
)

FALLBACK_WRITING_RULES = """
Write Agent Skills for a coding-agent linter.
Front-load the description with a leading verb and when to activate.
Add Error handling, Prerequisites, and Limitations when they are missing.
Do not invent banking facts. Keep 'do not invent' rules.
Do not delete YAML frontmatter keys. Return the full SKILL.md.
"""

CACHE_SCHEMA = "v3"
NOOP_WORD_DELTA = 8


def _approx_tokens(text: str) -> int:
    """Cheap token estimate: whitespace-separated words."""
    return len(text.split())


def _ensure_section(body: str, heading: str, paragraph: str) -> tuple[str, bool]:
    """Append a markdown section when the heading is missing."""
    if re.search(rf"^##\s+{re.escape(heading)}\s*$", body, re.MULTILINE | re.IGNORECASE):
        return body, False
    addition = f"\n\n## {heading}\n\n{paragraph.strip()}\n"
    return body.rstrip() + addition, True


def _is_noop_rewrite(original: str, rewritten: str) -> bool:
    """Return True when the rewrite barely changes the projected skeleton."""
    _, original_body = split_frontmatter(original)
    _, rewritten_body = split_frontmatter(rewritten)
    orig_headings = heading_names(original_body)
    new_headings = heading_names(rewritten_body)
    word_delta = abs(_approx_tokens(rewritten_body) - _approx_tokens(original_body))
    return new_headings <= orig_headings and word_delta <= NOOP_WORD_DELTA


def _load_skill_text(skill_dir: Path | None) -> str:
    """Read SKILL.md plus optional SKILL-MECHANICS.md from a vendored skill folder."""
    if skill_dir is None or not skill_dir.is_dir():
        return ""
    skill_file = find_skill_file(skill_dir)
    parts: list[str] = []
    if skill_file is not None:
        parts.append(read_text_utf8(skill_file))
    mechanics = skill_dir / "SKILL-MECHANICS.md"
    if mechanics.is_file():
        parts.append(read_text_utf8(mechanics))
    return "\n\n".join(parts)


def _extract_skill_md(text: str) -> str | None:
    """Pull a SKILL.md document out of an LLM reply if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:markdown|md)?\n", "", stripped)
        stripped = re.sub(r"\n```$", "", stripped)
    if stripped.startswith("---") and "\n---" in stripped[3:]:
        return stripped
    match = re.search(r"---\n[\s\S]+?\n---\n[\s\S]+", stripped)
    if match:
        return match.group(0)
    return None


def _heuristic_rewrite(
    frontmatter: dict[str, object],
    body: str,
    dest_dir: Path,
    settings: ProjectionSettings,
) -> tuple[dict[str, object], str, list[str]]:
    """Deterministic hygiene helper preserved for offline non-LLM tests only."""
    changes: list[str] = []
    description = str(frontmatter.get("description") or "").strip()
    if description and not description[0].isupper():
        description = description[0].upper() + description[1:]
        changes.append("capitalized description")
    lower = description.lower()
    if description and "when" not in lower and "activate" not in lower:
        description = (
            f"{description.rstrip('.')} Activate when the user asks for this capability."
        )
        changes.append("added activate-when trigger phrasing")
    if description and not any(description.startswith(v) for v in LEADING_VERBS):
        pass
    frontmatter["description"] = description

    if not frontmatter.get("license"):
        frontmatter["license"] = settings.license
        changes.append("stamped license")
    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    if "author" not in metadata:
        metadata["author"] = settings.author
        changes.append("stamped metadata.author")
    frontmatter["metadata"] = {str(k): str(v) for k, v in metadata.items()}

    if "Do not invent" in body or "do not invent" in body.lower():
        body, added = _ensure_section(
            body,
            "Limitations",
            "Do not invent accounts, balances, payees, cards, or policy facts. "
            "Use tools and references. If they do not contain the answer, say so.",
        )
        if added:
            changes.append("added Limitations section")

    body, added_err = _ensure_section(
        body,
        "Error handling",
        "If a tool fails or returns no data, tell the customer what happened "
        "and stop. Do not guess a result.",
    )
    if added_err:
        changes.append("added Error handling section")

    if (dest_dir / "scripts").is_dir() or (dest_dir / "config" / "mantle.yml").is_file():
        body, added_prereq = _ensure_section(
            body,
            "Prerequisites",
            "Customer identity and account data come from Mantle tools and "
            "project memory. Do not proceed without a successful tool result "
            "when a lookup is required.",
        )
        if added_prereq:
            changes.append("added Prerequisites section")
    return frontmatter, body, changes


def _try_complete(
    client: ChatClient,
    messages: list[ChatMessage],
    label: str,
) -> str | None:
    """Call the chat client and return assistant text, or None after a logged failure."""
    try:
        result = client.complete(messages)
    except Exception as exc:
        logger.warning("Improver {} LLM call failed; continuing: {}", label, exc)
        return None
    return result.text


def _llm_rewrite(
    original: str,
    client: ChatClient,
    writing_rules: str,
    unslop_rules: str,
) -> tuple[str | None, list[str]]:
    """Ask the improver model to rewrite SKILL.md in one call."""
    changes: list[str] = []
    user_parts = [
        "Follow this writing-for-agents skill:\n\n",
        writing_rules[:12000],
        "\n\nRewrite this SKILL.md:\n\n",
        original,
    ]
    if unslop_rules.strip():
        user_parts.extend(
            [
                "\n\nAlso apply this unslop skill. Keep meaning, tool names, and frontmatter:\n\n",
                unslop_rules[:8000],
            ]
        )
    text = _try_complete(
        client,
        [
            ChatMessage(
                role="system",
                content=(
                    "You rewrite one Agent Skills SKILL.md. "
                    "Return only the full document with YAML frontmatter. "
                    "Keep a top-level '# Title', '## Instructions', and '## Examples'. "
                    "Apply writing-for-agents: leading-word description. "
                    "Put completion criteria in instruction prose ('Done when …'), "
                    "never as new YAML keys inside :::ordered_block. "
                    "Do not add step properties other than those already present. "
                    "Never drop a 'do not invent' limitation. "
                    "Do not invent banking facts. Keep tool names."
                ),
            ),
            ChatMessage(role="user", content="".join(user_parts)),
        ],
        "writing-for-agents",
    )
    if text is None:
        return None, changes
    rewritten = _extract_skill_md(text)
    if rewritten is None:
        logger.warning("Improver LLM did not return a valid SKILL.md markdown block")
        return None, changes
    changes.append("llm writing-for-agents rewrite")
    if unslop_rules.strip():
        changes.append("llm unslop in same call")
    return rewritten, changes


def _source_hash(
    original: str,
    model_id: str,
    *,
    writing_rules: str = "",
    unslop_rules: str = "",
    extra: str = "",
) -> str:
    """Stable cache key for SKILL.md plus every input that changes the rewrite."""
    payload = "\n".join(
        [CACHE_SCHEMA, model_id, writing_rules, unslop_rules, extra, original]
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _cache_root(cache_dir: Path, cache_id: str) -> Path:
    """Return the folder for one cached improved skill."""
    return cache_dir.joinpath(*cache_id.split("/"))


def _read_cached_skill(
    cache_dir: Path,
    cache_id: str,
    source_hash: str,
) -> str | None:
    """Return cached SKILL.md when the source hash matches."""
    root = _cache_root(cache_dir, cache_id)
    meta_path = root / "meta.json"
    skill_path = root / "SKILL.md"
    if not meta_path.is_file() or not skill_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(meta, dict) or str(meta.get("source_hash") or "") != source_hash:
        return None
    if meta.get("schema_ok") is False:
        return None
    text = skill_path.read_text(encoding="utf-8")
    _, body = split_frontmatter(text)
    if not has_agent_skills_template(body):
        return None
    return text


def _write_cached_skill(
    cache_dir: Path,
    cache_id: str,
    source_hash: str,
    model_id: str,
    skill_md: str,
) -> None:
    """Persist a successful LLM rewrite for later runs."""
    root = _cache_root(cache_dir, cache_id)
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(skill_md, encoding="utf-8")
    (root / "meta.json").write_text(
        json.dumps(
            {
                "source_hash": source_hash,
                "model_id": model_id,
                "cache_schema": CACHE_SCHEMA,
                "schema_ok": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def improve_projected_skill(
    source_dir: Path,
    dest_dir: Path,
    settings: ProjectionSettings,
    client: ChatClient | None = None,
    backup_client: ChatClient | None = None,
    writing_for_agents_dir: Path | None = None,
    unslop_dir: Path | None = None,
    cache_dir: Path | None = None,
    cache_id: str = "",
    reimprove: bool = False,
    improver_model_id: str = "",
) -> ImproverDelta:
    """Copy a projected skill and rewrite SKILL.md via pure LLM.

    Never delete ``config/mantle.yml``.
    """
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(source_dir, dest_dir)
    skill_md = dest_dir / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"Projected skill missing SKILL.md: {dest_dir}")

    original = read_text_utf8(skill_md)
    mode = "failed"
    changes: list[str] = []
    degraded = False
    writing_rules = _load_skill_text(writing_for_agents_dir) or FALLBACK_WRITING_RULES
    unslop_rules = _load_skill_text(unslop_dir)
    extra = (
        f"license={settings.license}\nauthor={settings.author}\n"
        f"compat={settings.compatibility}\nmeta={settings.metadata_version}"
    )
    source_hash = _source_hash(
        original,
        improver_model_id,
        writing_rules=writing_rules,
        unslop_rules=unslop_rules,
        extra=extra,
    )
    cache_key = cache_id or dest_dir.name

    if cache_dir is not None and not reimprove:
        cached = _read_cached_skill(cache_dir, cache_key, source_hash)
        if cached is not None:
            write_text_utf8(skill_md, cached if cached.endswith("\n") else cached + "\n")
            changes.append("cache hit")
            mode = "cached"

    # Pure LLM rewrite: try primary client first, switch to backup_client if primary fails.
    if mode != "cached":
        clients_to_try: list[tuple[str, ChatClient]] = []
        if client is not None:
            clients_to_try.append(("primary", client))
        if backup_client is not None:
            clients_to_try.append(("backup", backup_client))

        rewritten: str | None = None
        for client_role, current_client in clients_to_try:
            candidate_rewritten, llm_changes = _llm_rewrite(
                original, current_client, writing_rules, unslop_rules
            )
            if candidate_rewritten is not None:
                try:
                    frontmatter, body = split_frontmatter(candidate_rewritten)
                    if not has_agent_skills_template(body):
                        logger.warning(
                            "Improver {} rewrite missing Agent Skills headings",
                            client_role,
                        )
                        continue
                    if _is_noop_rewrite(original, candidate_rewritten):
                        logger.warning(
                            "Improver {} rewrite is a near-noop; trying next client",
                            client_role,
                        )
                        continue
                    if not frontmatter.get("license"):
                        frontmatter["license"] = settings.license
                        llm_changes.append("stamped license")
                    metadata = frontmatter.get("metadata")
                    if not isinstance(metadata, dict):
                        metadata = {}
                    metadata.setdefault("author", settings.author)
                    frontmatter["metadata"] = {str(k): str(v) for k, v in metadata.items()}
                    rewritten = dump_skill_markdown(frontmatter, body)
                    changes.extend(llm_changes)
                    if client_role == "backup":
                        changes.append("rewritten using backup improver model")
                    mode = "llm"
                    break
                except Exception as exc:
                    logger.warning(
                        "Improved SKILL.md unreadable from {} client: {}", client_role, exc
                    )
            else:
                logger.warning("Improver {} client failed to produce rewrite", client_role)

        if rewritten is not None:
            write_text_utf8(skill_md, rewritten)
            if cache_dir is not None:
                _write_cached_skill(
                    cache_dir,
                    cache_key,
                    source_hash,
                    improver_model_id,
                    read_text_utf8(skill_md),
                )
        else:
            degraded = True
            changes.append(
                "llm rewrite failed schema/noop gate or timed out; "
                "original skill kept without heuristic alteration"
            )

    constraints_ok = assert_constraints_preserved(source_dir, dest_dir)
    if not constraints_ok:
        degraded = True
        changes.append("config/mantle.yml changed or missing")

    return ImproverDelta(
        skill_id=dest_dir.name,
        baseline_skill_md_words=_approx_tokens(original),
        improved_skill_md_words=_approx_tokens(read_text_utf8(skill_md)),
        constraints_preserved=constraints_ok,
        changes=changes,
        mode=mode,
        degraded=degraded,
        source_hash=source_hash,
        mantle_yml_match=constraints_ok,
    )


def assert_constraints_preserved(source_dir: Path, improved_dir: Path) -> bool:
    """Return True when Mantle control YAML survived the improver copy."""
    src = source_dir / "config" / "mantle.yml"
    if not src.is_file():
        return True
    dst = improved_dir / "config" / "mantle.yml"
    if not dst.is_file():
        return False
    return src.read_text(encoding="utf-8") == dst.read_text(encoding="utf-8")
