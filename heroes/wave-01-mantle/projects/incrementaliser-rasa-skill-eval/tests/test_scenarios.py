"""Committed scenarios load with agent routing."""

from __future__ import annotations

from rasa_skill_eval.scenarios import load_scenarios


def test_scenarios_cover_core_paths() -> None:
    """The suite includes balance, transfer refuse, FAQ, and small talk."""
    rows = load_scenarios(agent_id="rasano")
    ids = {row["id"] for row in rows}
    assert "balance_named" in ids
    assert "transfer_refused" in ids
    assert "faq_grounded" in ids
    assert "smalltalk_no_transfer" in ids
    for row in rows:
        assert row.get("agent") == "rasano"
        assert "expect" in row


def test_personalization_scenarios_are_separate() -> None:
    """Personalization scenarios do not mix into Rasano."""
    rasano = {row["id"] for row in load_scenarios(agent_id="rasano")}
    personal = load_scenarios(agent_id="personalization")
    ids = {row["id"] for row in personal}
    assert "session_start_identity" in ids
    assert "view_transactions_usual" in ids
    assert rasano.isdisjoint(ids)
    for row in personal:
        assert row.get("agent") == "personalization"
