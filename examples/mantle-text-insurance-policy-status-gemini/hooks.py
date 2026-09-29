"""Output guard: no coverage promise without a coverage decision.

The tools already keep policy state, claim progress and coverage decisions
apart. This hook is the second line: it reads every model response before the
caller sees it. If the text promises or implies cover ("you're covered", "we'll
pay"), the response is discarded and the model is sent back with a correction,
unless the text cites the claim number or decision reference of a coverage
decision a tool returned in this conversation. That exception is narrow on
purpose: a decision on one claim must not leak onto a different loss. After
two consecutive retries the text is replaced with a fixed, safe answer.

Each intervention is logged as ``harborcover.coverage_guard`` with the sender
id, so a test harness can count how often the model tried.
"""

from __future__ import annotations

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

SAFE_TEXT = (
    "I can't tell you whether that loss is covered. Only the HarborCover claims "
    "service can decide that, and no decision has been made. I can pass the "
    "question to them and give you a reference. Would you like me to do that?"
)

RETRY_FEEDBACK = (
    "Your draft said or implied that a loss is covered. No tool result in this "
    "conversation contains a coverage decision for it. Rewrite without saying "
    "or implying cover. Report only recorded status, and offer "
    "open_coverage_question for any question about whether a loss is covered. "
    "If you are reporting a recorded coverage decision, name its claim number "
    "or decision reference and say it applies to that claim only."
)

# Per-conversation state, in process memory: the claim numbers and decision
# references of recorded coverage decisions, and consecutive retries.
_decisions: dict[str, set[str]] = defaultdict(set)
_retries: dict[str, int] = defaultdict(int)


@modify_tool_result()
async def remember_coverage_decisions(payload: ToolResultPayload) -> ToolResultPayload:
    value = payload.value if isinstance(payload.value, dict) else {}
    if value.get("decision_type") == "coverage_decision" and value.get("coverage_decision"):
        _decisions[payload.sender_id].add(str(value.get("claim_number")).upper())
        _decisions[payload.sender_id].add(str(value["coverage_decision"].get("reference")).upper())
    return payload


@modify_model_response()
async def block_coverage_promises(payload: ModelResponsePayload) -> ModelResponsePayload:
    text = payload.text or ""
    promises = coverage_promises(text)
    cited = any(ref in text.upper() for ref in _decisions.get(payload.sender_id, ()))
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
            matched=promises[0],
        )
        _retries.pop(payload.sender_id, None)
        return payload.model_copy(update={"text": SAFE_TEXT})
    log.warning(
        "harborcover.coverage_guard",
        sender_id=payload.sender_id,
        action="retry",
        attempt=attempt,
        matched=promises[0],
    )
    raise RetryModel(RETRY_FEEDBACK)
