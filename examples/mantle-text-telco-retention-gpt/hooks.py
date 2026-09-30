"""Output guard: after a refusal, the words cannot keep offering, and no words can invent terms.

The tools already make the case failure impossible to record: after a
refusal get_retention_offer returns blocked and accept_retention_offer
records nothing, and only the catalogue's terms can be read back. This hook
is the second line, for the words. The case failure is a conversation, not a
record: an agent that keeps typing "how about 20% off?" after the customer
said stop has failed even if no tool ever ran.

It reads every model response before the customer sees it and sends it back
when the response puts an offer in front of the customer
(``lib.retention.offer_prompts``, straight and typographic apostrophes) and
either the customer has refused in this conversation, or the offer carries a
price or discount that no tool result in this conversation carried
(``lib.retention.invented_terms``). After two consecutive retries the text
is replaced with a fixed answer built from what the tools returned.

The customer's words come from the model request (``on_model_request``),
because Mantle's ``incoming_message`` hook point never runs on 3.21.0.dev5
(found in the Willow Shop payment-boundary build). Tool results come from
``modify_tool_result``; Mantle hands it the result as serialized JSON text,
not a dict (found in the HarborCover policy-status build), so it is parsed.

Each intervention is logged as ``juniper.offer_words_guard`` with the sender
id, so the case-build harness counts how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict

import structlog

from lib.retention import invented_terms, offer_prompts, refusal_in
from rasa.mantle.hooks import (
    ModelRequestPayload,
    ModelResponsePayload,
    RetryModel,
    ToolResultPayload,
    modify_model_response,
    modify_tool_result,
    on_model_request,
)

log = structlog.get_logger()

MAX_CONSECUTIVE_RETRIES = 2
# The `no-words-guard` variant in case-build/conversations.json sets this to False.
ENABLED = True

# Per conversation, in process memory.
_customer_words: dict[str, list[str]] = defaultdict(list)
_tool_texts: dict[str, list[str]] = defaultdict(list)
_closed: dict[str, str] = {}
_cancellations: dict[str, dict[str, str]] = defaultdict(dict)
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


def _text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, list):
        return " ".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
    return str(content or "")


def remember_result(sender: str, tool: str, value: dict) -> None:
    _tool_texts[sender].append(json.dumps(value, ensure_ascii=False))
    if tool == "withdraw_contact" and value.get("status") == "recorded":
        _closed[sender] = "the customer withdrew contact"
    if value.get("status") == "blocked" and value.get("reason") == "contact_withdrawn":
        _closed.setdefault(sender, "offers are closed for this customer")
    if tool == "record_cancellation_request" and value.get("status") == "recorded" and value.get("reference"):
        _cancellations[sender][value.get("service") or "service"] = value["reference"]


def refused(sender: str) -> str | None:
    if sender in _closed:
        return _closed[sender]
    for words in _customer_words.get(sender, []):
        found = refusal_in(words)
        if found:
            return f"the customer said {found!r}"
    return None


def feedback(why: str, prompts: list[str], invented: list[str]) -> str:
    if not why:
        return (f"Your draft offers terms no tool returned ({', '.join(invented)}). Only an offer that "
                "get_retention_offer returned exists, with exactly its terms. Rewrite it without any price, discount "
                "or offer of your own.")
    return (f"Your draft puts an offer in front of the customer ({prompts[0]!r}) after a refusal: {why}. After a "
            "refusal make no offer, mention no price or discount, and do not ask whether they want one. Rewrite it "
            "to confirm only what they asked for.")


def fallback_text(sender: str, invented_only: bool) -> str:
    """Built only from tool data, so it cannot offer anything."""
    lines = []
    if invented_only:
        lines.append("I can't apply those terms: there is no authorized offer for them.")
    else:
        lines.append("Understood. I won't make any more offers.")
    for service, reference in _cancellations.get(sender, {}).items():
        lines.append(f"Your cancellation request for your {service} is recorded ({reference}).")
    if not _cancellations.get(sender):
        lines.append("If you want to cancel, tell me which service and I will record the request.")
    return " ".join(lines)


@on_model_request()
async def read_customer_words(payload: ModelRequestPayload) -> None:
    words = [_text(m) for m in payload.messages if m.get("role") == "user"]
    _customer_words[payload.sender_id] = [w for w in words if not w.strip().lower().startswith("/session_start")]


@modify_tool_result()
async def remember_tool_results(payload: ToolResultPayload) -> ToolResultPayload:
    remember_result(payload.sender_id, payload.tool_name, _as_dict(payload.value))
    return payload


@modify_model_response()
async def block_offer_words(payload: ModelResponsePayload) -> ModelResponsePayload:
    if not ENABLED:
        return payload
    sender = payload.sender_id
    text = payload.text or ""
    prompts = offer_prompts(text)
    why = refused(sender) if prompts else None
    invented = invented_terms(text, _tool_texts.get(sender, [])) if prompts else []
    if not prompts or (why is None and not invented):
        _retries.pop(sender, None)
        return payload
    _retries[sender] += 1
    attempt = _retries[sender]
    kind = "after_refusal" if why else "invented_terms"
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning("juniper.offer_words_guard", sender_id=sender, action="replaced", kind=kind,
                    matched=(invented or prompts)[0])
        _retries.pop(sender, None)
        return payload.model_copy(update={"text": fallback_text(sender, invented_only=why is None)})
    log.warning("juniper.offer_words_guard", sender_id=sender, action="retry", attempt=attempt, kind=kind,
                matched=(invented or prompts)[0])
    raise RetryModel(feedback(why or "", prompts, invented))
