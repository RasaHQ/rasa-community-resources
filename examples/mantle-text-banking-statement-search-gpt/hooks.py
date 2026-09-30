"""Output guard: no partial search presented as complete, no search total called a statement balance.

The tools already keep the scope explicit: every search result says
``complete`` or ``partial``, carries its range and statuses, and a partial one
has no period total. This hook is the second line, for the words. It reads
every model response before the customer sees it. When the latest search in
the conversation is partial and the text presents a result set as complete
("in total", "that's all", "you spent $412.10", ``lib.history.complete_claims``),
or when the text calls a search total a statement balance, the response is
discarded and the model is sent back with the search states. After two
consecutive retries the text is replaced with a fixed answer built from tool
data.

Mantle hands ``modify_tool_result`` the tool's result as serialized JSON
text, not a dict (found in the HarborCover case build), so it is parsed.

Each intervention is logged as ``northgate.search_scope_guard`` with the
sender id, so the case-build harness counts how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict

import structlog

from lib.history import complete_claims, statement_claims
from rasa.mantle.hooks import (
    ModelResponsePayload,
    RetryModel,
    ToolResultPayload,
    modify_model_response,
    modify_tool_result,
)

log = structlog.get_logger()

MAX_CONSECUTIVE_RETRIES = 2
SEARCH_TOOLS = {"search_transactions", "continue_search"}

# Per conversation, in process memory: each issued search by reference, in order.
_searches: dict[str, dict[str, dict]] = defaultdict(dict)
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


def remember(searches: dict[str, dict], value: dict) -> None:
    """Record one issued search. A continuation replaces the earlier state and makes it the latest."""
    if value.get("status") not in ("complete", "partial") or not value.get("search_ref"):
        return
    ref = value["search_ref"]
    searches.pop(ref, None)
    searches[ref] = {
        "complete": bool(value.get("complete")),
        "count": value.get("count"),
        "label": (value.get("range") or {}).get("label"),
        "status_label": value.get("status_label"),
        "totals": [t for t in (value.get("total_debits"), value.get("total_credits")) if t],
    }


def problems(text: str, searches: dict[str, dict]) -> list[str]:
    found = []
    if searches:
        latest = list(searches.values())[-1]
        if not latest["complete"] and complete_claims(text):
            found.append("partial_as_complete")
    totals = [t for s in searches.values() for t in s["totals"] if t != "$0.00"]
    if statement_claims(text, totals):
        found.append("search_total_as_statement")
    return found


def search_lines(searches: dict[str, dict]) -> str:
    return "; ".join(
        f"{ref}: {s['status_label']}, {s['label']}, {s['count']} transactions, "
        f"{'complete' if s['complete'] else 'PARTIAL, no period total'}"
        for ref, s in searches.items()
    )


def feedback(found: list[str], searches: dict[str, dict]) -> str:
    parts = []
    if "partial_as_complete" in found:
        parts.append("Your draft presented a partial search as complete (a period total, or all the transactions). "
                     "The latest search is partial: not every page was read.")
    if "search_total_as_statement" in found:
        parts.append("Your draft called a search total a statement balance. A search total covers the searched range "
                     "and statuses only; statements come from get_statement and run on the billing cycle.")
    return (" ".join(parts) + f" Searches: {search_lines(searches)}. Rewrite it: say which search is partial, give only "
            "the transactions shown, give no period total for a partial search, and offer to continue it.")


def fallback_text(searches: dict[str, dict]) -> str:
    """Built only from tool data, so it cannot claim more than the searches hold."""
    lines = []
    for ref, s in searches.items():
        if s["complete"]:
            lines.append(f"Search {ref} ({s['status_label']}, {s['label']}) is complete with {s['count']} transactions.")
        else:
            lines.append(f"Search {ref} ({s['status_label']}, {s['label']}) is partial: {s['count']} transactions "
                         "read so far, so there is no total for the period yet. I can continue it.")
    lines.append("A search result is not a statement balance.")
    return " ".join(lines)


@modify_tool_result()
async def remember_searches(payload: ToolResultPayload) -> ToolResultPayload:
    if payload.tool_name in SEARCH_TOOLS:
        remember(_searches[payload.sender_id], _as_dict(payload.value))
    return payload


@modify_model_response()
async def guard_search_scope(payload: ModelResponsePayload) -> ModelResponsePayload:
    text = payload.text or ""
    searches = _searches.get(payload.sender_id, {})
    found = problems(text, searches)
    if not found:
        _retries.pop(payload.sender_id, None)
        return payload
    _retries[payload.sender_id] += 1
    attempt = _retries[payload.sender_id]
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning("northgate.search_scope_guard", sender_id=payload.sender_id, action="replaced",
                    problems=found, searches_on_record=len(searches))
        _retries.pop(payload.sender_id, None)
        return payload.model_copy(update={"text": fallback_text(searches)})
    log.warning("northgate.search_scope_guard", sender_id=payload.sender_id, action="retry", attempt=attempt,
                problems=found, searches_on_record=len(searches))
    raise RetryModel(feedback(found, searches))
