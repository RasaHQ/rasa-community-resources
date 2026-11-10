"""Two hooks: a request fix for Claude, and an output guard for payoff figures.

**Request fix (Claude).** Anthropic's API rejects a request whose last message
is the assistant's ("This model does not support assistant message prefill.
The conversation must end with a user message."). Over REST the customer's
first message starts the session, so the session-start greeting lands after
it in the tracker, and Mantle's ``append_current_user_message``
(``rasa/mantle/prompts/messages.py``) does not re-append the user's text
because it compares only with the last *user* text. The first model call of
every conversation then ends on the greeting and fails, and the customer gets
"I'm sorry, but something went wrong." (``case-build/results/estimate/``).
``ensure_trailing_user_turn`` re-appends the latest user message when a
request would end on an assistant text turn, which is what the engine does
when the greeting is not in between. Each fix is logged as
``northgate.trailing_user_turn_fix`` with the roles it saw, so the runs count
how often Claude would have been sent a trailing assistant turn. Set
``ENSURE_TRAILING_USER_TURN`` to False (the ``no-trailing-user-fix`` variant
in ``case-build/conversations.json``) to see the engine without it.

**Output guard: no payoff figure without a presented quote, and no closure promise.**

The tools already keep a payoff figure behind the contract: present_payoff_quote
returns an amount only when the quote on file is current, lists its charges
and has a servicing route, and a blocked result carries no amount. This hook is
the second line, for the words. It reads every model response before the
customer sees it and sends it back when:

- it presents a payoff figure (``lib.servicing.payoff_figures``) that is not
  the amount of a quote present_payoff_quote presented in this conversation:
  a balance, yesterday's figure, a number the customer typed, or an estimate;
- it promises the loan will close, or has closed, with no condition in front
  (``lib.servicing.closure_promises``). No tool here takes a payment.

After two consecutive retries the text is replaced with a fixed answer built
from tool data. Every intervention is logged as ``northgate.payoff_guard``
with the sender id, so the case-build harness counts how often the model
tried; the run's results report the count, the guard does not hide it.

Mantle hands ``modify_tool_result`` the tool's result as serialized JSON text,
not a dict (found in the HarborCover case build), so it is parsed.
"""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal

import structlog

from lib.servicing import closure_promises, payoff_figures
from rasa.mantle.hooks import (
    ModelRequestPayload,
    ModelResponsePayload,
    RetryModel,
    ToolResultPayload,
    modify_model_request,
    modify_model_response,
    modify_tool_result,
)

log = structlog.get_logger()

ENSURE_TRAILING_USER_TURN = True
MAX_CONSECUTIVE_RETRIES = 2

# Per conversation, in process memory: presented quotes (amount -> quote) and retries.
_quotes: dict[str, dict[Decimal, dict]] = defaultdict(dict)
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


def remember(quotes: dict[Decimal, dict], value: dict) -> None:
    if value.get("status") != "presented" or not value.get("payoff_amount"):
        return
    amount = Decimal(value["payoff_amount"].replace("$", "").replace(",", ""))
    quotes[amount] = {"quote_ref": value.get("quote_ref"), "loan": value.get("loan"),
                      "good_through": value.get("good_through"), "amount": value["payoff_amount"]}


def problems(text: str, quotes: dict[Decimal, dict]) -> tuple[list[str], list[str]]:
    unquoted = [f"${a:,.2f}" for a in payoff_figures(text) if a not in quotes]
    return unquoted, closure_promises(text)


def feedback(unquoted: list[str], promises: list[str], quotes: dict[Decimal, dict]) -> str:
    parts = []
    if unquoted:
        on_record = "; ".join(f"{q['quote_ref']}: {q['amount']} for the {q['loan']}, good through {q['good_through']}"
                              for q in quotes.values()) or "none"
        parts.append(
            f"Your draft presents {', '.join(unquoted)} as a payoff amount, but no presented quote has that "
            f"amount. Presented quotes: {on_record}. State a payoff amount only from a presented quote; "
            "otherwise refresh the quote or offer a servicing callback, and give no estimate."
        )
    if promises:
        parts.append(
            "Your draft promises the loan will close. No tool here takes a payment; the loan closes only "
            "after the payoff is received and posted. Say that instead."
        )
    return " ".join(parts) + " Rewrite the reply."


def fallback_text(quotes: dict[Decimal, dict]) -> str:
    """Built only from tool data, so it cannot claim more than the servicing system holds."""
    if not quotes:
        return ("I can't give a payoff amount without a current quote from the servicing system. "
                "I can request a new quote or arrange a callback from loan servicing.")
    lines = [f"Quote {q['quote_ref']} for your {q['loan']} is {q['amount']}, good through {q['good_through']}."
             for q in quotes.values()]
    return " ".join(lines) + " The loan closes only after the payoff is received and posted."


def trailing_user_fix(messages: list[dict]) -> tuple[list[dict], dict | None]:
    """Messages that end on a user turn, and what was changed (None when nothing was).

    Only a request whose last non-system message is assistant *text* (no tool
    calls) is changed: the latest user message is appended again. System
    messages at the end stay where they are; LiteLLM lifts them into Anthropic's
    top-level system prompt.
    """
    conversational = [m for m in messages if m.get("role") != "system"]
    if not conversational:
        return messages, None
    last = conversational[-1]
    if last.get("role") != "assistant" or last.get("tool_calls"):
        return messages, None
    users = [m for m in conversational if m.get("role") == "user"]
    detail = {"roles_tail": [m.get("role") for m in conversational[-3:]], "user_messages": len(users)}
    if not users:
        return messages, {**detail, "action": "none_no_user_message"}
    return [*messages, {"role": "user", "content": users[-1].get("content")}], {**detail, "action": "appended_last_user"}


@modify_model_request()
async def ensure_trailing_user_turn(payload: ModelRequestPayload) -> ModelRequestPayload:
    if not ENSURE_TRAILING_USER_TURN:
        return payload
    messages, detail = trailing_user_fix(payload.messages)
    if detail is None:
        return payload
    log.warning("northgate.trailing_user_turn_fix", sender_id=payload.sender_id, iteration=payload.iteration, **detail)
    return payload.model_copy(update={"messages": messages})


@modify_tool_result()
async def remember_presented_quotes(payload: ToolResultPayload) -> ToolResultPayload:
    if payload.tool_name == "present_payoff_quote":
        remember(_quotes[payload.sender_id], _as_dict(payload.value))
    return payload


@modify_model_response()
async def block_unquoted_payoffs(payload: ModelResponsePayload) -> ModelResponsePayload:
    text = payload.text or ""
    quotes = _quotes.get(payload.sender_id, {})
    unquoted, promises = problems(text, quotes)
    if not unquoted and not promises:
        _retries.pop(payload.sender_id, None)
        return payload
    _retries[payload.sender_id] += 1
    attempt = _retries[payload.sender_id]
    details = {"unquoted_figures": unquoted, "closure_promises": promises, "quotes_on_record": len(quotes)}
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning("northgate.payoff_guard", sender_id=payload.sender_id, action="replaced", **details)
        _retries.pop(payload.sender_id, None)
        return payload.model_copy(update={"text": fallback_text(quotes)})
    log.warning("northgate.payoff_guard", sender_id=payload.sender_id, action="retry", attempt=attempt, **details)
    raise RetryModel(feedback(unquoted, promises, quotes))
