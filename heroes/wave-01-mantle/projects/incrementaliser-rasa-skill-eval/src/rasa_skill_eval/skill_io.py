"""Parse and dump ``skill.md`` / ``SKILL.md`` YAML frontmatter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

MANTLE_EXTRA_KEYS: frozenset[str] = frozenset(
    {
        "requires",
        "complete_when",
        "import_tools",
        "tool_constraints",
        "utter",
        "disabled",
        "routing",
    }
)

SKILL_FILENAMES: tuple[str, ...] = ("skill.md", "SKILL.md")


def read_text_utf8(path: Path) -> str:
    """Read text as UTF-8, falling back to Windows-1252 if the file is not UTF-8."""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def write_text_utf8(path: Path, text: str) -> None:
    """Write text as UTF-8. Required on Windows, where ``Path.write_text`` uses the locale."""
    path.write_text(text, encoding="utf-8", newline="\n")


def find_skill_file(skill_dir: Path) -> Path | None:
    """Return the skill markdown path in ``skill_dir``, or None."""
    lower = skill_dir / "skill.md"
    upper = skill_dir / "SKILL.md"
    if lower.is_file():
        return lower
    if upper.is_file():
        return upper
    return None


def discover_skill_dirs(root: Path) -> list[Path]:
    """Find directories under ``root``, including ``root`` itself, that contain a skill file."""
    if not root.is_dir():
        return []
    found: list[Path] = []
    candidates = [root, *sorted(p for p in root.rglob("*") if p.is_dir())]
    for path in candidates:
        if find_skill_file(path) is None:
            continue
        if any(part in {".git", ".venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        found.append(path)
    return found


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from a markdown body."""
    if not text.startswith("---"):
        return {}, text
    rest = text[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    end = rest.find("\n---")
    if end < 0:
        return {}, text
    raw_yaml = rest[:end]
    body = rest[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    data = yaml.safe_load(raw_yaml) or {}
    if not isinstance(data, dict):
        return {}, text
    return data, body


def dump_skill_markdown(frontmatter: dict[str, Any], body: str) -> str:
    """Serialize frontmatter plus body to a skill markdown string."""
    dumped = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    body_text = body.strip()
    return f"---\n{dumped}---\n\n{body_text}\n"


def kebab_name(skill_id: str) -> str:
    """Turn a Mantle folder id into an Agent Skills kebab-case name."""
    return skill_id.replace("_", "-").strip("-").lower()
