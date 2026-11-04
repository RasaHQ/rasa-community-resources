"""Project Mantle skill.md into Agent Skills SKILL.md."""

from __future__ import annotations

from pathlib import Path

from rasa_skill_eval.config import ProjectionSettings
from rasa_skill_eval.projector import (
    FALLBACK_EXAMPLE,
    example_lines_for_skill,
    has_agent_skills_template,
    load_sidecar,
    project_skill,
    sidecar_path,
    wrap_agent_skills_body,
)
from rasa_skill_eval.skill_io import split_frontmatter

FIXTURE = Path(__file__).parent / "fixtures" / "sample_agent"
SETTINGS = ProjectionSettings()


def test_projector_kebabs_name_and_moves_constraints(tmp_path: Path) -> None:
    """Native control YAML is moved out of Agent Skills frontmatter."""
    src = FIXTURE / "skills" / "block_card"
    dest = tmp_path / "block-card"
    sidecar = project_skill(src, dest, SETTINGS)
    assert sidecar.projected_name == "block-card"
    assert "tool_constraints" in sidecar.moved_frontmatter
    assert (dest / "SKILL.md").is_file()
    assert (dest / "config" / "mantle.yml").is_file()
    frontmatter, _body = split_frontmatter((dest / "SKILL.md").read_text(encoding="utf-8"))
    assert frontmatter["name"] == "block-card"
    assert "tool_constraints" not in frontmatter
    assert frontmatter["metadata"]["rasa_skill_id"] == "block_card"
    mantle = (dest / "config" / "mantle.yml").read_text(encoding="utf-8")
    assert "block_card" in mantle
    assert "requires_confirmation" in mantle


def test_projector_copies_local_tools_to_scripts(tmp_path: Path) -> None:
    """Skill-local tools.py becomes scripts/tools.py for NVIDIA lint."""
    src = FIXTURE / "skills" / "check_balance"
    dest = tmp_path / "check-balance"
    project_skill(src, dest, SETTINGS)
    assert (dest / "scripts" / "tools.py").is_file()
    assert (dest / "config" / "memory.yml").is_file()


def test_projector_moves_routing_out_of_frontmatter(tmp_path: Path) -> None:
    """engine_managed routing is Mantle control, not Agent Skills frontmatter."""
    src = FIXTURE / "skills" / "default_session_start"
    dest = tmp_path / "default-session-start"
    sidecar = project_skill(src, dest, SETTINGS)
    assert "routing" in sidecar.moved_frontmatter
    frontmatter, _body = split_frontmatter((dest / "SKILL.md").read_text(encoding="utf-8"))
    assert "routing" not in frontmatter
    assert "engine_managed" in (dest / "config" / "mantle.yml").read_text(encoding="utf-8")


def test_projector_wraps_agent_skills_headings(tmp_path: Path) -> None:
    """Projected SKILL.md gets H1, Instructions, and Examples without inventing tools."""
    src = FIXTURE / "skills" / "block_card"
    dest = tmp_path / "block-card"
    sidecar = project_skill(src, dest, SETTINGS, example_lines=["My card was stolen."])
    text = (dest / "SKILL.md").read_text(encoding="utf-8")
    _frontmatter, body = split_frontmatter(text)
    assert has_agent_skills_template(body)
    assert "# Block Card" in body
    assert "## Instructions" in body
    assert "## Examples" in body
    assert "My card was stolen." in body
    assert "body_headings" in sidecar.rewritten_fields
    assert not (dest / "projection.json").exists()
    assert sidecar_path(dest).is_file()
    loaded = load_sidecar(dest)
    assert loaded is not None
    assert loaded.projected_name == "block-card"


def test_wrap_agent_skills_body_uses_fallback_example() -> None:
    """Missing examples get a non-invented placeholder, not a fake banking dialog."""
    wrapped = wrap_agent_skills_body("Call list_cards then stop.", "Check Balance")
    assert has_agent_skills_template(wrapped)
    assert FALLBACK_EXAMPLE in wrapped
    assert "account 123" not in wrapped.lower()


def test_example_lines_for_skill_reads_first_user_turn(tmp_path: Path) -> None:
    """Matching eval scenarios contribute the first user line as an example."""
    folder = tmp_path / "eval" / "scenarios" / "rasano"
    folder.mkdir(parents=True)
    (folder / "block_card_stolen.yml").write_text(
        "id: block_card_stolen\nskill: block_card\nturns:\n  - user: My card was stolen.\n",
        encoding="utf-8",
    )
    assert example_lines_for_skill(tmp_path, "rasano", "block_card") == [
        "My card was stolen."
    ]


def test_load_sidecar_reads_legacy_projection_json(tmp_path: Path) -> None:
    """Windows donated skills may still keep projection.json inside the skill root."""
    dest = tmp_path / "block-card"
    dest.mkdir()
    (dest / "projection.json").write_text(
        '{"source_skill_id": "block_card", "source_display_name": "Block Card", '
        '"projected_name": "block-card", "source_path": "x", "projected_path": "y"}',
        encoding="utf-8",
    )
    loaded = load_sidecar(dest)
    assert loaded is not None
    assert loaded.source_skill_id == "block_card"
