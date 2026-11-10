"""Output guard: no coverage promise without a coverage decision.

The tools already keep policy state, claim progress and coverage decisions
apart. This hook is the second line: it reads every model response before the
caller sees it. If the text promises or implies cover ("you're covered", "we'll
pay"), the response is discarded and the model is sent back with a correction,
unless the text cites the claim number or decision reference of a coverage
decision a tool returned in this conversation. That exception is narrow on
purpose: a decision on one claim must not leak onto a different loss. After
two consecutive retries the text is replaced with a fixed answer built from
tool data: the recorded decision when one exists, otherwise a referral.

Revision note: the first version (the run recorded in
case-build/results/2026-09-29-gemini-3.1-pro-preview/) fell back to "no
decision has been made" even when a decision was on record, and told the
model no decision existed. Gemini stated the real decision on CLM-24-0913
without citing it, and in three conversations the caller was told the
opposite of the record. The same run exposed the cause: the engine hands
modify_tool_result the tool's serialized JSON string, and the first version
only looked for a dict, so it never saw a decision. Both texts now depend on
what the tools returned, and the result is parsed from JSON.

Each intervention is logged as ``harborcover.coverage_guard`` with the sender
id, so a test harness can count how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict

import structlog

from lib.harborcover import coverage_promises
from rasa.mantle.hooks import (
    ModelResponsePayload,
    RetryModel,
    ToolResultPayload,
    modify_model_response,
    modify_tool_result,
)

log = structlog.get_logger()

MAX_CONSECUTIVE_RETRIES = 2

NO_DECISION_TEXT = (
    "I can't tell you whether that loss is covered. Only the HarborCover claims "
    "service can decide that, and there is no decision on it. I can pass the "
    "question to them and give you a reference. Would you like me to do that?"
)

NO_DECISION_FEEDBACK = (
    "Your draft said or implied that a loss is covered. No tool result in this "
    "conversation contains a coverage decision. Rewrite without saying or "
    "implying cover. Report only recorded status, and offer "
    "open_coverage_question for any question about whether a loss is covered."
)

# Per-conversation state, in process memory: recorded coverage decisions by
# claim number, and consecutive retries.
_decisions: dict[str, dict[str, dict]] = defaultdict(dict)
_retries: dict[str, int] = defaultdict(int)


def _decision_lines(decisions: dict[str, dict]) -> str:
    return "; ".join(
        f"claim {claim}: {d.get('outcome')} (decision {d.get('reference')})"
        for claim, d in sorted(decisions.items())
    )


def decision_feedback(decisions: dict[str, dict]) -> str:
    return (
        "Your draft said or implied that a loss is covered without naming the "
        f"claim the decision belongs to. Recorded decisions: {_decision_lines(decisions)}. "
        "If you are reporting one of these, name its claim number and say it "
        "applies to that claim only. For any other loss, do not say or imply "
        "cover; offer open_coverage_question."
    )


def decision_text(decisions: dict[str, dict]) -> str:
    """Fallback built only from tool data, so it cannot deny a real decision."""
    return (
        f"The HarborCover claims service has recorded this decision: {_decision_lines(decisions)}. "
        "It applies to that claim only. For any other loss I can pass a question "
        "to the claims team and give you a reference."
    )


def _as_dict(value: object) -> dict:
    """The engine passes the tool result as its serialized JSON text, not a dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


@modify_tool_result()
async def remember_coverage_decisions(payload: ToolResultPayload) -> ToolResultPayload:
    value = _as_dict(payload.value)
    decision = value.get("coverage_decision")
    if value.get("decision_type") == "coverage_decision" and isinstance(decision, dict):
        _decisions[payload.sender_id][str(value.get("claim_number")).upper()] = decision
    return payload


@modify_model_response()
async def block_coverage_promises(payload: ModelResponsePayload) -> ModelResponsePayload:
    text = payload.text or ""
    promises = coverage_promises(text)
    decisions = _decisions.get(payload.sender_id, {})
    citations = set(decisions) | {str(d.get("reference")).upper() for d in decisions.values()}
    cited = any(ref in text.upper() for ref in citations)
    if not promises or cited:
        _retries.pop(payload.sender_id, None)
        return payload
    _retries[payload.sender_id] += 1
    attempt = _retries[payload.sender_id]
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning(
            "harborcover.coverage_guard",
            sender_id=payload.sender_id,
            action="replaced",
            decisions_on_record=len(decisions),
            matched=promises[0],
        )
        _retries.pop(payload.sender_id, None)
        fallback = decision_text(decisions) if decisions else NO_DECISION_TEXT
        return payload.model_copy(update={"text": fallback})
    log.warning(
        "harborcover.coverage_guard",
        sender_id=payload.sender_id,
        action="retry",
        attempt=attempt,
        decisions_on_record=len(decisions),
        matched=promises[0],
    )
    raise RetryModel(decision_feedback(decisions) if decisions else NO_DECISION_FEEDBACK)
