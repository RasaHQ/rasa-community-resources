"""Tag skills as skill-local, project-global, engine-managed, or coding-agent."""

from __future__ import annotations

from pathlib import Path

from rasa_skill_eval.models import MantleInventory, SkillScope
from rasa_skill_eval.skill_io import find_skill_file


def _is_mantle_agent(project_root: Path | None) -> bool:
    """Return True when ``project_root`` looks like a Mantle agent project."""
    return project_root is not None and (project_root / "agent.yml").is_file()


def tag_inventory(inv: MantleInventory, project_root: Path | None = None) -> list[SkillScope]:
    """Assign one or more scopes to a parsed Mantle or coding-agent skill."""
    scopes: list[SkillScope] = []
    if not _is_mantle_agent(project_root):
        return [SkillScope.CODING_AGENT_LOCAL]

    routing = inv.frontmatter.get("routing")
    engine_managed = inv.skill_id == "default_session_start" or (
        isinstance(routing, dict) and bool(routing.get("engine_managed"))
    )
    if engine_managed:
        scopes.append(SkillScope.ENGINE_MANAGED)
    if inv.has_local_tools or inv.has_memory_yml or inv.has_responses_yml:
        scopes.append(SkillScope.SKILL_LOCAL)
    uses_project = bool(inv.import_tools) or any(
        ref.startswith("project.") for ref in inv.memory_refs
    )
    if uses_project:
        scopes.append(SkillScope.PROJECT_GLOBAL)
    if not scopes:
        scopes.append(SkillScope.SKILL_LOCAL)
    return scopes


def tag_skill_dir(skill_dir: Path, project_root: Path | None = None) -> list[SkillScope]:
    """Tag a skill directory using inventory plus Mantle-vs-coding detection."""
    from rasa_skill_eval.rasa_static import inventory_skill

    skill_file = find_skill_file(skill_dir)
    if skill_file is None:
        return []
    inv = inventory_skill(skill_dir, project_root)
    return tag_inventory(inv, project_root)
