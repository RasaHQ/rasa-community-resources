"""Rasa-owned host glue. Routing IDs are not real customer authentication.

Only a private, single-user teaching host chooses the fixed fictional caller.
Model tools never receive the host capability, MCP credential or review handle.
"""
import asyncio
from dataclasses import dataclass, field
import json
import os
import re

from rasa.mantle.orchestration.turn_context import current_turn_context
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult


@dataclass
class _Conversation:
    origin: str = field(repr=False)
    client: object = field(repr=False)
    session: object = field(repr=False)
    pending: dict | None = field(default=None, repr=False)
    observed_turn: int = 0
    pending_turn: int = 0
    last_review: str | None = field(default=None, repr=False)


@dataclass
class _OutcomeHold:
    client: object = field(repr=False)
    session: object = field(repr=False)
    review: str = field(repr=False)


_conversations = {}
# All conversations on this private teaching host share the fixed demo-A
# principal. A new routing ID or session cannot erase an uncertain dispatch.
# This is process-lifetime state, not a durable payment journal.
_outcome_holds = {}
_CONFIRM = 'confirm transfer'


def _is_confirmation(text):
    return re.fullmatch(r'confirm\s+transfer[.!]?', text.strip().casefold()) is not None


def _is_reset(text):
    normalized = ' '.join(text.strip().casefold().rstrip('.!?').split())
    return normalized in {'reset', 'logout', 'log out', 'switch user'}


def _users(context):
    return [event.as_dict() for event in context.events
            if event.as_dict().get('event') == 'user']


def _payload(result):
    if result.isError:
        return {'state': 'refused', 'reason': 'service_refused'}
    data = result.structuredContent
    if data is None:
        data = json.loads(result.content[0].text)
    if not isinstance(data, dict):
        raise ValueError('invalid_result')
    return data


def _safe(data):
    # Never forward generic transport errors, capabilities or host handles.
    allowed = {'state', 'reason', 'fixture', 'accounts', 'amount', 'currency',
               'source', 'destination', 'balance_type', 'entries', 'page', 'more',
               'due_date', 'as_of'}
    return {key: value for key, value in data.items() if key in allowed}


async def _host(context, *, create=True):
    native = current_turn_context()
    origin = os.environ.get('BANKING_HOST_URL', '')
    capability = os.environ.get('BANKING_HOST_CAPABILITY', '')
    if not origin or len(capability) < 32:
        raise ValueError('host_unavailable')
    # No routing identifier or caller supplied as a tool/model argument.
    key = (origin, native.sender_id)
    users = _users(context)
    conversation = _conversations.get(key)
    if conversation is None:
        if not create:
            raise ValueError('review_unavailable')
        from .client import HostClient
        client = HostClient(origin, capability)
        session = await asyncio.to_thread(client.open_session, 'demo-A')
        conversation = _Conversation(origin, client, session, observed_turn=max(0, len(users) - 1))
        _conversations[key] = conversation
    text = native.turn.text.strip().lower()
    # A model may choose no tool on logout. Observe every raw user turn since
    # the last host operation before allowing any later protected operation.
    unseen = users[conversation.observed_turn:]
    conversation.observed_turn = len(users)
    if any(_is_reset(str(event.get('text', ''))) for event in unseen):
        try:
            await asyncio.to_thread(conversation.client.reset, conversation.session)
        finally:
            _conversations.pop(key, None)
        raise ValueError('session_reset')
    if conversation.pending and len(users) > conversation.pending_turn:
        # Only the immediately following exact phrase can confirm. A question,
        # denial, reset, changed request or intervening turn invalidates consent.
        if len(users) != conversation.pending_turn + 1 or not _is_confirmation(text):
            await asyncio.to_thread(conversation.client.cancel, conversation.session,
                                    conversation.pending['review'])
            conversation.pending = None
    return conversation


async def _read(context, name, arguments):
    try:
        host = await _host(context)
        return ToolResult(llm_response=_safe(_payload(await host.client.call(host.session, name, arguments))))
    except Exception:
        return ToolResult(llm_response={'state': 'unavailable', 'reason': 'host_or_service_unavailable'})


@tool(description='List only permitted fictional account aliases.')
async def banking_accounts(context: ToolContext = None) -> ToolResult:
    return await _read(context, 'banking_accounts', {})


@tool(description='Read the supplied balance for a permitted fictional account.')
async def banking_balance(account: str, balance_type: str = 'available',
                          context: ToolContext = None) -> ToolResult:
    return await _read(context, 'banking_balance', {'account': account, 'balance_type': balance_type})


@tool(description='Read supported history, or report that history is unsupported.')
async def banking_history(account: str, page: int = 1, context: ToolContext = None) -> ToolResult:
    return await _read(context, 'banking_history', {'account': account, 'page': page})


