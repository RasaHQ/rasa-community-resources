"""Tracker JSON maps onto ObservedTrace fields used by weighted TSR."""

from __future__ import annotations

from rasa_skill_eval.tracker_parse import observation_from_tracker


def test_observation_reads_skill_tool_memory_and_confirm() -> None:
    """Mantle event types are the source of truth, not bot-text heuristics alone."""
    tracker = {
        "events": [
            {"event": "skill_activated", "skill_id": "check_balance"},
            {"event": "flow_started", "flow_id": "check_balance", "skill_id": "check_balance"},
            {"event": "tool_executed", "tool_name": "list_accounts", "arguments": {}},
            {
                "event": "memory_set",
                "key": "session.check_balance.account_number",
                "value": "23456789",
            },
            {"event": "bot", "text": "Your current account balance is 4923.67."},
            {
                "event": "bot",
                "text": "Shall I go ahead and confirm this transfer?",
            },
        ]
    }
    observed = observation_from_tracker(tracker)
    assert "check_balance" in observed.skills_started
    assert "list_accounts" in observed.tools_called
    assert observed.memory_set["session.check_balance.account_number"] == "23456789"
    assert observed.confirmation_seen is True
    assert "4923.67" in observed.bot_text
    assert observed.tool_arguments[0]["name"] == "list_accounts"
    assert observed.events[0].kind == "skill"


def test_action_listen_is_not_a_tool() -> None:
    """Framework actions must not count as banking tools."""
    observed = observation_from_tracker(
        {"events": [{"event": "action", "name": "action_listen"}]}
    )
    assert observed.tools_called == []


def test_observation_tokens_from_metadata() -> None:
    """Provider usage metadata takes precedence for token counts."""
    tracker = {
        "events": [
            {
                "event": "bot",
                "text": "Hello user.",
                "metadata": {"usage": {"prompt_tokens": 10, "completion_tokens": 5}},
            }
        ]
    }
    observed = observation_from_tracker(tracker)
    assert observed.tokens == 15


def test_observation_tokens_fallback_conversational() -> None:
    """Fallback token estimation is computed from dialogue turns when usage metadata is missing."""
    tracker = {
        "events": [
            {"event": "user", "text": "What is my current account balance?"},
            {"event": "bot", "text": "Your current account balance is 4923.67."},
        ]
    }
    observed = observation_from_tracker(tracker)
    assert observed.tokens is not None
    assert observed.tokens > 10
