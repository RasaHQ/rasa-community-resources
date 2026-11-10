"""Output guard: no active-cover wording and no policy number without a receipt.

The tools already keep estimate, offer and bound policy apart: only a bind
with a verified receipt returns a policy number. This hook is the second line,
for the words, because the case's failure is a sentence: the agent described
an estimate as active cover. It reads every model response before the customer
sees it. The response is discarded and the model sent back with a correction
when it

- says or implies cover is active or a policy is bound
  (``lib.quotes.active_cover_claims``) and does not name the policy number of
  a verified bind receipt from this conversation, or
- names a policy number that no verified receipt in this conversation holds.

After two consecutive retries the text is replaced with a fixed answer built
from tool data (the receipt, a pending bind or the current offer).

Mantle hands ``modify_tool_result`` the tool's result as serialized JSON text,
not a dict (found in the HarborCover policy-status build), so it is parsed.

Revision note: the first version only listened for ``bind_offer``. A
confirmed ``bind_offer`` reaches the hook as ``resolve_tool_confirmation``, so
in the estimate run (case-build/results/estimate/) the hook never saw the
receipt, refused the model's correct answer twice for naming an "unverified"
policy number, and replaced it with "Nothing is bound": the customer heard
the opposite of the receipt. Bind results are now recognised by content.
The hook does not see the ``rephrased`` messages Mantle generates after
``complete_skill`` (same build), so it is not a complete output filter.

Each intervention is logged as ``harborcover.bind_guard`` with the sender id,
so the case-build harness can count how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict

import structlog

from lib.quotes import active_cover_claims, policy_references
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
    "Your draft said or implied that the customer is covered or that a policy is "
    "active or bound, or it gave a policy number, without a verified bind receipt "
    "to back it. {state} Rewrite it: an estimate is a price range, an offer is not "
    "cover, and only a succeeded bind_offer result has a policy number. If a bind "
    "succeeded, name its policy number."
)

# Per-conversation state, in process memory: verified receipts by policy
# number, the last pending bind and the last offer, and consecutive retries.
_receipts: dict[str, dict[str, dict]] = defaultdict(dict)
_pending: dict[str, dict] = {}
_offers: dict[str, dict] = {}
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


def state_line(sender: str) -> str:
    receipts = _receipts.get(sender) or {}
    if receipts:
        return "Verified bind receipts in this conversation: " + "; ".join(
            f"policy {p} from offer {r.get('offer_id')}, cover from {r.get('effective_from')}"
            for p, r in sorted(receipts.items())
        ) + "."
    if sender in _pending:
        return f"The bind of offer {_pending[sender].get('offer_id')} has no receipt: it is not bound."
    return "No bind has succeeded in this conversation."


def fallback_text(sender: str) -> str:
    """Built only from tool data, so it cannot claim more than the services hold."""
    receipts = _receipts.get(sender) or {}
    if receipts:
        policy, receipt = sorted(receipts.items())[-1]
        return (
            f"The HarborCover binding service confirmed policy {policy}, bound from offer "
            f"{receipt.get('offer_id')}, with cover from {receipt.get('effective_from')}."
        )
    if sender in _pending:
        return (
            f"Offer {_pending[sender].get('offer_id')} is not bound yet: the binding service "
            "has not returned a receipt, so it is not active cover and there is no policy number."
        )
    offer = _offers.get(sender)
    if offer:
        return (
            f"Offer {offer.get('offer_id')} is an underwritten offer, not active cover. Nothing "
            "is bound until the HarborCover binding service returns a policy number."
        )
    return (
        "No HarborCover policy is bound in this conversation. An estimate or an offer is not "
        "active cover."
    )


@modify_tool_result()
async def remember_bind_state(payload: ToolResultPayload) -> ToolResultPayload:
    value = _as_dict(payload.value)
    sender = payload.sender_id
    # A gated tool's confirmed run never reaches this hook under its own name:
    # Mantle runs it inside resolve_tool_confirmation and hands the hook that
    # name with the tool's result (rasa/mantle/orchestration/tool_execution/
    # constraints.py, _record_confirmation_tool_event, 3.21.0.dev5). A bind
    # result is therefore recognised by its content too.
    is_bind_result = payload.tool_name in ("bind_offer", "check_bind_status") or (
        payload.tool_name == "resolve_tool_confirmation" and "offer_id" in value and "policy_number" in value
    )
    if is_bind_result:
        if value.get("status") == "succeeded" and value.get("policy_number"):
            _receipts[sender][str(value["policy_number"]).upper()] = value
            _pending.pop(sender, None)
        elif value.get("status") == "pending":
            _pending[sender] = value
    elif payload.tool_name == "request_underwritten_offer" and value.get("status") == "offered":
        _offers[sender] = value
    return payload


def violations(sender: str, text: str) -> list[str]:
    receipts = _receipts.get(sender) or {}
    named = set(policy_references(text))
    invented = sorted(named - set(receipts))
    found = [f"unverified policy number {p}" for p in invented]
    claims = active_cover_claims(text)
    if claims and not (named & set(receipts)):
        found.extend(claims)
    return found


@modify_model_response()
async def block_unbound_cover_claims(payload: ModelResponsePayload) -> ModelResponsePayload:
    sender = payload.sender_id
    found = violations(sender, payload.text or "")
    if not found:
        _retries.pop(sender, None)
        return payload
    _retries[sender] += 1
    attempt = _retries[sender]
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning("harborcover.bind_guard", sender_id=sender, action="replaced",
                    receipts=len(_receipts.get(sender) or {}), matched=found[0])
        _retries.pop(sender, None)
        return payload.model_copy(update={"text": fallback_text(sender)})
    log.warning("harborcover.bind_guard", sender_id=sender, action="retry", attempt=attempt,
                receipts=len(_receipts.get(sender) or {}), matched=found[0])
    raise RetryModel(FEEDBACK.format(state=state_line(sender)))
