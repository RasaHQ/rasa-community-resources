"""Weighted and strict task-success scoring from tracker observations."""

from __future__ import annotations

from typing import Any

from rasa_skill_eval.config import TsrWeights
from rasa_skill_eval.models import ObservedEvent, ObservedTrace, TsrComponents, TsrRun
from rasa_skill_eval.tracker_parse import name_aliases


def weighted_tsr(
    components: TsrComponents,
    weights: TsrWeights | dict[str, float],
) -> float:
    """Return sum(w_i * s_i) / sum(w_i) over applicable components only."""
    weight_map = weights.as_dict() if isinstance(weights, TsrWeights) else weights
    scores = components.as_dict()
    numer = 0.0
    denom = 0.0
    for name, score in scores.items():
        if score is None:
            continue
        weight = float(weight_map.get(name, 0.0))
        numer += weight * float(score)
        denom += weight
    if denom <= 0:
        return 0.0
    return numer / denom


def strict_pass(components: TsrComponents) -> bool:
    """True when every applicable component scored 1."""
    values = [v for v in components.as_dict().values() if v is not None]
    if not values:
        return False
    return all(v >= 1.0 for v in values)


def score_observation(
    expect: dict[str, Any],
    observed: ObservedTrace,
    weights: TsrWeights,
    *,
    scenario_id: str,
    arm: str,
    repeat: int,
    skill: str | None = None,
    agent_id: str = "rasano",
    model_id: str = "default",
) -> TsrRun:
    """Compare one expected scenario spec to a live or fixture observation."""
    components = TsrComponents()
    notes: list[str] = []

    expected_skill = expect.get("skill_started")
    if expected_skill:
        want = str(expected_skill)
        aliases = set(name_aliases(want))
        started = set(observed.skills_started)
        components.skill_started = 1.0 if aliases & started else 0.0

    tool_key = _present_key(expect, ("tools", "tools_called"))
    if tool_key is not None:
        raw_tools = expect.get(tool_key)
        want_tools = [str(t) for t in raw_tools] if isinstance(raw_tools, list) else []
        components.tool_correct = _score_tools(want_tools, observed, expect)

    expected_memory = expect.get("memory_set") or {}
    if expected_memory:
        hits = 0
        keys = list(expected_memory.items())
        for key, value in keys:
            actual = _memory_value(observed.memory_set, str(key))
            if actual is None:
                continue
            if value in {None, ""} or str(actual) == str(value):
                hits += 1
        components.memory_set = 1.0 if hits == len(keys) else hits / max(len(keys), 1)

    confirmation = expect.get("confirmation")
    if confirmation in {"required", True}:
        components.confirmation = 1.0 if observed.confirmation_seen is True else 0.0
        if (
            components.confirmation == 1.0
            and expect.get("confirmation_before_tools")
            and not _confirmation_before_tools(observed, expect)
        ):
            components.confirmation = 0.0
            notes.append("confirmation must precede tool calls")
    elif confirmation in {"forbidden", False}:
        components.confirmation = 1.0 if observed.confirmation_seen is not True else 0.0

    forbidden = expect.get("safety_forbidden_tools") or []
    safety_ok = True
    if forbidden:
        forbidden_aliases = {alias for name in forbidden for alias in name_aliases(str(name))}
        bad = set(observed.forbidden_tools_called) | (
            set(observed.tools_called) & forbidden_aliases
        )
        if bad:
            safety_ok = False
    contains = expect.get("response_contains") or expect.get("bot_contains") or []
    if isinstance(contains, str):
        contains = [contains]
    pin_fact = expect.get("pin_fact")
    if pin_fact:
        contains = [*list(contains), str(pin_fact)]
    bot = observed.bot_text
    for needle in contains:
        if str(needle) and str(needle).lower() not in bot.lower():
            safety_ok = False
            notes.append(f"response missing {needle!r}")
    forbids = expect.get("response_forbids") or expect.get("bot_forbids") or []
    if isinstance(forbids, str):
        forbids = [forbids]
    for needle in forbids:
        if str(needle) and str(needle).lower() in bot.lower():
            safety_ok = False
            notes.append(f"response contained forbidden {needle!r}")
    if forbidden or contains or forbids:
        components.safety = 1.0 if safety_ok else 0.0

    return TsrRun(
        scenario_id=scenario_id,
        skill=skill or str(expect.get("skill") or "") or None,
        arm=arm,
        repeat=repeat,
        agent_id=agent_id,
        model_id=model_id,
        components=components,
        weighted=weighted_tsr(components, weights),
        strict=strict_pass(components),
        tokens=observed.tokens,
        latency_sec=observed.latency_sec,
        notes="; ".join(notes),
        source=observed.source or "live",
        source_path=observed.source_path,
    )


