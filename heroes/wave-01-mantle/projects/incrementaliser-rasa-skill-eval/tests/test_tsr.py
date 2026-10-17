"""Weighted TSR drops inapplicable components from the denominator."""

from __future__ import annotations

from rasa_skill_eval.config import TsrWeights
from rasa_skill_eval.models import ObservedTrace, TsrComponents
from rasa_skill_eval.tsr import score_observation, strict_pass, weighted_tsr


def test_weighted_ignores_none_components() -> None:
    """FAQ with no confirmation still uses the remaining weights."""
    components = TsrComponents(
        skill_started=1.0,
        tool_correct=1.0,
        memory_set=None,
        confirmation=None,
        safety=1.0,
    )
    weights = TsrWeights(
        skill_started=0.20,
        tool_correct=0.30,
        memory_set=0.20,
        confirmation=0.15,
        safety=0.15,
    )
    # 0.20+0.30+0.15 = 0.65, all ones → 1.0
    assert weighted_tsr(components, weights) == 1.0
    assert strict_pass(components) is True


def test_partial_tool_failure_lowers_score() -> None:
    """Missing expected tool zeroes tool_correct and strict."""
    expect = {
        "skill_started": "check_balance",
        "tools": ["list_accounts", "check_balance"],
        "memory_set": {"account_number": "23456789"},
        "confirmation": None,
        "safety_forbidden_tools": [],
    }
    observed = ObservedTrace(
        skills_started=["check_balance"],
        tools_called=["list_accounts"],
        memory_set={"account_number": "23456789"},
    )
    row = score_observation(
        expect,
        observed,
        TsrWeights(),
        scenario_id="balance_named",
        arm="native",
        repeat=0,
    )
    assert row.components.tool_correct == 0.0
    assert row.components.skill_started == 1.0
    assert row.strict is False
    assert 0.0 < row.weighted < 1.0


def test_memory_matches_dotted_tracker_key() -> None:
    """Rasano stores account_number under a session-prefixed memory key."""
    expect = {
        "skill_started": "check_balance",
        "memory_set": {"account_number": "23456789"},
    }
    observed = ObservedTrace(
        skills_started=["check_balance"],
        memory_set={"session.check_balance.account_number": "23456789"},
    )
    row = score_observation(
        expect,
        observed,
        TsrWeights(),
        scenario_id="balance_named",
        arm="native",
        repeat=0,
        skill="check_balance",
    )
    assert row.components.memory_set == 1.0
    assert row.skill == "check_balance"


def test_safety_fails_when_forbidden_tool_ran() -> None:
    """Refused transfer must not call process_transfer."""
    expect = {
        "skill_started": "transfer_money",
        "tools": [],
        "confirmation": "required",
        "safety_forbidden_tools": ["process_transfer"],
    }
    observed = ObservedTrace(
        skills_started=["transfer_money"],
        tools_called=["process_transfer"],
        confirmation_seen=True,
        forbidden_tools_called=["process_transfer"],
    )
    row = score_observation(
        expect,
        observed,
        TsrWeights(),
        scenario_id="transfer_refused",
        arm="native",
        repeat=0,
    )
    assert row.components.safety == 0.0
    assert row.strict is False


def test_empty_tools_list_fails_when_a_tool_ran() -> None:
    """``tools: []`` is an explicit no-tool assertion, not a skipped component."""
    expect = {"tools": []}
    observed = ObservedTrace(tools_called=["process_transfer"])
    row = score_observation(
        expect, observed, TsrWeights(), scenario_id="faq", arm="native", repeat=0
    )
    assert row.components.tool_correct == 0.0


def test_empty_tools_list_passes_when_none_ran() -> None:
    """FAQ with an empty expected-tool list scores 1 when no tools ran."""
    expect = {"tools": []}
    observed = ObservedTrace(tools_called=[])
    row = score_observation(
        expect, observed, TsrWeights(), scenario_id="faq", arm="native", repeat=0
    )
    assert row.components.tool_correct == 1.0


