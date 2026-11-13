# SPDX-License-Identifier: MIT
"""Rasa-owned host glue. Routing IDs are not real customer authentication.

Only the private teaching launcher chooses the fixed fictional caller. The model
tools never receive the host capability, the MCP credential or a review handle.
Confirming and sending a transfer are private host calls made only after the
next raw user turn says exactly "confirm transfer".
"""
import asyncio
from dataclasses import dataclass, field
import json
import os
import re
import time

from rasa.mantle.orchestration.turn_context import current_turn_context
from .hostclient import HostRefused
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from lib.reply_policy import delivery_pending, remember_delivery, deliver_reply, is_user_turn


@dataclass
class _Conversation:
    origin: str = field(repr=False)
    client: object = field(repr=False)
    session: object = field(repr=False)
    pending: dict | None = field(default=None, repr=False)
    observed_turn: int = 0
    pending_turn: int = 0
    last_submit_state: str | None = None
    # Each successful simulated step-up, with the age of the raw phrase it used.
    assured_count: int = 0
    assured_age: float | None = None
    # Serialises review and submit for one conversation across their awaits.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


_conversations = {}


def _is_confirmation(text):
    return re.fullmatch(r"confirm\s+transfer[.!]?", text.strip().casefold()) is not None


def _norm(text):
    return " ".join(text.strip().casefold().rstrip(".!?").split())


def _is_reset(text):
    return _norm(text) in {"reset", "logout", "log out", "switch user"}


def _is_assure(text):
    return _norm(text) in {"verify me", "verify my identity"}


def _users(context):
    return [event.as_dict() for event in context.events if event.as_dict().get("event") == "user"]


def _payload(result):
    if result.isError:
        return {"state": "refused", "reason": "service_refused"}
    data = result.structuredContent
    if data is None:
        data = json.loads(result.content[0].text)
    if not isinstance(data, dict):
        raise ValueError("invalid_result")
    return data


def _safe(data):
    # Never forward transport errors, capabilities or host handles to the model.
    allowed = {"state", "reason", "accounts", "amount", "currency", "source", "destination",
               "balance_type", "entries", "page", "more", "scope", "due_date", "as_of"}
    return {key: value for key, value in data.items() if key in allowed}


async def _host(context, *, create=True):
    native = current_turn_context()
    origin = os.environ.get("PREMIER_HOST_URL", "")
    capability = os.environ.get("PREMIER_HOST_CAPABILITY", "")
    if not origin or len(capability) < 32:
        raise ValueError("host_unavailable")
    key = (origin, native.sender_id)  # never a tool or model argument
    users = _users(context)
    conversation = _conversations.get(key)
    if conversation is None:
        if not create:
            raise ValueError("review_unavailable")
        from .hostclient import HostClient
        client = HostClient(origin, capability)
        session = await asyncio.to_thread(client.open_session, "demo-A")
        conversation = _Conversation(origin, client, session, observed_turn=max(0, len(users) - 1))
        _conversations[key] = conversation
    text = native.turn.text.strip().lower()
    # A model may choose no tool on logout. Observe every raw user turn since the
    # last host operation before any later protected operation.
    unseen = users[conversation.observed_turn:]
    conversation.observed_turn = len(users)
    if any(_is_reset(str(event.get("text", ""))) for event in unseen):
        try:
            await asyncio.to_thread(conversation.client.reset, conversation.session)
        finally:
            _conversations.pop(key, None)
        raise ValueError("session_reset")
    said = [event.get("timestamp") for event in unseen if _is_assure(str(event.get("text", "")))]
    said = [stamp for stamp in said if isinstance(stamp, (int, float)) and not isinstance(stamp, bool)]
    if said:
        # Bind the simulated step-up to when the caller actually said it, not to
        # when a later tool call happened to notice it. A stale phrase stays stale.
        age = time.time() - max(said)
        await asyncio.to_thread(conversation.client.assure, conversation.session, age)
        conversation.assured_count += 1
        conversation.assured_age = age
    if conversation.pending and len(users) > conversation.pending_turn:
        # Only the immediately following exact phrase can confirm. A question,
        # denial, reset, changed request or intervening turn invalidates consent.
        if len(users) != conversation.pending_turn + 1 or not _is_confirmation(text):
            await asyncio.to_thread(conversation.client.cancel, conversation.session,
                                    conversation.pending["review"])
            conversation.pending = None
    return conversation


