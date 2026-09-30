"""Output guard: no transfer described as posted without a posted ledger entry.

The tools already keep the two states apart: submit_transfer and
check_transfer_status return ``ledger_status`` ``pending``, ``posted`` or
``unknown``, and only a transfer between the customer's own accounts posts at
once. This hook is the second line, for the words. It reads every model
response before the caller sees it. If the text says or implies the money has
moved ("it has gone through", "Sam has it now", ``lib.ledger.posted_claims``)
and the ledger has not posted what the text is about, the response is
discarded and the model is sent back with the ledger states. After two
consecutive retries the text is replaced with a fixed answer built from tool
data.

A claim is allowed when the text cites the reference of a posted transfer, or
when every transfer this conversation has seen is posted. That is narrow on
purpose: a posted transfer between the caller's own accounts must not make a
pending payment to someone else sound complete.

Mantle hands ``modify_tool_result`` the tool's result as serialized JSON
text, not a dict (found in the HarborCover case build), so it is parsed.

Each intervention is logged as ``northgate.posted_claim_guard`` with the
sender id, so the case-build harness counts how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict

import structlog

from lib.ledger import posted_claims
from rasa.mantle.hooks import (
    ModelResponsePayload,
    RetryModel,
    ToolResultPayload,
    modify_model_response,
    modify_tool_result,
)

log = structlog.get_logger()

MAX_CONSECUTIVE_RETRIES = 2
LEDGER_TOOLS = {"submit_transfer", "check_transfer_status"}

# Per conversation, in process memory: what the ledger said about each transfer
# (key: reference, or attempt id when the reference was lost), and retries.
_transfers: dict[str, dict[str, dict]] = defaultdict(dict)
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


def remember(transfers: dict[str, dict], value: dict) -> None:
    """Record one ledger answer. A later answer for the same attempt replaces the earlier one."""
    if value.get("status") not in ("submitted", "unconfirmed", "read"):
        return
    key = value.get("reference") or value.get("attempt_id")
    if not key:
        return
    attempt = value.get("attempt_id")
    if attempt and value.get("reference"):
        transfers.pop(attempt, None)
    transfers[str(key).upper()] = {
        "ledger_status": value.get("ledger_status") or "unknown",
        "amount": value.get("amount"),
        "destination": value.get("destination"),
    }


def claim_allowed(text: str, transfers: dict[str, dict]) -> bool:
    posted = {ref for ref, t in transfers.items() if t["ledger_status"] == "posted"}
    if any(ref in text.upper() for ref in posted):
        return True
    return bool(transfers) and len(posted) == len(transfers)


def ledger_lines(transfers: dict[str, dict]) -> str:
    return "; ".join(
        f"{ref}: {t.get('amount')} to {t.get('destination')}, ledger_status {t['ledger_status']}"
        for ref, t in sorted(transfers.items())
    )


def feedback(transfers: dict[str, dict]) -> str:
    if not transfers:
        return (
            "Your draft said or implied that money has moved. No transfer has been submitted or read in "
            "this conversation. Rewrite it without saying a transfer is sent, posted, complete or received."
        )
    return (
        "Your draft said or implied that money has moved, but the ledger has not posted it. Ledger states: "
        f"{ledger_lines(transfers)}. Rewrite it: give the reference and say pending, posted or unconfirmed "
        "exactly as the ledger does. A pending transfer is reserved, not received."
    )


def fallback_text(transfers: dict[str, dict]) -> str:
    """Built only from tool data, so it cannot claim more than the ledger holds."""
    if not transfers:
        return "No transfer has been submitted in this conversation, so nothing has posted."
    words = {"posted": "posted", "pending": "pending, not yet received by the payee's bank",
             "unknown": "not confirmed by the ledger yet"}
    lines = [
        f"Transfer {ref} of {t.get('amount')} to {t.get('destination')} is {words.get(t['ledger_status'], t['ledger_status'])}."
        for ref, t in sorted(transfers.items())
    ]
    return " ".join(lines)


@modify_tool_result()
async def remember_ledger_states(payload: ToolResultPayload) -> ToolResultPayload:
    if payload.tool_name in LEDGER_TOOLS:
        remember(_transfers[payload.sender_id], _as_dict(payload.value))
    return payload


@modify_model_response()
async def block_posted_claims(payload: ModelResponsePayload) -> ModelResponsePayload:
    text = payload.text or ""
    claims = posted_claims(text)
    transfers = _transfers.get(payload.sender_id, {})
    if not claims or claim_allowed(text, transfers):
        _retries.pop(payload.sender_id, None)
        return payload
    _retries[payload.sender_id] += 1
    attempt = _retries[payload.sender_id]
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning(
            "northgate.posted_claim_guard",
            sender_id=payload.sender_id,
            action="replaced",
            transfers_on_record=len(transfers),
            matched=claims[0],
        )
        _retries.pop(payload.sender_id, None)
        return payload.model_copy(update={"text": fallback_text(transfers)})
    log.warning(
        "northgate.posted_claim_guard",
        sender_id=payload.sender_id,
        action="retry",
        attempt=attempt,
        transfers_on_record=len(transfers),
        matched=claims[0],
    )
    raise RetryModel(feedback(transfers))
