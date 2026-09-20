"""Reverse-merge keeps Mantle frontmatter and swaps prose."""

from __future__ import annotations

from pathlib import Path

from rasa_skill_eval.config import ProjectionSettings
from rasa_skill_eval.improver import improve_projected_skill
from rasa_skill_eval.llm.types import ChatResult
from rasa_skill_eval.projector import project_skill
from rasa_skill_eval.remerge import (
    AGENT_SKILLS_HEADING_ASK,
    UNKNOWN_STEP_ASK,
    apply_session_prose_workaround,
    apply_unknown_step_workaround,
    remerge_prose,
    rewrite_session_prose,
    strip_unknown_step_keys,
)
from rasa_skill_eval.skill_io import split_frontmatter

AGENT = Path(__file__).parent / "fixtures" / "sample_agent"

LLM_SKILL_MD = """---
name: Block Card
description: Help block a lost or stolen card. Activate for lost card or fraud.
license: Apache-2.0
metadata:
  author: testdoc
---

# Block Card

## Instructions

1. Look up the customer's cards with list_cards. Done when a card id is returned.
2. Ask which card to block. Done when the customer names one card.
3. Call block_card after confirmation. Done when the tool succeeds.

## Examples

- Customer: My card was stolen.

## Limitations

Do not invent accounts, balances, or card facts.

## Error handling

If a tool fails, tell the customer and stop.
"""


class _ScriptedClient:
    """Chat client that returns canned SKILL.md or raises on selected calls."""

    def __init__(self, replies: list[str]) -> None:
        """Store replies."""
        self.replies = list(replies)

    def complete(self, messages: list[object], **_kwargs: object) -> ChatResult:
        """Return the next canned reply."""
        return ChatResult(text=self.replies.pop(0))


def test_remerge_keeps_confirmation(tmp_path: Path) -> None:
    """Native tool_constraints survive after taking improved SKILL.md prose."""
    src = AGENT / "skills" / "block_card"
    projected = tmp_path / "projected" / "block-card"
    improved = tmp_path / "improved" / "block-card"
    native_copy = tmp_path / "native" / "block_card"
    native_copy.mkdir(parents=True)
    (native_copy / "skill.md").write_text(
        (src / "skill.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    project_skill(src, projected, ProjectionSettings())
    client = _ScriptedClient([LLM_SKILL_MD])
    improve_projected_skill(projected, improved, ProjectionSettings(), client=client)
    target = remerge_prose(native_copy, improved)
    frontmatter, body = split_frontmatter(target.read_text(encoding="utf-8"))
    assert "tool_constraints" in frontmatter
    assert "Error handling" in body
    assert "# Block Card" in body
    assert "## Instructions" in body
    assert "## Examples" in body
    constraints = frontmatter["tool_constraints"]
    assert isinstance(constraints, list)
    assert "Report this to Rasa" in AGENT_SKILLS_HEADING_ASK


def test_rewrite_session_prose_leaves_if_lines() -> None:
    """Only instruction prose is rewritten; ``if:`` keeps ``session.*``."""
    body = (
        "Tell the customer session.check_balance.account_number.\n"
        "if: session.check_balance.account_number\n"
        "Call check_balance.\n"
        "Greet @memory.session.customer_name.\n"
    )
    rewritten, count = rewrite_session_prose(body)
    assert count == 1
    assert "Tell the customer @memory.session.check_balance.account_number." in rewritten
    assert "if: session.check_balance.account_number" in rewritten
    assert "Greet @memory.session.customer_name." in rewritten


def test_apply_session_prose_workaround_on_poisoned_skill(tmp_path: Path) -> None:
    """A reverse-merged skill with session keys in prose becomes train-safe."""
    skill_dir = tmp_path / "skills" / "check_balance"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_text(
        "---\nname: Check Balance\n---\n"
        "Read session.check_balance.account_number aloud.\n"
        "if: session.check_balance.account_number\n"
        "Call check_balance.\n",
        encoding="utf-8",
    )
    n = apply_session_prose_workaround(tmp_path)
    assert n == 1
    text = (skill_dir / "skill.md").read_text(encoding="utf-8")
    assert "@memory.session.check_balance.account_number" in text
    assert "if: session.check_balance.account_number" in text


def test_strip_unknown_step_keys_drops_done_when() -> None:
    """Improver ``done_when`` is not a Mantle ExecuteStep field."""
    body = (
        "# Session Start\n\n## Instructions\n\n"
        ":::ordered_block id=main\n"
        "name: default_session_start\n"
        "steps:\n"
        "  - id: load_profile\n"
        "    execute_tool: load_customer_profile\n"
        "    done_when: The customer profile is loaded into project memory.\n"
        "  - id: greet\n"
        "    action: utter_greet\n"
        "    complete_when: session.block_card.selected_card_id\n"
        ":::\n"
    )
    rewritten, count = strip_unknown_step_keys(body)
    assert count == 1
    assert "done_when" not in rewritten
    assert "execute_tool: load_customer_profile" in rewritten
    assert "complete_when: session.block_card.selected_card_id" in rewritten


def test_remerge_strips_done_when_from_native_skill(tmp_path: Path) -> None:
    """Reverse-merge sanitizes Mantle skill.md and leaves the projected copy intact."""
    native = tmp_path / "native" / "default_session_start"
    native.mkdir(parents=True)
    (native / "skill.md").write_text(
        "---\nname: Session Start\nimport_tools:\n  - load_customer_profile\n---\n"
        ":::ordered_block id=main\n"
        "steps:\n"
        "  - id: load_profile\n"
        "    execute_tool: load_customer_profile\n"
        ":::\n",
        encoding="utf-8",
    )
    improved = tmp_path / "improved" / "default-session-start"
    improved.mkdir(parents=True)
    (improved / "SKILL.md").write_text(
        "---\nname: default-session-start\ndescription: Load then greet.\n---\n"
        "# Session Start\n\n## Instructions\n\n"
        ":::ordered_block id=main\n"
        "steps:\n"
        "  - id: load_profile\n"
        "    execute_tool: load_customer_profile\n"
        "    done_when: Profile loaded.\n"
        ":::\n\n## Examples\n\n- Customer: /session_start\n",
        encoding="utf-8",
    )
    target = remerge_prose(native, improved)
    text = target.read_text(encoding="utf-8")
    assert "done_when" not in text
    assert "execute_tool: load_customer_profile" in text
    assert "import_tools" in text
    assert "done_when: Profile loaded." in (improved / "SKILL.md").read_text(encoding="utf-8")


def test_apply_unknown_step_workaround_on_poisoned_skill(tmp_path: Path) -> None:
    """A reverse-merged skill with ``done_when`` becomes train-safe."""
    skill_dir = tmp_path / "skills" / "default_session_start"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_text(
        "---\nname: Session Start\n---\n"
        ":::ordered_block id=main\n"
        "steps:\n"
        "  - id: load_profile\n"
        "    execute_tool: load_customer_profile\n"
        "    done_when: The profile is loaded.\n"
        ":::\n",
        encoding="utf-8",
    )
    n = apply_unknown_step_workaround(tmp_path)
    assert n == 1
    text = (skill_dir / "skill.md").read_text(encoding="utf-8")
    assert "done_when" not in text
    assert UNKNOWN_STEP_ASK.startswith("Reverse-merged")