_CONFIRMATIONS = {"yes", "confirm", "confirmed", "confirm transfer"}
NO_ACTIVE_REVIEW_TEXT = ("The transfer review was canceled or is no longer active. "
                         "Request a new transfer before confirming.")


UNKNOWN_OUTCOME_TEXT = "The earlier transfer outcome is unknown. Do not retry. Check the original transfer status."
EXPIRED_REVIEW_TEXT = ("Your verification has expired, so this transfer was not reviewed and nothing was sent. "
                       "Say verify me, then ask for the transfer again.")
REVIEW_NOT_MADE_TEXT = "That transfer was not reviewed, and nothing was sent."
REVIEW_UNAVAILABLE_TEXT = ("The transfer review is unavailable, and nothing was sent. "
                           "Check the original transfer status before making another request.")
STALE_REVIEW_TEXT = ("That review can no longer be confirmed, and nothing was sent. "
                     "Say verify me if needed, then ask for the transfer again.")
OUTSIDE_SCOPE_TEXT = ("That transfer was not reviewed, and nothing was sent: only transfers between "
                      "your own listed accounts are supported.")


def _review_refusal_text(reason):
    """Host-owned words for a review that was not made: the model never improvises
    retry advice for a refused, unresolved or failed transfer review."""
    if reason == "outcome_unresolved":
        return UNKNOWN_OUTCOME_TEXT
    if reason in _EXPIRED:
        return EXPIRED_REVIEW_TEXT
    if reason in _OUT_OF_SCOPE:
        return OUTSIDE_SCOPE_TEXT
    return REVIEW_NOT_MADE_TEXT


_EXPIRED = frozenset({"assurance_required"})
_OUT_OF_SCOPE = frozenset({"account_unavailable", "unsupported_transfer"})


async def _unresolved(host):
    """True while the host's journal holds an unknown or pending outcome.

    The journal survives a restart; last_submit_state lives only in this
    process, so both are consulted before any new-request advice."""
    if host.last_submit_state == "unknown":
        return True
    try:
        result = await host.client.call(host.session, "banking_transfer_status", {})
        if result.isError:
            return True  # the status was never learned: never invite a new transfer
        data = _payload(result)
    except Exception:
        return True  # cannot tell: never invite a new transfer
    # Only a successful read of a recognized, resolved state allows new-request advice;
    # unknown, pending, missing or unrecognized all fail closed.
    return data.get("state") not in {"none", "accepted", "refused", "rejected"}


async def _read(context, name, arguments):
    try:
        host = await _host(context)
        if name == "banking_transfer_status" and _norm(current_turn_context().turn.text) in _CONFIRMATIONS:
            # A confirmation is about the review just read back, never an earlier
            # transfer: the latest retained outcome must not answer it.
            if host.pending:
                return ToolResult(llm_response={"state": "confirmation_pending",
                                                "instruction": "Call banking_submit_transfer now."})
            if await _unresolved(host):  # an unknown outcome is never retried, even after a restart
                await deliver_reply(context, UNKNOWN_OUTCOME_TEXT)
                return ToolResult(llm_response={"state": "unknown", "reason": "no_retry_check_original_status"})
            await deliver_reply(context, NO_ACTIVE_REVIEW_TEXT)
            return ToolResult(llm_response={"state": "not_submitted", "reason": "no_active_review"})
        result = _safe(_payload(await host.client.call(host.session, name, arguments)))
        if name == "banking_transfer_status" and result.get("state") == "accepted":
            await deliver_reply(context, "The transfer request was accepted. Accepted does not mean posted.")
        return ToolResult(llm_response=result)
    except Exception:
        return ToolResult(llm_response={"state": "unavailable", "reason": "host_or_service_unavailable"})


