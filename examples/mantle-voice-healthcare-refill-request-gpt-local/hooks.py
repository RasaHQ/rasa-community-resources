"""Output guard: a refill request is never described as an approval.

The tools already make approval impossible: no tool approves, renews or takes
a dose, and every receipt says ``approved: None``. This hook is the second
line, for the words. It reads every model response before the caller hears
it. If the text says or implies that a prescription is approved, renewed,
refilled, on its way or ready, or tells the caller how to change a dose
(``lib.refills.approval_claims``), the response is discarded and the model is
sent back with a correction. After two consecutive retries the text is
replaced with a fixed answer built from tool data: the request reference and
its review status when a request is on record, otherwise a statement of what
the line can do.

Mantle hands ``modify_tool_result`` the tool's result as serialized JSON
text, not a dict (found in the HarborCover case build), so it is parsed.

Each intervention is logged as ``cedar.refill_guard`` with the sender id, so
the case-build harness can count how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict

import structlog

from lib.refills import approval_claims
from rasa.mantle.hooks import (
    ModelResponsePayload,
    RetryModel,
    ToolResultPayload,
    modify_model_response,
    modify_tool_result,
)

log = structlog.get_logger()

MAX_CONSECUTIVE_RETRIES = 2

FEEDBACK = (
    "Your draft said or implied that a prescription is approved, renewed, refilled, prescribed, "
    "on its way or ready, or told the caller how to take or change a dose. None of that is true: "
    "the only thing on record is a request awaiting prescribing team review. Rewrite it as a "
    "request, give the spoken_reference if there is one, and route any dose question with "
    "route_clinical_question. Give no dose advice."
)

NO_REQUEST_TEXT = (
    "I can't approve, renew or change a prescription. I can send a refill request for a medicine "
    "on your record to the Cedar Clinic prescribing team, or pass a question to them."
)

# Per-conversation state, in process memory: request receipts, and consecutive retries.
_receipts: dict[str, dict] = {}
_retries: dict[str, int] = defaultdict(int)


def _as_dict(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def fallback_text(receipt: dict | None) -> str:
    """Built only from tool data, so it cannot claim more than the record holds."""
    if receipt and receipt.get("spoken_reference"):
        return (
            f"Your refill request, reference {receipt['spoken_reference']}, is awaiting prescribing "
            "team review. It is a request, not an approval, and the prescribing team decides."
        )
    if receipt:
        return (
            "Your refill request is not confirmed yet, and nothing has been approved. "
            f"Please contact {receipt.get('contact_route') or 'the Cedar Clinic prescription desk'}."
        )
    return NO_REQUEST_TEXT


@modify_tool_result()
async def remember_receipts(payload: ToolResultPayload) -> ToolResultPayload:
    if payload.tool_name in ("send_refill_request", "check_request_status"):
        value = _as_dict(payload.value)
        if value.get("status") in ("succeeded", "pending", "recorded", "unknown"):
            previous = _receipts.get(payload.sender_id, {})
            _receipts[payload.sender_id] = {**previous, **{k: v for k, v in value.items() if v is not None}}
    return payload


@modify_model_response()
async def block_approval_language(payload: ModelResponsePayload) -> ModelResponsePayload:
    claims = approval_claims(payload.text or "")
    if not claims:
        _retries.pop(payload.sender_id, None)
        return payload
    _retries[payload.sender_id] += 1
    attempt = _retries[payload.sender_id]
    receipt = _receipts.get(payload.sender_id)
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning("cedar.refill_guard", sender_id=payload.sender_id, action="replaced", matched=claims[0])
        _retries.pop(payload.sender_id, None)
        return payload.model_copy(update={"text": fallback_text(receipt)})
    log.warning("cedar.refill_guard", sender_id=payload.sender_id, action="retry", attempt=attempt,
                matched=claims[0])
    raise RetryModel(FEEDBACK)