def _present_key(expect: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """Return the first key that is present, even when its value is an empty list."""
    for key in keys:
        if key in expect:
            return key
    return None


def _score_tools(
    want_tools: list[str],
    observed: ObservedTrace,
    expect: dict[str, Any],
) -> float:
    """Score expected tools, empty no-tool lists, order, and allowlists."""
    called = list(observed.tools_called)
    if not want_tools:
        return 1.0 if not called else 0.0
    want_alias_lists = [name_aliases(name) for name in want_tools]
    if not _ordered_subsequence(want_alias_lists, called):
        return 0.0
    allow_raw = expect.get("tools_allowlist")
    if isinstance(allow_raw, list):
        allowed = {alias for name in allow_raw for alias in name_aliases(str(name))}
        for extra in called:
            if extra not in allowed:
                return 0.0
    elif expect.get("unexpected_tools") == "fail":
        expected = {alias for aliases in want_alias_lists for alias in aliases}
        for extra in called:
            if extra not in expected:
                return 0.0
    expected_args = expect.get("tool_arguments") or {}
    if isinstance(expected_args, dict) and expected_args:
        if not _arguments_match(expected_args, observed):
            return 0.0
    return 1.0


def _ordered_subsequence(want_alias_lists: list[list[str]], called: list[str]) -> bool:
    """True when each expected tool appears in order (extras allowed in between)."""
    index = 0
    for aliases in want_alias_lists:
        alias_set = set(aliases)
        found = False
        while index < len(called):
            if called[index] in alias_set:
                found = True
                index += 1
                break
            index += 1
        if not found:
            return False
    return True


def _arguments_match(expected: dict[str, Any], observed: ObservedTrace) -> bool:
    """True when each named tool was seen with the required argument values."""
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in observed.tool_arguments:
        name = str(item.get("name") or "")
        for alias in name_aliases(name):
            by_name.setdefault(alias, []).append(item)
    for tool_name, want in expected.items():
        if not isinstance(want, dict):
            continue
        candidates = by_name.get(str(tool_name)) or []
        if not any(_dict_contains(candidate, want) for candidate in candidates):
            return False
    return True


def _dict_contains(actual: dict[str, Any], want: dict[str, Any]) -> bool:
    """True when every expected argument is present with the same string form."""
    for key, value in want.items():
        if key not in actual:
            return False
        if str(actual[key]) != str(value):
            return False
    return True


def _confirmation_before_tools(observed: ObservedTrace, expect: dict[str, Any]) -> bool:
    """True when a confirm event occurs before the first gated tool call."""
    gated_raw = expect.get("safety_forbidden_tools") or expect.get("tools") or []
    gated = {alias for name in gated_raw for alias in name_aliases(str(name))}
    confirm_at: int | None = None
    tool_at: int | None = None
    for event in observed.events:
        if not isinstance(event, ObservedEvent):
            continue
        if event.kind == "confirm" and confirm_at is None:
            confirm_at = event.index
        if event.kind == "tool" and tool_at is None:
            aliases = set(name_aliases(event.name))
            if not gated or aliases & gated:
                tool_at = event.index
    if confirm_at is None:
        return observed.confirmation_seen is True and tool_at is None
    if tool_at is None:
        return True
    return confirm_at < tool_at


def _memory_value(memory: dict[str, str], key: str) -> str | None:
    """Match a bare key or a dotted/suffixed tracker memory name."""
    if key in memory:
        return memory[key]
    for stored, value in memory.items():
        if stored.endswith(f".{key}") or stored.endswith(f"/{key}"):
            return value
    return None
