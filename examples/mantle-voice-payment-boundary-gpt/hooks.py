"""Observers that measure the card-data boundary. They change nothing.

- ``on_model_request`` scans every model request for card details that got
  past speech-to-text, and logs ``willowshop.model_request_scan`` with counts
  only: messages sent, messages still holding card details, and messages
  carrying the "[card details removed]" placeholder. It is the evidence that
  card digits did or did not reach the model vendor.
- ``on_turn_started``, ``on_incoming_message`` and ``on_outgoing_text`` log
  that they ran. Mantle declares the last two as hook points, and an
  ``incoming_message`` modifier would be the natural place to strip card
  details from what the caller said, but on rasa-pro 3.21.0.dev5 no code path
  dispatches either of them (README, "What we found"). Counting them against
  ``on_turn_started`` in a live run shows it.

Each log line carries the sender id, so the harness counts it per conversation.
"""

from __future__ import annotations

import re

import structlog

from lib.pci import PLACEHOLDER, contains_payment_secret
from rasa.mantle.hooks import (
    IncomingMessagePayload,
    ModelRequestPayload,
    OutgoingTextPayload,
    TurnStartedPayload,
    on_incoming_message,
    on_model_request,
    on_outgoing_text,
    on_turn_started,
)

log = structlog.get_logger()

# Mantle's system prompt carries "Current date and time: 2026-09-30 19:37"
# (rasa/mantle/prompts/system_prompt.py, _DATETIME_FORMAT). Its 12 digits read
# as a card-length run, so engine date-times are masked before the scan. The
# first recorded runs scanned without this and counted every request.
_ENGINE_DATETIME_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?")


def _text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, list):
        return " ".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
    return str(content or "")


@on_model_request()
async def scan_model_request(payload: ModelRequestPayload) -> None:
    # The conversation id itself ends in a run-date stamp (8 digits) and Mantle
    # puts it in the prompt; it is not card data.
    texts = [(str(m.get("role")), _ENGINE_DATETIME_RE.sub("<datetime>",
              _text(m).replace(payload.sender_id, "<conversation id>"))) for m in payload.messages]
    flagged = [role for role, t in texts if contains_payment_secret(t)]
    log.info("willowshop.model_request_scan", sender_id=payload.sender_id, messages=len(texts),
             messages_with_card_details=len(flagged), card_details_roles=sorted(set(flagged)),
             messages_with_placeholder=sum(1 for _, t in texts if PLACEHOLDER in t))


@on_turn_started()
async def turn_started(payload: TurnStartedPayload) -> None:
    log.info("willowshop.turn_started_hook", sender_id=payload.sender_id, is_voice=payload.is_voice)


@on_incoming_message()
async def incoming_message(payload: IncomingMessagePayload) -> None:
    log.info("willowshop.incoming_message_hook", sender_id=payload.sender_id,
             card_details=contains_payment_secret(payload.text))


@on_outgoing_text()
async def outgoing_text(payload: OutgoingTextPayload) -> None:
    log.info("willowshop.outgoing_text_hook", sender_id=payload.sender_id, is_voice=payload.is_voice)
