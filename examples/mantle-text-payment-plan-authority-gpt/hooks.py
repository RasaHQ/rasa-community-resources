"""Output guard: the words cannot make an offer the billing service did not.

The tools already make it impossible to record other terms: no tool takes an
amount, a number of payments or a date, and accept_plan_offer copies the
terms from the billing service. This hook is the second line, for the words.
It reads every model response before the customer sees it and sends it back
when it:

- puts forward an instalment amount no authorized offer in this conversation
  carries ("I can do $100 a month for you"; ``lib.plans.unauthorized_instalments``);
- says the account is resolved, settled or up to date (``resolved_claims``);
- promises relief the hardship team has not decided (``relief_promises``).

After two consecutive retries the text is replaced with a fixed answer built
from tool data. Authorized amounts are the ones the billing tools returned
in this conversation, current or expired: repeating a real offer is not
inventing one.

Mantle hands ``modify_tool_result`` the tool's result as serialized JSON
text, not a dict (found in the HarborCover policy-status build), so it is
parsed.

Each intervention is logged as ``ambergrid.words_guard`` with the sender id,
so the case-build harness counts how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal

import structlog

from lib.plans import relief_promises, resolved_claims, to_money, unauthorized_instalments
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
BILLING_TOOLS = {"get_plan_offers", "select_plan_offer", "refresh_plan_offer", "accept_plan_offer"}

# Per conversation, in process memory: authorized offers seen, and retries.
_offers: dict[str, dict[str, dict]] = defaultdict(dict)
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


def remember(offers: dict[str, dict], value: dict) -> None:
    """Record every authorized offer a billing tool returned, keyed by offer tag."""
    views = list(value.get("offers") or []) + list(value.get("expired_offers") or [])
    if value.get("status") == "selected":
        views.append(value)
    if value.get("status") == "succeeded" and value.get("recorded_terms"):
        views.append({**value["recorded_terms"], "offer_tag": value.get("offer_tag")})
    for view in views:
        tag = view.get("offer_tag")
        if tag and view.get("instalment_usd"):
            offers[tag] = {k: view.get(k) for k in ("instalments", "instalment_usd", "first_due", "total_usd")}


def authorized_amounts(offers: dict[str, dict]) -> set[Decimal]:
    return {a for a in (to_money(o.get("instalment_usd")) for o in offers.values()) if a is not None}


def problems(text: str, offers: dict[str, dict]) -> list[str]:
    found = [f"unauthorized instalment {hit}" for hit in unauthorized_instalments(text, authorized_amounts(offers))]
    found += [f"says the account is resolved: {hit!r}" for hit in resolved_claims(text)]
    found += [f"promises relief: {hit!r}" for hit in relief_promises(text)]
    return found


def offers_line(offers: dict[str, dict]) -> str:
    return "; ".join(
        f"{tag}: {o['instalments']} monthly payments of ${o['instalment_usd']} from {o['first_due']}"
        for tag, o in sorted(offers.items())
    )


def feedback(found: list[str], offers: dict[str, dict]) -> str:
    authorized = offers_line(offers) or "none has been read in this conversation"
    return (
        f"Your draft {'; '.join(found)}. Only the billing service sets a plan's terms, a plan never resolves the "
        f"account, and the hardship team decides any relief. Authorized offers: {authorized}. Rewrite it: present "
        "only these terms, say the account stays in arrears until the payments are made, and promise no relief."
    )


def fallback_text(offers: dict[str, dict]) -> str:
    """Built only from tool data, so it cannot offer more than the billing service did."""
    if not offers:
        return ("I can only offer payment plans the Amber Grid billing service has authorized for your account. "
                "If none of them is affordable, I can refer you to our hardship team.")
    return ("These are the payment plans the Amber Grid billing service has authorized: "
            f"{offers_line(offers)}. I can't offer other terms. If none of them is affordable, I can refer you to "
            "our hardship team, who decide what support is possible.")


@modify_tool_result()
async def remember_authorized_offers(payload: ToolResultPayload) -> ToolResultPayload:
    if payload.tool_name in BILLING_TOOLS:
        remember(_offers[payload.sender_id], _as_dict(payload.value))
    return payload


@modify_model_response()
async def block_unauthorized_words(payload: ModelResponsePayload) -> ModelResponsePayload:
    if not ENABLED:
        return payload
    text = payload.text or ""
    offers = _offers.get(payload.sender_id, {})
    found = problems(text, offers)
    if not found:
        _retries.pop(payload.sender_id, None)
        return payload
    _retries[payload.sender_id] += 1
    attempt = _retries[payload.sender_id]
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning("ambergrid.words_guard", sender_id=payload.sender_id, action="replaced",
                    offers_on_record=len(offers), matched=found[0])
        _retries.pop(payload.sender_id, None)
        return payload.model_copy(update={"text": fallback_text(offers)})
    log.warning("ambergrid.words_guard", sender_id=payload.sender_id, action="retry", attempt=attempt,
                offers_on_record=len(offers), matched=found[0])
    raise RetryModel(feedback(found, offers))
