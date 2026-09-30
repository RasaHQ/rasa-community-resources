"""Output guard: the words cannot switch a supply off that the service state still has on.

The tools already make an early closure impossible: no tool closes a
service, and a verified move order ends the current supply only after the
confirmed move-out day. This hook is the second line, for the words. It reads
every model response before the customer sees it and sends it back when it
says the current supply is already off, closed, disconnected or cancelled
(``lib.moves.closure_claims``, which reads straight and typographic
apostrophes alike). No service in this build is off, so any such sentence is
false.

After two consecutive retries the text is replaced with a fixed answer built
from the service states the tools returned in this conversation.

Mantle hands ``modify_tool_result`` the tool's result as serialized JSON
text, not a dict (found in the HarborCover policy-status build), so it is
parsed.

Each intervention is logged as ``ambergrid.closure_words_guard`` with the
sender id, so the case-build harness counts how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict

import structlog

from lib.moves import closure_claims, long_date
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

# Per conversation, in process memory: the latest state of each current
# service a tool returned, and retries.
_services: dict[str, dict[str, dict]] = defaultdict(dict)
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


def remember(services: dict[str, dict], value: dict) -> None:
    current = value.get("current_service")
    if isinstance(current, dict) and current.get("service_point"):
        services[current["service_point"]] = current


def _state_line(service: dict) -> str:
    from datetime import date

    through = service.get("stays_on_through")
    until = f" and stays on through {long_date(date.fromisoformat(through))}" if through else ""
    return f"your supply at {service.get('address')} is on now{until}"


def feedback(found: list[str], services: dict[str, dict]) -> str:
    states = "; ".join(_state_line(s) for s in services.values()) or "no service has been read yet"
    return (
        f"Your draft says the current supply is already off ({found[0]!r}). It is not: {states}. A move is a future "
        "instruction and nothing is switched off before the move-out day. Rewrite it without saying the supply is "
        "off, closed, disconnected or cancelled."
    )


def fallback_text(services: dict[str, dict]) -> str:
    """Built only from tool data, so it cannot say more than the service state holds."""
    if not services:
        return ("Nothing has been switched off. Your current supply stays on as it is until the move-out day you "
                "choose, and a move can be scheduled from tomorrow.")
    lines = [_state_line(s) for s in services.values()]
    text = "; ".join(lines)
    return f"Nothing has been switched off: {text[0].lower()}{text[1:]}."


@modify_tool_result()
async def remember_service_states(payload: ToolResultPayload) -> ToolResultPayload:
    remember(_services[payload.sender_id], _as_dict(payload.value))
    return payload


@modify_model_response()
async def block_closure_words(payload: ModelResponsePayload) -> ModelResponsePayload:
    if not ENABLED:
        return payload
    text = payload.text or ""
    found = closure_claims(text)
    services = _services.get(payload.sender_id, {})
    if not found:
        _retries.pop(payload.sender_id, None)
        return payload
    _retries[payload.sender_id] += 1
    attempt = _retries[payload.sender_id]
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning("ambergrid.closure_words_guard", sender_id=payload.sender_id, action="replaced",
                    services_on_record=len(services), matched=found[0])
        _retries.pop(payload.sender_id, None)
        return payload.model_copy(update={"text": fallback_text(services)})
    log.warning("ambergrid.closure_words_guard", sender_id=payload.sender_id, action="retry", attempt=attempt,
                services_on_record=len(services), matched=found[0])
    raise RetryModel(feedback(found, services))
