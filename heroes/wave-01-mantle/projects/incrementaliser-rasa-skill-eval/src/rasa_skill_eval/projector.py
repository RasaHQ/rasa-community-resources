"""Copy a Mantle skill folder into Agent Skills layout: SKILL.md, config/, scripts/."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from rasa_skill_eval.config import ProjectionSettings
from rasa_skill_eval.models import ProjectionSidecar
from rasa_skill_eval.skill_io import (
    MANTLE_EXTRA_KEYS,
    dump_skill_markdown,
    find_skill_file,
    kebab_name,
    split_frontmatter,
)

_H1_RE = re.compile(r"^#\s+\S", re.MULTILINE)
_INSTRUCTIONS_RE = re.compile(r"^##\s+Instructions\s*$", re.MULTILINE | re.IGNORECASE)
_EXAMPLES_RE = re.compile(r"^##\s+Examples\s*$", re.MULTILINE | re.IGNORECASE)
_HEADING_RE = re.compile(r"^#{1,2}\s+(.+?)\s*$", re.MULTILINE)

FALLBACK_EXAMPLE = "Follow Instructions; do not invent account details."


def sidecar_path(projected_dir: Path) -> Path:
    """Return the sidecar JSON path beside the skill folder, not inside it."""
    return projected_dir.parent / ".sidecars" / f"{projected_dir.name}.json"


def has_agent_skills_template(body: str) -> bool:
    """Return True when the body has H1, ``## Instructions``, and ``## Examples``."""
    text = body.strip()
    return bool(
        _H1_RE.search(text) and _INSTRUCTIONS_RE.search(text) and _EXAMPLES_RE.search(text)
    )


def heading_names(body: str) -> set[str]:
    """Return lowercase markdown heading titles in ``body``."""
    return {match.group(1).strip().lower() for match in _HEADING_RE.finditer(body)}


def wrap_agent_skills_body(
    body: str,
    display_name: str,
    example_lines: list[str] | None = None,
) -> str:
    """Ensure NVIDIA Agent Skills headings exist without inventing banking facts.

    Existing H1 / Instructions / Examples sections are left in place.
    """
    text = body.strip()
    title = display_name.strip() or "Skill"
    if not _H1_RE.search(text):
        text = f"# {title}\n\n{text}".strip()
    if not _INSTRUCTIONS_RE.search(text):
        lines = text.splitlines()
        out: list[str] = []
        inserted = False
        for line in lines:
            out.append(line)
            if (
                not inserted
                and line.startswith("# ")
                and not line.startswith("##")
            ):
                out.append("")
                out.append("## Instructions")
                inserted = True
        if not inserted:
            out = ["## Instructions", ""] + out
        text = "\n".join(out).strip()
    if not _EXAMPLES_RE.search(text):
        if example_lines:
            block = "\n".join(f"- Customer: {line}" for line in example_lines)
        else:
            block = FALLBACK_EXAMPLE
        text = f"{text.rstrip()}\n\n## Examples\n\n{block}"
    return f"{text.rstrip()}\n"


