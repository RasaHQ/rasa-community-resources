"""Native Mantle static inventory and Mantle-only checks."""

from __future__ import annotations

import shutil
from pathlib import Path

from rasa_skill_eval.rasa_static import inventory_skill
from rasa_skill_eval.skill_io import discover_skill_dirs

AGENT = Path(__file__).parent / "fixtures" / "sample_agent"


def test_discovers_fixture_skills() -> None:
    """The sample agent exposes five skill folders."""
    found = discover_skill_dirs(AGENT / "skills")
    ids = {p.name for p in found}
    assert ids == {
        "check_balance",
        "block_card",
        "risky_transfer",
        "add_payee",
        "default_session_start",
    }


def test_block_card_inventory() -> None:
    """block_card records confirmation, an ordered block, and extra keys."""
    inv = inventory_skill(AGENT / "skills" / "block_card", AGENT)
    assert "tool_constraints" in inv.extra_frontmatter_keys
    assert inv.tool_constraints[0].requires_confirmation is True
    assert "pick_card" in inv.ordered_block_ids
    assert inv.irreversible_without_confirmation == []


def test_risky_transfer_missing_confirmation_and_composition() -> None:
    """process_transfer without confirmation is a high Mantle-only finding."""
    inv = inventory_skill(AGENT / "skills" / "risky_transfer", AGENT)
    assert "process_transfer" in inv.irreversible_without_confirmation
    codes = {f.code for f in inv.findings}
    assert "confirmation.missing" in codes
    assert "composition.missing_target" not in codes
    assert "add_payee" in inv.skill_refs


def test_description_trigger_finding() -> None:
    """Risky transfer description lacks when/activate wording."""
    inv = inventory_skill(AGENT / "skills" / "risky_transfer", AGENT)
    assert any(f.code == "description.triggers" for f in inv.findings)


def test_session_start_project_memory_and_voice() -> None:
    """Session start inventories project fields, bare memory writes, and voice."""
    inv = inventory_skill(AGENT / "skills" / "default_session_start", AGENT)
    assert "customer_name" in inv.project_memory_fields
    assert inv.llm_settable_project_fields == []
    assert inv.voice_enabled is True
    assert inv.voice_one_question is True
    assert "routing" in inv.extra_frontmatter_keys
    codes = {f.code for f in inv.findings}
    assert "memory.project_llm_settable" not in codes
    assert "memory.session_start_project_prefix" not in codes
    assert "voice.one_question" not in codes


def test_llm_settable_project_field(tmp_path: Path) -> None:
    """A project field marked llm_settable is a high Mantle-only finding."""
    agent = tmp_path / "agent"
    shutil.copytree(AGENT, agent)
    (agent / "memory.yml").write_text(
        "customer_name:\n  type: text\n  llm_settable: true\n",
        encoding="utf-8",
    )
    inv = inventory_skill(agent / "skills" / "default_session_start", agent)
    assert "customer_name" in inv.llm_settable_project_fields
    assert any(f.code == "memory.project_llm_settable" for f in inv.findings)


def test_session_start_rejects_project_prefix_write(tmp_path: Path) -> None:
    """Writing project.customer_name from session-start tools is invalid Mantle."""
    agent = tmp_path / "agent"
    shutil.copytree(AGENT, agent)
    tools = agent / "skills" / "default_session_start" / "tools.py"
    tools.write_text(
        "def load_customer_profile() -> None:\n"
        '    """Bad write uses a project. prefix."""\n'
        '    memory.set("project.customer_name", "Ada")\n',
        encoding="utf-8",
    )
    inv = inventory_skill(agent / "skills" / "default_session_start", agent)
    assert any(f.code == "memory.session_start_project_prefix" for f in inv.findings)


def test_fixture_llm_uses_model_group() -> None:
    """Mantle 3.20.0.dev6 rejects inline llm.provider. The fixture uses a model group."""
    text = (AGENT / "integrations.yml").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "model_group: orchestrator" in text
    assert "llm:\n  provider:" not in text