@tool(description="List only permitted fictional account aliases.")
async def banking_accounts(context: ToolContext = None) -> ToolResult:
    return await _read(context, "banking_accounts", {})


VERIFIED_TEXT = "Your simulated verification was refreshed. It lasts about a minute."
FRESH_SECONDS = 60  # the host's transfer grant window, "about a minute"


@tool(description="ALWAYS call this, and nothing else, when the caller says verify me or verify my identity. Refreshes simulated verification and delivers the confirmation sentence.")
async def banking_refresh_verification(context: ToolContext = None) -> ToolResult:
    # Rasa-side trigger, not an MCP tool, and no authority of its own: the host
    # refreshes the simulated grant only when it observes the caller's raw
    # "verify me" turn, dated by when it was said (see _host).
    try:
        # Only the caller's own turn counts: on a session-start pass the phrase is
        # pending, not yet this turn's message.
        if not is_user_turn(current_turn_context()) or not _is_assure(current_turn_context().turn.text):
            return ToolResult(llm_response={"state": "refused", "reason": "say_verify_me"})
        native = current_turn_context()
        key = (os.environ.get("PREMIER_HOST_URL", ""), native.sender_id)
        before = _conversations[key].assured_count if key in _conversations else 0
        host = await _host(context)
        # Say "refreshed" only when this call made the host grant a step-up from
        # a fresh raw phrase: a missing timestamp, an already consumed phrase or
        # a stale one gives no success wording.
        if host.assured_count <= before or host.assured_age is None or host.assured_age >= FRESH_SECONDS:
            return ToolResult(llm_response={"state": "refused", "reason": "verification_not_observed"})
        await deliver_reply(context, VERIFIED_TEXT)
        return ToolResult(llm_response={"state": "verified"})
    except Exception:
        return ToolResult(llm_response={"state": "unavailable", "reason": "host_or_service_unavailable"})


@tool(description="Read the supplied available balance of a permitted checking account.")
async def banking_balance(account: str, context: ToolContext = None) -> ToolResult:
    return await _read(context, "banking_balance", {"account": account})


@tool(description="Read one returned page of posted transactions, at most three.")
async def banking_history(account: str, page: int = 1, context: ToolContext = None) -> ToolResult:
    return await _read(context, "banking_history", {"account": account, "page": page})


@tool(description="Read the supplied next payment total and date of a permitted loan.")
async def banking_loan_payment(account: str, context: ToolContext = None) -> ToolResult:
    return await _read(context, "banking_loan_payment", {"account": account})


@tool(description="Read the CURRENT payoff amount only. A dated payoff quote is not supported.")
async def banking_payoff(account: str, context: ToolContext = None) -> ToolResult:
    return await _read(context, "banking_payoff", {"account": account})


@tool(description="Review an own-account transfer without submitting it.")
async def banking_review_transfer(source: str, destination: str, amount: str,
                                  currency: str, context: ToolContext = None) -> ToolResult:
    try:
        host = await _host(context)
        async with host.lock:
            return await _review_locked(host, context, source, destination, amount, currency)
    except Exception:
        await deliver_reply(context, REVIEW_UNAVAILABLE_TEXT)
        return ToolResult(llm_response={"state": "refused", "reason": "review_unavailable"})


