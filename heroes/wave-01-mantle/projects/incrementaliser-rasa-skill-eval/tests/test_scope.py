"""Scope tags for Mantle local/global vs coding-agent skills."""

from __future__ import annotations

from pathlib import Path

from rasa_skill_eval.models import SkillScope
from rasa_skill_eval.rasa_static import inventory_skill
from rasa_skill_eval.scope import tag_inventory, tag_skill_dir

AGENT = Path(__file__).parent / "fixtures" / "sample_agent"
CODING = Path(__file__).parent / "fixtures" / "coding_skill" / "writing-for-agents"


def test_session_start_is_engine_managed() -> None:
    """default_session_start is tagged engine-managed."""
    inv = inventory_skill(AGENT / "skills" / "default_session_start", AGENT)
    scopes = tag_inventory(inv, AGENT)
    assert SkillScope.ENGINE_MANAGED in scopes
    assert SkillScope.SKILL_LOCAL in scopes
    assert SkillScope.PROJECT_GLOBAL in scopes


def test_check_balance_is_skill_local_and_project_global() -> None:
    """Local tools.py plus import_tools means both local and project-global."""
    inv = inventory_skill(AGENT / "skills" / "check_balance", AGENT)
    scopes = tag_inventory(inv, AGENT)
    assert SkillScope.SKILL_LOCAL in scopes
    assert SkillScope.PROJECT_GLOBAL in scopes


def test_coding_skill_is_not_mantle() -> None:
    """A SKILL.md tree without agent.yml is a coding-agent skill."""
    scopes = tag_skill_dir(CODING, project_root=CODING.parent)
    assert SkillScope.CODING_AGENT_LOCAL in scopes
    assert SkillScope.ENGINE_MANAGED not in scopes