def example_lines_for_skill(
    data_dir: Path,
    corpus_name: str,
    skill_folder: str,
) -> list[str]:
    """Return the first user utterance from a matching eval scenario, if any."""
    folder = data_dir / "eval" / "scenarios" / corpus_name
    if not folder.is_dir():
        return []
    wanted = {skill_folder, kebab_name(skill_folder), skill_folder.replace("-", "_")}
    for path in sorted(folder.glob("*.yml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(raw, dict):
            continue
        skill = str(raw.get("skill") or "")
        if skill not in wanted:
            continue
        turns = raw.get("turns")
        if not isinstance(turns, list):
            continue
        for turn in turns:
            if not isinstance(turn, dict):
                continue
            user = str(turn.get("user") or "").strip()
            if user:
                return [user]
    return []


def project_skill(
    skill_dir: Path,
    dest_dir: Path,
    settings: ProjectionSettings,
    example_lines: list[str] | None = None,
) -> ProjectionSidecar:
    """Write an Agent Skills copy of ``skill_dir`` into ``dest_dir``.

    Native files are not modified. Extra Mantle frontmatter is moved to
    ``config/mantle.yml``. Local ``tools.py`` is copied to ``scripts/tools.py``.
    Sidecar metadata is written next to the skill folder, not in the skill root.
    """
    skill_file = find_skill_file(skill_dir)
    if skill_file is None:
        raise FileNotFoundError(f"No skill markdown in {skill_dir}")
    frontmatter, body = split_frontmatter(skill_file.read_text(encoding="utf-8"))
    skill_id = skill_dir.name
    projected_name = kebab_name(skill_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    extra: dict[str, Any] = {}
    moved: list[str] = []
    for key in list(frontmatter):
        if key in MANTLE_EXTRA_KEYS:
            extra[key] = frontmatter.pop(key)
            moved.append(key)

    display = str(frontmatter.get("name") or skill_id)
    rewritten: list[str] = []
    if frontmatter.get("name") != projected_name:
        rewritten.append("name")
    frontmatter["name"] = projected_name
    if "description" not in frontmatter or not str(frontmatter.get("description")).strip():
        frontmatter["description"] = f"Mantle skill {skill_id}."
        rewritten.append("description")
    if "license" not in frontmatter:
        frontmatter["license"] = settings.license
        rewritten.append("license")
    if "version" not in frontmatter:
        frontmatter["version"] = settings.metadata_version
        rewritten.append("version")
    if "compatibility" not in frontmatter:
        frontmatter["compatibility"] = settings.compatibility
        rewritten.append("compatibility")
    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        rewritten.append("metadata")
    metadata.setdefault("author", settings.author)
    metadata.setdefault("version", settings.metadata_version)
    metadata["rasa_skill_id"] = skill_id
    metadata["rasa_display_name"] = display
    # Agent Skills metadata values must be strings.
    frontmatter["metadata"] = {str(k): str(v) for k, v in metadata.items()}

    wrapped = wrap_agent_skills_body(body, display, example_lines)
    if wrapped.strip() != body.strip():
        rewritten.append("body_headings")
    (dest_dir / "SKILL.md").write_text(
        dump_skill_markdown(frontmatter, wrapped), encoding="utf-8"
    )
    copied: list[str] = ["SKILL.md"]

    if extra:
        config_dir = dest_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        from yaml import safe_dump

        (config_dir / "mantle.yml").write_text(
            safe_dump(extra, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        copied.append("config/mantle.yml")

    tools_py = skill_dir / "tools.py"
    if tools_py.is_file():
        scripts = dest_dir / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tools_py, scripts / "tools.py")
        copied.append("scripts/tools.py")

    tools_dir = skill_dir / "tools"
    if tools_dir.is_dir():
        shutil.copytree(tools_dir, dest_dir / "scripts" / "tools", dirs_exist_ok=True)
        copied.append("scripts/tools/")

    for companion in ("memory.yml", "responses.yml"):
        src = skill_dir / companion
        if src.is_file():
            config_dir = dest_dir / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, config_dir / companion)
            copied.append(f"config/{companion}")

    refs = skill_dir / "references"
    if refs.is_dir():
        shutil.copytree(refs, dest_dir / "references", dirs_exist_ok=True)
        copied.append("references/")

    sidecar = ProjectionSidecar(
        source_skill_id=skill_id,
        source_display_name=display,
        projected_name=projected_name,
        source_path=str(skill_dir),
        projected_path=str(dest_dir),
        rewritten_fields=rewritten,
        moved_frontmatter=moved,
        copied_files=copied,
    )
    dest = sidecar_path(dest_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(sidecar.model_dump_json(indent=2), encoding="utf-8")
    copied.append(f".sidecars/{dest_dir.name}.json")
    sidecar.copied_files = copied
    return sidecar


def load_sidecar(projected_dir: Path) -> ProjectionSidecar | None:
    """Load sidecar JSON from the sibling ``.sidecars`` folder or a legacy skill-root file."""
    for path in (sidecar_path(projected_dir), projected_dir / "projection.json"):
        if not path.is_file():
            continue
        try:
            return ProjectionSidecar.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    return None
