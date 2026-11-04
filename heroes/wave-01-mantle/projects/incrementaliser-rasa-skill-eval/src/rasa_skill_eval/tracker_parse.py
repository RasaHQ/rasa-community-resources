"""Turn a Rasa tracker JSON payload into an ``ObservedTrace`` for TSR."""

from __future__ import annotations

import re
from typing import Any

from rasa_skill_eval.models import ObservedEvent, ObservedTrace

SKIP_ACTIONS = frozenset(
    {
        "action_listen",
        "action_session_start",
        "action_restart",
        "action_default_fallback",
        "action_unlikely_intent",
        "action_back",
        "action_deactivate_loop",
    }
)

_CONFIRM_RE = re.compile(
    r"\b(confirm|confirmation|are you sure|shall i|is that (correct|right|okay|ok)|"
    r"do you want me to|yes or no)\b",
    re.IGNORECASE,
)


def name_aliases(name: str) -> list[str]:
    """Return underscore and kebab forms so scenario ids match tracker ids."""
    raw = name.strip()
    if not raw:
        return []
    return list(dict.fromkeys([raw, raw.replace("-", "_"), raw.replace("_", "-")]))


def observation_from_tracker(tracker: dict[str, Any]) -> ObservedTrace:
    """Parse skill, tool, memory, and confirmation signals from tracker events."""
    events = tracker.get("events")
    if not isinstance(events, list):
        events = []
    skills: list[str] = []
    tools: list[str] = []
    tool_arguments: list[dict[str, Any]] = []
    memory: dict[str, str] = {}
    user_parts: list[str] = []
    bot_parts: list[str] = []
    ordered: list[ObservedEvent] = []
    confirmation = False
    tokens = 0

    for raw in events:
        if not isinstance(raw, dict):
            continue
        etype = str(raw.get("event") or "")
        index = len(ordered)
        confirmation = confirmation or _event_is_confirmation(raw)
        tokens += _event_tokens(raw)

        if etype == "user":
            text = str(raw.get("text") or "")
            if text:
                user_parts.append(text)
        elif etype == "skill_activated":
            skill = str(raw.get("skill_id") or "")
            skills.extend(name_aliases(skill))
            ordered.append(ObservedEvent(kind="skill", name=skill, index=index))
        elif etype == "flow_started":
            skill = str(raw.get("skill_id") or raw.get("flow_id") or "")
            skills.extend(name_aliases(skill))
            ordered.append(ObservedEvent(kind="skill", name=skill, index=index))
        elif etype in {"tool_executed", "mcp_tool_executed"}:
            tool = str(raw.get("tool_name") or "")
            args = _tool_arguments(raw)
            tools.extend(name_aliases(tool))
            tool_arguments.append({"name": tool, **args})
            ordered.append(
                ObservedEvent(kind="tool", name=tool, index=index, arguments=args)
            )
        elif etype == "action":
            action = str(raw.get("name") or raw.get("action_name") or "")
            if action and action not in SKIP_ACTIONS and not action.startswith("utter_"):
                args = _tool_arguments(raw)
                tools.extend(name_aliases(action))
                tool_arguments.append({"name": action, **args})
                ordered.append(
                    ObservedEvent(kind="tool", name=action, index=index, arguments=args)
                )
        elif etype == "memory_set":
            key = str(raw.get("key") or "")
            if key:
                memory[key] = "" if raw.get("value") is None else str(raw.get("value"))
        elif etype == "slot":
            key = str(raw.get("name") or raw.get("key") or "")
            if key:
                memory[key] = "" if raw.get("value") is None else str(raw.get("value"))
        elif etype == "bot":
            text = str(raw.get("text") or "")
            if text:
                bot_parts.append(text)
                if _CONFIRM_RE.search(text):
                    confirmation = True
                    ordered.append(ObservedEvent(kind="confirm", name="bot", index=index))
                else:
                    ordered.append(ObservedEvent(kind="bot", name="", index=index))
        if _event_is_confirmation(raw) and etype not in {"bot"}:
            confirm_name = str(
                raw.get("flow_id") or raw.get("skill_id") or raw.get("name") or ""
            )
            ordered.append(ObservedEvent(kind="confirm", name=confirm_name, index=index))

    slots = tracker.get("slots")
    if isinstance(slots, dict):
        for key, value in slots.items():
            if value is None or str(key) in memory:
                continue
            memory[str(key)] = str(value)

    final_tokens: int | None = tokens if tokens > 0 else None
    if final_tokens is None:
        estimated = estimate_conversational_tokens(user_parts, bot_parts)
        if estimated > 0:
            final_tokens = estimated

    return ObservedTrace(
        skills_started=_unique(skills),
        tools_called=_unique(tools),
        memory_set=memory,
        confirmation_seen=confirmation,
        forbidden_tools_called=[],
        bot_text="\n".join(bot_parts),
        tokens=final_tokens,
        events=ordered,
        tool_arguments=tool_arguments,
    )


def estimate_conversational_tokens(user_texts: list[str], bot_texts: list[str]) -> int:
    """Estimate token count from user and bot dialogue when provider usage is absent."""
    combined = " ".join(user_texts + bot_texts).strip()
    if not combined:
        return 0
    words = len(combined.split())
    return max(1, int(round(words * 1.33)))


def _tool_arguments(event: dict[str, Any]) -> dict[str, Any]:
    """Pull a JSON-object argument map from a tool or action event."""
    for key in ("arguments", "args", "tool_arguments", "params"):
        raw = event.get(key)
        if isinstance(raw, dict):
            return dict(raw)
    return {}


def _event_is_confirmation(event: dict[str, Any]) -> bool:
    """True when a flow or skill name looks like a confirmation prompt."""
    for key in ("flow_id", "skill_id", "name"):
        value = str(event.get(key) or "").lower()
        if "confirm" in value:
            return True
    return False


def _event_tokens(event: dict[str, Any]) -> int:
    """Sum provider token counts attached to an event when present."""
    meta = event.get("metadata")
    if not isinstance(meta, dict):
        return 0
    usage = meta.get("usage") if isinstance(meta.get("usage"), dict) else meta
    prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    completion = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    total = usage.get("total_tokens")
    if isinstance(total, (int, float)):
        return int(total)
    n = 0
    if isinstance(prompt, (int, float)):
        n += int(prompt)
    if isinstance(completion, (int, float)):
        n += int(completion)
    return n


def _unique(values: list[str]) -> list[str]:
    """Preserve order while dropping empties and duplicates."""
    return list(dict.fromkeys(v for v in values if v))