async def _review_locked(host, context, source, destination, amount, currency):
    if delivery_pending():
        return ToolResult(llm_response={"state": "review_delivered"})
    if host.pending:
        await asyncio.to_thread(host.client.cancel, host.session, host.pending["review"])
        host.pending = None
    result = _payload(await host.client.call(host.session, "banking_review_transfer",
        {"source": source, "destination": destination, "amount": amount, "currency": currency}))
    if result.get("state") == "pending" and isinstance(result.get("review"), str):
        # A draft is not confirmable until its canonical text was delivered.
        try:
            await context.send(f"Review: transfer {result['currency']} {result['amount']} from "
                               f"{result['source']} to {result['destination']}. "
                               "To submit exactly this transfer, say confirm transfer next. "
                               "Anything else cancels this review.")
            if context.is_cancelled:
                raise asyncio.CancelledError()
        except (Exception, asyncio.CancelledError):
            host.pending = None
            try:
                await asyncio.shield(asyncio.to_thread(host.client.cancel, host.session, result["review"]))
            except (Exception, asyncio.CancelledError):
                pass
            raise
        host.pending = result
        host.pending_turn = len(_users(context))
    if host.pending:
        host.last_submit_state = None
        remember_delivery()
        return ToolResult(llm_response={"state": "review_delivered"})
    if result.get("state") == "refused":
        # No review was made: the host says so, so no retry advice is improvised. An
        # unknown earlier outcome outranks every other reason (a stale verification
        # may be checked first), so the retained status is read before any advice.
        reason = result.get("reason")
        text = _review_refusal_text(reason)
        if reason != "outcome_unresolved" and await _unresolved(host):
            text = UNKNOWN_OUTCOME_TEXT
        await deliver_reply(context, text)
    return ToolResult(llm_response=_safe(result))


@tool(description="Submit only after the next raw user turn says exactly confirm transfer.")
async def banking_submit_transfer(context: ToolContext = None) -> ToolResult:
    dispatched = False
    try:
        host = await _host(context, create=False)
        native = current_turn_context()
        await host.lock.acquire()
    except Exception:
        await deliver_reply(context, "The current transfer review is unavailable. Check the original transfer status before making another request.")
        return ToolResult(llm_response={"state": "refused", "reason": "host_or_confirmation_unavailable"})
    try:
        if (not host.pending or context.is_cancelled
                or len(_users(context)) != host.pending_turn + 1
                or not _is_confirmation(native.turn.text)):
            if await _unresolved(host):
                await deliver_reply(context, UNKNOWN_OUTCOME_TEXT)
                return ToolResult(llm_response={"state": "unknown", "reason": "no_retry_check_original_status"})
            await deliver_reply(context, NO_ACTIVE_REVIEW_TEXT)
            return ToolResult(llm_response={"state": "refused", "reason": "new_review_required"})
        review = host.pending
        host.pending = None  # consume local permission before the first effectful call
        exact = {key: review[key] for key in ("source", "destination", "amount", "currency")}
        await asyncio.to_thread(host.client.confirm, host.session, review["review"], exact)
        if context.is_cancelled:
            await asyncio.to_thread(host.client.cancel, host.session, review["review"])
            return ToolResult(llm_response={"state": "refused", "reason": "interrupted"})
        dispatched = True
        try:
            result = await asyncio.to_thread(host.client.submit, host.session, review["review"])
        except HostRefused as refused:
            # The host refused before any send (for example an unresolved earlier
            # outcome), so nothing was dispatched.
            return ToolResult(llm_response={"state": "refused", "reason": refused.reason})
        if result.get("state") not in {"accepted", "refused", "unknown"}:
            raise ValueError("unresolved_submit_outcome")
        host.last_submit_state = result["state"]
        if result.get("state") == "accepted":
            await deliver_reply(context, "The transfer request was accepted. Accepted does not mean posted.")
        return ToolResult(llm_response=_safe(result))
    except Exception:
        if dispatched:
            host.last_submit_state = "unknown"
        # A failure after dispatch must never invite an automatic retry.
        return ToolResult(llm_response=(
            {"state": "unknown", "reason": "no_retry_check_original_status"} if dispatched
            else {"state": "refused", "reason": "host_or_confirmation_unavailable"}))
    finally:
        host.lock.release()


@tool(description="Check the latest retained transfer outcome without a new submission.")
async def banking_transfer_status(context: ToolContext = None) -> ToolResult:
    return await _read(context, "banking_transfer_status", {})
