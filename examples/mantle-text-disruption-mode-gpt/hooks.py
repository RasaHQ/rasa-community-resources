"""Output guard: no recovery promise the holds do not back.

The tools keep the three states apart: a search returns seat counts marked
as not a hold, hold_recovery_option returns ``held`` only when the inventory
placed a hold, and no tool ever confirms a journey. This hook is the second
line, for the words. It reads every model response before the passenger sees
it:

- A sentence that commits a journey ("you're booked on HZ 315", "your seat is
  confirmed", "you're guaranteed a seat", ``lib.recovery.COMMITMENT_PATTERN``)
  is never backed, because this chat cannot confirm a journey.
- A sentence that says a seat is held (``HOLD_CLAIM_PATTERN``) is backed only
  while a hold the tools placed or found is active in this conversation.

An unbacked draft is discarded and the model is sent back with the hold
states. After two consecutive retries the text is replaced with a fixed
answer built from tool data.

Mantle hands ``modify_tool_result`` the tool's result as serialized JSON
text, not a dict (found in the HarborCover case build), so it is parsed.

Each intervention is logged as ``horizon.promise_guard`` with the sender id,
so the case-build harness counts how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict

import structlog

from lib.recovery import promise_claims
from rasa.mantle.hooks import (
    ModelResponsePayload,
    RetryModel,
    ToolResultPayload,
    modify_model_response,
    modify_tool_result,
)

log = structlog.get_logger()

MAX_CONSECUTIVE_RETRIES = 2
HOLD_TOOLS = {"hold_recovery_option", "check_hold", "release_hold"}

# Per conversation, in process memory: each hold the tools reported, and retries.
_holds: dict[str, dict[str, dict]] = defaultdict(dict)
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


def remember(holds: dict[str, dict], tool: str, value: dict) -> None:
    """Record one hold state. A later answer for the same hold replaces the earlier one."""
    hold_id = value.get("hold_id")
    status = value.get("status")
    if not hold_id or status not in ("held", "active", "expired", "released"):
        return
    holds[str(hold_id).upper()] = {
        "state": "active" if status in ("held", "active") else status,
        "flight": value.get("flight") or value.get("option"),
        "expires": value.get("expires"),
    }


def unbacked(text: str, holds: dict[str, dict]) -> list[tuple[str, str]]:
    active = any(h["state"] == "active" for h in holds.values())
    return [(kind, s) for kind, s in promise_claims(text) if kind == "commitment" or not active]


def hold_lines(holds: dict[str, dict]) -> str:
    return "; ".join(f"{hid}: {h.get('flight')}, {h['state']}, expires {h.get('expires')}"
                     for hid, h in sorted(holds.items()))


def feedback(holds: dict[str, dict]) -> str:
    state = f"Holds on record: {hold_lines(holds)}." if holds else "No seat is held in this conversation."
    return (
        "Your draft promised more than the holds back. This chat never books, rebooks or confirms a journey, "
        f"and a seat count is not a hold. {state} Rewrite it: say what is held (with its hold id and expiry) "
        "or that nothing is held, and never say the passenger is booked, confirmed or guaranteed a seat."
    )


def fallback_text(holds: dict[str, dict]) -> str:
    """Built only from tool data, so it cannot promise more than the holds."""
    active = {hid: h for hid, h in holds.items() if h["state"] == "active"}
    if not active:
        return ("No seat is held for you in this chat, and nothing here confirms a journey. I can list recovery "
                "flights, try to hold one, or put you in the recovery queue.")
    lines = [f"Hold {hid} on {h.get('flight')} is active until {h.get('expires')}." for hid, h in sorted(active.items())]
    return " ".join(lines) + " A hold is not a confirmed journey."


@modify_tool_result()
async def remember_hold_states(payload: ToolResultPayload) -> ToolResultPayload:
    if payload.tool_name in HOLD_TOOLS:
        remember(_holds[payload.sender_id], payload.tool_name, _as_dict(payload.value))
    return payload


@modify_model_response()
async def block_unbacked_promises(payload: ModelResponsePayload) -> ModelResponsePayload:
    text = payload.text or ""
    holds = _holds.get(payload.sender_id, {})
    claims = unbacked(text, holds)
    if not claims:
        _retries.pop(payload.sender_id, None)
        return payload
    _retries[payload.sender_id] += 1
    attempt = _retries[payload.sender_id]
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning("horizon.promise_guard", sender_id=payload.sender_id, action="replaced",
                    holds_on_record=len(holds), kind=claims[0][0], matched=claims[0][1])
        _retries.pop(payload.sender_id, None)
        return payload.model_copy(update={"text": fallback_text(holds)})
    log.warning("horizon.promise_guard", sender_id=payload.sender_id, action="retry", attempt=attempt,
                holds_on_record=len(holds), kind=claims[0][0], matched=claims[0][1])
    raise RetryModel(feedback(holds))
