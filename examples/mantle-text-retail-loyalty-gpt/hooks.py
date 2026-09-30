"""Output guard: the words cannot invent an entitlement date or a refund.

The tools already make the wrong command impossible to run unconfirmed: no
tool takes a date or an amount, and apply_subscription_change runs only the
change the member was asked about, with the effect the subscription service
computed. This hook is the second line, for the words. It reads every model
response before the member sees it and sends it back when it states a
calendar date or a dollar amount that no tool result in this conversation
carried (``lib.subscriptions.unsupported_figures``): "you'll keep access until
the end of the month", written as a date the service never gave, is the
hidden entitlement loss the case is about.

Clauses that refuse, condition or report the member's own figure are skipped
("I can't pause it until March 1"). After two consecutive retries the text is
replaced with a fixed answer that states no date at all.

Mantle hands ``modify_tool_result`` the tool's result as serialized JSON
text, not a dict (found in the HarborCover policy-status build), so it is
parsed.

Each intervention is logged as ``willowshop.words_guard`` with the sender id,
so the case-build harness counts how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal

import structlog

from lib.subscriptions import ISO_DATE_RE, known_figures, load_data, unsupported_figures
from rasa.mantle.hooks import (
    ModelResponsePayload,
    RetryModel,
    ToolResultPayload,
    modify_model_response,
    modify_tool_result,
)

log = structlog.get_logger()

MAX_CONSECUTIVE_RETRIES = 2
# The `no-words-guard` variant in case-build/conversations.json sets this to False.
ENABLED = True
# A tool behind requires_confirmation reaches this hook as resolve_tool_confirmation,
# which carries the gated tool's result (rasa/mantle/orchestration/orchestrator.py,
# 3.21.0.dev5), so that name is read too.
SERVICE_TOOLS = {"list_subscriptions", "compare_subscription_changes", "select_subscription_change",
                 "apply_subscription_change", "check_change_status", "route_subscription_support",
                 "resolve_tool_confirmation"}

# Today, on the fixture clock, is always a date the member may be told.
_TODAY = {tuple(int(x) for x in m) for m in ISO_DATE_RE.findall(load_data()["as_of"][:10])}

# Per conversation, in process memory: figures seen in tool results, and retries.
_dates: dict[str, set[tuple[int, int, int]]] = defaultdict(lambda: set(_TODAY))
_amounts: dict[str, set[Decimal]] = defaultdict(set)
_retries: dict[str, int] = defaultdict(int)


def _as_value(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def remember(dates: set, amounts: set, value: object) -> None:
    """Record every date and amount a subscription tool returned."""
    found_dates, found_amounts = known_figures(_as_value(value))
    dates |= found_dates
    amounts |= found_amounts


def problems(text: str, dates: set, amounts: set) -> list[str]:
    return unsupported_figures(text, dates, amounts)


def feedback(found: list[str]) -> str:
    return (
        f"Your draft states {'; '.join(found)}, which no subscription-service result in this conversation gave. "
        "Only the subscription service gives effective dates, refunds and entitlements. Rewrite it using only the "
        "dates and amounts in the tool results, or call compare_subscription_changes first."
    )


FALLBACK_TEXT = (
    "Stopping the renewal, pausing and cancelling now each change your subscription differently. I can show you "
    "the exact dates and what you keep for each one from the Willow Shop subscription service before anything "
    "changes. Which subscription is it about?"
)


@modify_tool_result()
async def remember_service_figures(payload: ToolResultPayload) -> ToolResultPayload:
    if payload.tool_name in SERVICE_TOOLS:
        remember(_dates[payload.sender_id], _amounts[payload.sender_id], payload.value)
    return payload


@modify_model_response()
async def block_invented_figures(payload: ModelResponsePayload) -> ModelResponsePayload:
    if not ENABLED:
        return payload
    text = payload.text or ""
    found = problems(text, _dates[payload.sender_id], _amounts[payload.sender_id])
    if not found:
        _retries.pop(payload.sender_id, None)
        return payload
    _retries[payload.sender_id] += 1
    attempt = _retries[payload.sender_id]
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning("willowshop.words_guard", sender_id=payload.sender_id, action="replaced", matched=found[0])
        _retries.pop(payload.sender_id, None)
        return payload.model_copy(update={"text": FALLBACK_TEXT})
    log.warning("willowshop.words_guard", sender_id=payload.sender_id, action="retry", attempt=attempt,
                matched=found[0])
    raise RetryModel(feedback(found))
