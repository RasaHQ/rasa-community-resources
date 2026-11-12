"""Improver must not strip Mantle control YAML from projected copies."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from rasa_skill_eval.config import ProjectionSettings
from rasa_skill_eval.improver import (
    CACHE_SCHEMA,
    assert_constraints_preserved,
    improve_projected_skill,
)
from rasa_skill_eval.llm.types import ChatResult
from rasa_skill_eval.projector import project_skill
from rasa_skill_eval.skill_io import split_frontmatter

AGENT = Path(__file__).parent / "fixtures" / "sample_agent"
SETTINGS = ProjectionSettings()

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
Do not invent card ids.

## Examples

- Customer: My card was stolen.
- Agent: I can block that card after you confirm.

## Limitations

Do not invent accounts, balances, or card facts.

## Error handling

If a tool fails, tell the customer and stop.
"""


class _ScriptedClient:
    """Chat client that returns canned SKILL.md or raises on selected calls."""

    def __init__(self, replies: list[str], fail_on: set[int] | None = None) -> None:
        """Store replies and 1-based call indexes that should raise."""
        self.replies = list(replies)
        self.fail_on = fail_on or set()
        self.calls = 0
        self.messages: list[list[object]] = []

    def complete(
        self,
        messages: list[object],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> ChatResult:
        """Return the next canned reply or raise ``httpx.ReadTimeout``."""
        del max_tokens, temperature, seed
        self.calls += 1
        self.messages.append(list(messages))
        if self.calls in self.fail_on:
            raise httpx.ReadTimeout("The read operation timed out")
        return ChatResult(text=self.replies.pop(0))


def test_improver_preserves_mantle_config(tmp_path: Path) -> None:
    """The improver copy must leave config/mantle.yml byte-identical."""
    src = AGENT / "skills" / "block_card"
    projected = tmp_path / "projected" / "block-card"
    improved = tmp_path / "improved" / "block-card"
    project_skill(src, projected, SETTINGS)
    client = _ScriptedClient([LLM_SKILL_MD])
    delta = improve_projected_skill(projected, improved, SETTINGS, client=client)
    assert delta.constraints_preserved is True
    assert assert_constraints_preserved(projected, improved) is True
    assert (improved / "config" / "mantle.yml").read_text(
        encoding="utf-8"
    ) == (projected / "config" / "mantle.yml").read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter((improved / "SKILL.md").read_text(encoding="utf-8"))
    assert "Error handling" in body
    assert frontmatter["license"] == SETTINGS.license
    assert "author" in frontmatter["metadata"]


def test_llm_rewrite_is_a_single_call(tmp_path: Path) -> None:
    """writing-for-agents and unslop share one complete() per skill."""
    src = AGENT / "skills" / "block_card"
    projected = tmp_path / "projected" / "block-card"
    improved = tmp_path / "improved" / "block-card"
    project_skill(src, projected, SETTINGS)
    unslop_dir = tmp_path / "unslop_rules"
    unslop_dir.mkdir()
    (unslop_dir / "SKILL.md").write_text(
        "---\nname: unslop\n---\nRemove filler.\n",
        encoding="utf-8",
    )
    client = _ScriptedClient([LLM_SKILL_MD])
    delta = improve_projected_skill(
        projected,
        improved,
        SETTINGS,
        client=client,
        unslop_dir=unslop_dir,
    )
    assert delta.mode == "llm"
    assert delta.degraded is False
    assert "llm writing-for-agents rewrite" in delta.changes
    assert "llm unslop in same call" in delta.changes
    assert client.calls == 1
    user_msg = client.messages[0][1]
    user = getattr(user_msg, "content", str(user_msg))
    assert "Remove filler" in str(user)
    assert "Do not invent" in (improved / "SKILL.md").read_text(encoding="utf-8")
    system = getattr(client.messages[0][0], "content", str(client.messages[0][0]))
    assert "## Instructions" in str(system)
    assert "## Examples" in str(system)
    assert "ordered_block" in str(system)
    assert "Done when" in str(system)
    assert "completion criterion on each step" not in str(system)


def test_first_llm_timeout_switches_to_backup_or_marks_degraded(tmp_path: Path) -> None:
    """When the primary LLM times out, backup is tried; if both fail, it's marked degraded."""
    src = AGENT / "skills" / "block_card"
    projected = tmp_path / "projected" / "block-card"
    improved = tmp_path / "improved" / "block-card"
    project_skill(src, projected, SETTINGS)
    client = _ScriptedClient([], fail_on={1})
    backup_client = _ScriptedClient([LLM_SKILL_MD])
    delta = improve_projected_skill(
        projected, improved, SETTINGS, client=client, backup_client=backup_client
    )
    assert delta.mode == "llm"
    assert delta.degraded is False
    assert "rewritten using backup improver model" in delta.changes
    assert (improved / "SKILL.md").is_file()

    # When both fail, mark degraded without heuristic alterations
    improved_fail = tmp_path / "improved_fail" / "block-card"
    failing_backup = _ScriptedClient([], fail_on={1})
    delta_fail = improve_projected_skill(
        projected, improved_fail, SETTINGS, client=client, backup_client=failing_backup
    )
    assert delta_fail.mode == "failed"
    assert delta_fail.degraded is True


def test_improver_cache_skips_second_llm_call(tmp_path: Path) -> None:
    """A matching projected hash reuses the saved SKILL.md and does not call the LLM."""
    src = AGENT / "skills" / "block_card"
    projected = tmp_path / "projected" / "block-card"
    improved = tmp_path / "improved" / "block-card"
    project_skill(src, projected, SETTINGS)
    cache = tmp_path / "cache"
    client = _ScriptedClient([LLM_SKILL_MD, LLM_SKILL_MD])
    first = improve_projected_skill(
        projected,
        improved,
        SETTINGS,
        client=client,
        cache_dir=cache,
        cache_id="rasano/block-card",
        improver_model_id="kimi",
    )
    assert first.mode == "llm"
    assert client.calls == 1
    second = improve_projected_skill(
        projected,
        tmp_path / "improved2" / "block-card",
        SETTINGS,
        client=client,
        cache_dir=cache,
        cache_id="rasano/block-card",
        improver_model_id="kimi",
    )
    assert second.mode == "cached"
    assert client.calls == 1
    assert "cache hit" in second.changes


def test_reimprove_ignores_cache(tmp_path: Path) -> None:
    """``reimprove=True`` calls the LLM even when a cache entry exists."""
    src = AGENT / "skills" / "block_card"
    projected = tmp_path / "projected" / "block-card"
    project_skill(src, projected, SETTINGS)
    cache = tmp_path / "cache"
    client = _ScriptedClient([LLM_SKILL_MD, LLM_SKILL_MD])
    improve_projected_skill(
        projected,
        tmp_path / "improved" / "block-card",
        SETTINGS,
        client=client,
        cache_dir=cache,
        cache_id="rasano/block-card",
        improver_model_id="kimi",
    )
    again = improve_projected_skill(
        projected,
        tmp_path / "improved2" / "block-card",
        SETTINGS,
        client=client,
        cache_dir=cache,
        cache_id="rasano/block-card",
        improver_model_id="kimi",
        reimprove=True,
    )
    assert again.mode == "llm"
    assert client.calls == 2


def test_improver_cache_invalidates_when_prompt_inputs_change(tmp_path: Path) -> None:
    """Changing writing-for-agents rules must not reuse a cached rewrite."""
    src = AGENT / "skills" / "block_card"
    projected = tmp_path / "projected" / "block-card"
    project_skill(src, projected, SETTINGS)
    cache = tmp_path / "cache"
    writing = tmp_path / "writing"
    writing.mkdir()
    (writing / "SKILL.md").write_text("---\nname: w\n---\nRule A.\n", encoding="utf-8")
    client = _ScriptedClient([LLM_SKILL_MD, LLM_SKILL_MD])
    improve_projected_skill(
        projected,
        tmp_path / "improved" / "block-card",
        SETTINGS,
        client=client,
        writing_for_agents_dir=writing,
        cache_dir=cache,
        cache_id="rasano/block-card",
        improver_model_id="kimi",
    )
    (writing / "SKILL.md").write_text("---\nname: w\n---\nRule B.\n", encoding="utf-8")
    again = improve_projected_skill(
        projected,
        tmp_path / "improved2" / "block-card",
        SETTINGS,
        client=client,
        writing_for_agents_dir=writing,
        cache_dir=cache,
        cache_id="rasano/block-card",
        improver_model_id="kimi",
    )
    assert again.mode == "llm"
    assert client.calls == 2


def test_improver_rejects_noop_and_does_not_cache(tmp_path: Path) -> None:
    """A near-paraphrase of the projector skeleton is a failed improve, not a cache hit."""
    src = AGENT / "skills" / "block_card"
    projected = tmp_path / "projected" / "block-card"
    project_skill(src, projected, SETTINGS)
    original = (projected / "SKILL.md").read_text(encoding="utf-8")
    cache = tmp_path / "cache"
    client = _ScriptedClient([original])
    first = improve_projected_skill(
        projected,
        tmp_path / "improved" / "block-card",
        SETTINGS,
        client=client,
        cache_dir=cache,
        cache_id="rasano/block-card",
        improver_model_id="kimi",
    )
    assert first.mode == "failed"
    assert first.degraded is True
    assert not list(cache.rglob("SKILL.md"))


def test_improver_schema_gate_skips_missing_headings(tmp_path: Path) -> None:
    """Missing Agent Skills headings try backup, then succeed when backup is valid."""
    src = AGENT / "skills" / "block_card"
    projected = tmp_path / "projected" / "block-card"
    project_skill(src, projected, SETTINGS)
    bad = "---\nname: Block Card\nlicense: Apache-2.0\n---\nNo headings here.\n"
    client = _ScriptedClient([bad])
    backup = _ScriptedClient([LLM_SKILL_MD])
    delta = improve_projected_skill(
        projected,
        tmp_path / "improved" / "block-card",
        SETTINGS,
        client=client,
        backup_client=backup,
        cache_dir=tmp_path / "cache",
        cache_id="rasano/block-card",
        improver_model_id="kimi",
    )
    assert delta.mode == "llm"
    body = (tmp_path / "improved" / "block-card" / "SKILL.md").read_text(encoding="utf-8")
    assert "# Block Card" in body
    assert "## Instructions" in body
    meta = next((tmp_path / "cache").rglob("meta.json"))
    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["cache_schema"] == CACHE_SCHEMA
    assert payload["schema_ok"] is True