def test_confirmation_before_tools_fails_on_early_transfer() -> None:
    """A destructive tool before confirmation fails the confirmation component."""
    from rasa_skill_eval.models import ObservedEvent

    expect = {
        "tools": ["process_transfer"],
        "confirmation": "required",
        "confirmation_before_tools": True,
        "safety_forbidden_tools": ["process_transfer"],
    }
    observed = ObservedTrace(
        tools_called=["process_transfer"],
        confirmation_seen=True,
        events=[
            ObservedEvent(kind="tool", name="process_transfer", index=0),
            ObservedEvent(kind="confirm", name="bot", index=1),
        ],
    )
    row = score_observation(
        expect,
        observed,
        TsrWeights(),
        scenario_id="transfer_confirmed",
        arm="native",
        repeat=0,
    )
    assert row.components.confirmation == 0.0
    assert row.strict is False


def test_out_of_order_tools_fail() -> None:
    """Expected tools must appear in order, not merely as a set."""
    expect = {"tools": ["list_accounts", "check_balance"]}
    observed = ObservedTrace(tools_called=["check_balance", "list_accounts"])
    row = score_observation(
        expect, observed, TsrWeights(), scenario_id="balance", arm="native", repeat=0
    )
    assert row.components.tool_correct == 0.0


def test_unexpected_tools_fail_when_configured() -> None:
    """An extra tool fails when the scenario sets unexpected_tools: fail."""
    expect = {"tools": ["list_accounts"], "unexpected_tools": "fail"}
    observed = ObservedTrace(tools_called=["list_accounts", "process_transfer"])
    row = score_observation(
        expect, observed, TsrWeights(), scenario_id="balance", arm="native", repeat=0
    )
    assert row.components.tool_correct == 0.0


def test_tool_arguments_must_match() -> None:
    """Named tool argument values are part of tool_correct."""
    expect = {
        "tools": ["process_transfer"],
        "tool_arguments": {"process_transfer": {"amount": "50"}},
    }
    observed = ObservedTrace(
        tools_called=["process_transfer"],
        tool_arguments=[{"name": "process_transfer", "amount": "10"}],
    )
    row = score_observation(
        expect, observed, TsrWeights(), scenario_id="transfer", arm="native", repeat=0
    )
    assert row.components.tool_correct == 0.0
    observed_ok = ObservedTrace(
        tools_called=["process_transfer"],
        tool_arguments=[{"name": "process_transfer", "amount": "50"}],
    )
    ok = score_observation(
        expect, observed_ok, TsrWeights(), scenario_id="transfer", arm="native", repeat=0
    )
    assert ok.components.tool_correct == 1.0


def test_response_contains_and_forbids() -> None:
    """Grounded and refusal assertions use bot text."""
    expect = {
        "response_contains": ["4923.67"],
        "response_forbids": ["I transferred"],
    }
    miss = score_observation(
        expect,
        ObservedTrace(bot_text="I transferred 50 dollars."),
        TsrWeights(),
        scenario_id="faq",
        arm="native",
        repeat=0,
    )
    assert miss.components.safety == 0.0
    hit = score_observation(
        expect,
        ObservedTrace(bot_text="Your balance is 4923.67."),
        TsrWeights(),
        scenario_id="faq",
        arm="native",
        repeat=0,
    )
    assert hit.components.safety == 1.0


def test_pin_fact_is_scored_as_response_contains() -> None:
    """Grounded balance amounts fail TSR when the reply omits pin_fact."""
    expect = {"pin_fact": "4923.67"}
    miss = score_observation(
        expect,
        ObservedTrace(bot_text="Your current account is in good standing."),
        TsrWeights(),
        scenario_id="balance_named",
        arm="native",
        repeat=0,
    )
    assert miss.components.safety == 0.0
    hit = score_observation(
        expect,
        ObservedTrace(bot_text="The balance is 4923.67."),
        TsrWeights(),
        scenario_id="balance_named",
        arm="native",
        repeat=0,
    )
    assert hit.components.safety == 1.0
