"""Output guard: the words cannot turn a budget estimate into a debt adjustment.

The tools already keep the two apart: no tool takes an amount or a balance,
every result shows the outstanding balance separately from the schedule, and
no option changes it. This hook is the second line, for the words. It reads
every model response before the customer sees it and sends it back when it:

- describes the budget plan as a debt adjustment ("your balance will be
  waived", "$108 a month is all you owe"; ``lib.budget.debt_adjustment_claims``),
  the case's failure;
- promises relief the hardship team has not decided (``relief_promises``);
- puts forward a monthly amount no billing-service option in this
  conversation carries ("I can do $70 a month"; ``unauthorized_amounts``).

After two consecutive retries the text is replaced with a fixed answer built
from tool data. Authorized amounts are the ones the billing tools returned in
this conversation, current or withdrawn: repeating a real schedule is not
inventing one.

Mantle hands ``modify_tool_result`` the tool's result as serialized JSON
text, not a dict (found in the HarborCover policy-status build), so it is
parsed. A tool behind ``requires_confirmation`` never reaches this hook under
its own name: once the customer answers, the model calls
``resolve_tool_confirmation``, the engine runs ``request_budget_option``
inside it, and the hook sees only ``resolve_tool_confirmation`` carrying the
gated tool's result (``rasa/mantle/orchestration/orchestrator.py``, the
dispatch loop that calls ``apply_tool_result_hooks``, on 3.21.0.dev5). Found
in this build's estimate run, where the guard missed the re-estimated $66.50
and replaced a correct reply; so that name is read too.

Each intervention is logged as ``ambergrid.budget_words_guard`` with the
sender id, so the case-build harness counts how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict

import structlog

from lib.budget import debt_adjustment_claims, money, relief_promises, to_money, unauthorized_amounts
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
BILLING_TOOLS = {"get_budget_quote", "select_budget_option", "request_budget_option", "check_budget_request",
                 "resolve_tool_confirmation"}
AMOUNT_KEYS = ("budget_estimate_usd", "monthly_total_usd", "balance_spread_usd")

# Per conversation, in process memory: what the billing service said, and retries.
_seen: dict[str, dict] = defaultdict(lambda: {"amounts": set(), "balances": {}})
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


def remember(seen: dict, value: dict) -> None:
    """Record every authorized amount and balance a billing tool returned."""
    views = list(value.get("options") or []) + list(value.get("current_options") or [])
    if value.get("status") == "selected":
        views.append(value)
    if isinstance(value.get("payment_schedule"), dict):
        views.append(value["payment_schedule"])
    for view in views:
        for key in AMOUNT_KEYS:
            amount = to_money(view.get(key)) if view.get(key) is not None else None
            if amount is not None:
                seen["amounts"].add(amount)
    balance = value.get("outstanding_balance")
    if isinstance(balance, dict) and value.get("account"):
        seen["balances"][value["account"]] = balance.get("amount_usd")


def problems(text: str, seen: dict) -> list[str]:
    found = [f"describes the budget plan as a debt adjustment: {hit!r}" for hit in debt_adjustment_claims(text)]
    found += [f"promises relief: {hit!r}" for hit in relief_promises(text)]
    found += [f"puts forward an amount no option carries: {hit}" for hit in unauthorized_amounts(text, seen["amounts"])]
    return found


def _balances(seen: dict) -> str:
    return "; ".join(f"{acct}: {money(amount)}" for acct, amount in sorted(seen["balances"].items()))


def feedback(found: list[str], seen: dict) -> str:
    amounts = ", ".join(money(a) for a in sorted(seen["amounts"])) or "none read yet in this conversation"
    return (
        f"Your draft {'; '.join(found)}. A budget amount is an estimate of usage; it never waives, reduces or "
        "replaces the outstanding balance, and only the hardship team decides any relief. "
        f"Balances on record: {_balances(seen) or 'none read yet'}. Authorized monthly amounts: {amounts}. "
        "Rewrite it: keep the schedule and the balance separate, offer no other amount, and promise no relief."
    )


def fallback_text(seen: dict) -> str:
    """Built only from tool data, so it cannot adjust a debt or offer terms."""
    balances = _balances(seen)
    return (
        "A budget plan changes the payment schedule, not the stated balance. "
        + (f"Outstanding balance on record: {balances}; no budget option waives or reduces it. " if balances else "")
        + "I can only offer the options Amber Grid's billing service has authorized. If none of them is "
        "affordable, I can refer you to our hardship team, who decide what support is possible."
    )


@modify_tool_result()
async def remember_billing_results(payload: ToolResultPayload) -> ToolResultPayload:
    if payload.tool_name in BILLING_TOOLS or payload.tool_name.startswith("route_"):
        remember(_seen[payload.sender_id], _as_dict(payload.value))
    return payload


@modify_model_response()
async def block_debt_adjustment_words(payload: ModelResponsePayload) -> ModelResponsePayload:
    if not ENABLED:
        return payload
    text = payload.text or ""
    seen = _seen[payload.sender_id]
    found = problems(text, seen)
    if not found:
        _retries.pop(payload.sender_id, None)
        return payload
    _retries[payload.sender_id] += 1
    attempt = _retries[payload.sender_id]
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning("ambergrid.budget_words_guard", sender_id=payload.sender_id, action="replaced",
                    matched=found[0])
        _retries.pop(payload.sender_id, None)
        return payload.model_copy(update={"text": fallback_text(seen)})
    log.warning("ambergrid.budget_words_guard", sender_id=payload.sender_id, action="retry", attempt=attempt,
                matched=found[0])
    raise RetryModel(feedback(found, seen))
