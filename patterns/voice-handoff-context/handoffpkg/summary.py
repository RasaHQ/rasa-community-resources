"""Rendering the human-readable summary FROM the structured fields.

This module exists so that the derivation has one implementation and no
alternative. Everything here is a pure function of a
:class:`~handoffpkg.schema.HandoffPackage`: it reads fields and emits text. It
never takes a summary as input, never accepts an override, and there is no code
path anywhere in this pattern by which a human- or model-authored summary can
reach a package.

Why this is worth a module of its own:

    A handoff package that carries both a structured intent and a separately
    authored prose summary carries two sources of truth. They agree on the day
    they are written and diverge on the first edit. The human agent reads the
    prose — it is faster — so the human agent reads the stale one. The failure
    is silent and it is always in the direction of the desk acting on
    information the agent already superseded.

The summary is therefore not "a nice description of the package". It is a
*projection* of the package, in the same sense a formatted date is a projection
of a timestamp.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, typing only
    from handoffpkg.schema import HandoffPackage

_OUTCOME_VERB = {
    "succeeded": "succeeded",
    "failed": "FAILED",
    "blocked": "was blocked",
    "abandoned": "was abandoned",
}

_STAGE_PHRASE = {
    "stated": "had just stated what they wanted",
    "in_progress": "was part-way through",
    "blocked": "was blocked on",
    "abandoned": "gave up on",
}


def _identity_line(package: "HandoffPackage") -> str:
    from handoffpkg.schema import TIER_MEANING

    identity = package.identity
    who = identity.display_name or identity.customer_id or "Unidentified caller"
    tier = identity.verified_tier
    meaning = TIER_MEANING.get(tier, "Unrecognised verification tier — treat as unverified.")
    line = f"{who} — verified at tier '{tier}'. {meaning}"
    if identity.verified_factors:
        line += f" Factors satisfied: {', '.join(identity.verified_factors)}."
    return line


def _intent_line(package: "HandoffPackage") -> str:
    intent = package.intent
    label = intent.goal_label or intent.goal
    phrase = _STAGE_PHRASE.get(intent.stage, "was working on")
    line = f"They {phrase}: {label} ({intent.goal})."
    if intent.details:
        rendered = ", ".join(f"{key}={value}" for key, value in sorted(intent.details.items()))
        line += f" Details: {rendered}."
    return line


def _attempt_lines(package: "HandoffPackage") -> list[str]:
    if not package.attempts:
        return ["  (nothing attempted yet — the caller reached you before the agent tried anything)"]
    lines = []
    for attempt in package.attempts:
        verb = _OUTCOME_VERB.get(attempt.outcome, attempt.outcome)
        text = f"  - {attempt.action} {verb}"
        if attempt.code:
            text += f" [{attempt.code}]"
        if attempt.detail:
            text += f": {attempt.detail}"
        lines.append(text)
    return lines


def _do_not_repeat_lines(package: "HandoffPackage") -> list[str]:
    dnr = package.do_not_repeat
    lines: list[str] = []
    for question in dnr.questions_answered:
        lines.append(f"  - Already answered: {question}")
    for factor in dnr.factors_verified:
        lines.append(f"  - Already verified: {factor} — do not re-run this check")
    for fact in dnr.confirmed_facts:
        lines.append(f"  - Already confirmed: {fact}")
    if not lines:
        lines.append("  (nothing established yet)")
    return lines


def render_summary(package: "HandoffPackage") -> str:
    """Render the desk-facing summary for ``package``.

    Pure and total: same package in, same text out, no I/O, no model call. That
    matters more than the prose quality. A summary produced by an LLM at
    handoff time would be a *sixth* piece of state — unversioned, unreproducible
    and free to contradict the other five. The desk needs the summary to be a
    view, and a view has to be cheap enough to recompute on every read.
    """
    parts: list[str] = []
    parts.append(f"HANDOFF {package.handoff_id} — {package.reason}")
    parts.append("")
    parts.append(f"WHO:    {_identity_line(package)}")
    parts.append(f"WANTS:  {_intent_line(package)}")
    parts.append("")
    parts.append("ALREADY TRIED:")
    parts.extend(_attempt_lines(package))
    parts.append("")
    parts.append("DO NOT ASK AGAIN:")
    parts.extend(_do_not_repeat_lines(package))
    if package.withheld_fields:
        parts.append("")
        parts.append(
            "WITHHELD (present in the session, deliberately not transferred): "
            + ", ".join(package.withheld_fields)
        )
        parts.append(
            "  Do not ask the caller to repeat these. They are withheld by policy, "
            "not missing by accident."
        )
    return "\n".join(parts)