@tool(description='Read a supplied next payment, never calculate it from principal.')
async def banking_loan_payment(account: str, context: ToolContext = None) -> ToolResult:
    return await _read(context, 'banking_loan_payment', {'account': account})


@tool(description='Request a supplied dated payoff; unsupported dates must stay unsupported.')
async def banking_payoff(account: str, date: str, context: ToolContext = None) -> ToolResult:
    return await _read(context, 'banking_payoff', {'account': account, 'date': date})


@tool(description='Review an own-account transfer without submitting it.')
async def banking_review_transfer(source: str, destination: str, amount: str,
                                  currency: str, context: ToolContext = None) -> ToolResult:
    try:
        host = await _host(context)
        if host.origin in _outcome_holds:
            return ToolResult(llm_response={'state': 'refused', 'reason': 'outcome_unresolved'})
        if host.pending:
            await asyncio.to_thread(host.client.cancel, host.session, host.pending['review'])
            host.pending = None
        result = _payload(await host.client.call(host.session, 'banking_review_transfer',
            {'source': source, 'destination': destination, 'amount': amount, 'currency': currency}))
        if result.get('state') == 'pending' and isinstance(result.get('review'), str):
            host.last_review = result['review']
            # A draft is not confirmable until its canonical output has actually
            # been delivered. Preserve the private handle for status/cancellation.
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
                    await asyncio.shield(asyncio.to_thread(host.client.cancel, host.session,
                                                           result['review']))
                except (Exception, asyncio.CancelledError):
                    pass  # No local permission exists even if draft cancellation is uncertain.
                raise
            host.pending = result
            host.pending_turn = len(_users(context))
        return ToolResult(llm_response=_safe(result))
    except Exception:
        return ToolResult(llm_response={'state': 'refused', 'reason': 'review_unavailable'})


@tool(description='Submit only after the next raw user turn says exactly confirm transfer.')
async def banking_submit_transfer(context: ToolContext = None) -> ToolResult:
    dispatched = False
    try:
        host = await _host(context, create=False)
        native = current_turn_context()
        if host.origin in _outcome_holds:
            host.pending = None
            return ToolResult(llm_response={'state': 'refused', 'reason': 'outcome_unresolved'})
        if (not host.pending or context.is_cancelled
                or len(_users(context)) != host.pending_turn + 1
                or not _is_confirmation(native.turn.text)):
            return ToolResult(llm_response={'state': 'refused', 'reason': 'confirmation_required'})
        review = host.pending
        # Consume local permission before the first effectful host call too.
        host.pending = None
        exact = {key: review[key] for key in ('source', 'destination', 'amount', 'currency')}
        await asyncio.to_thread(host.client.confirm, host.session, review['review'], exact)
        if context.is_cancelled:
            await asyncio.to_thread(host.client.cancel, host.session, review['review'])
            return ToolResult(llm_response={'state': 'refused', 'reason': 'interrupted'})
        # Another conversation could have become uncertain while confirm
        # awaited its host round trip. Check again before dispatch, then install
        # our hold synchronously before the first network await.
        if host.origin in _outcome_holds:
            return ToolResult(llm_response={'state': 'refused', 'reason': 'outcome_unresolved'})
        held = _OutcomeHold(host.client, host.session, review['review'])
        _outcome_holds[host.origin] = held
        dispatched = True
        reply = await host.client.call(host.session, 'banking_submit_transfer',
                                       {'review': review['review']})
        if reply.isError:
            raise ValueError('uncertain_submit_reply')
        result = _payload(reply)
        from .contract import validate
        validate('banking_submit_transfer', 'output', result)
        if result.get('state') not in {'queued', 'accepted', 'posted', 'refused', 'canceled'}:
            raise ValueError('unresolved_submit_outcome')
        # Only this original call's validated known response releases its hold.
        # A later status read or a reset is not a reconciliation capability.
        if _outcome_holds.get(host.origin) is held:
            del _outcome_holds[host.origin]
        return ToolResult(llm_response=_safe(result))
    except Exception:
        # A post-dispatch network failure must never invite an automatic retry.
        return ToolResult(llm_response=({'state': 'unknown', 'reason': 'no_retry_check_original_status'}
                                        if dispatched else {'state': 'refused', 'reason': 'host_or_confirmation_unavailable'}))


@tool(description='Check the original retained transfer outcome without a new submission.')
async def banking_transfer_status(context: ToolContext = None) -> ToolResult:
    try:
        host = await _host(context, create=False)
        held = _outcome_holds.get(host.origin)
        identifier = held.review if held else host.last_review
        if not identifier:
            raise ValueError('review_unavailable')
        client, session = (held.client, held.session) if held else (host.client, host.session)
        return ToolResult(llm_response=_safe(_payload(await client.call(
            session, 'banking_transfer_status', {'review': identifier}))))
    except Exception:
        return ToolResult(llm_response={'state': 'unavailable', 'reason': 'status_unavailable'})
