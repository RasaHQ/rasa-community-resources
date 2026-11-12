# SPDX-License-Identifier: MIT
"""Native Rasa bindings; identity, raw turns and delivery come from the SDK.

Exactly seven tools are exported. The private per-turn observer consumes actual
channel confirmation before tool execution; no submit/confirm tool exists.
The model cannot supply the host capability, session, review handle or raw turn.
"""
import asyncio
from dataclasses import dataclass,field
import os
import time

from pydantic import StrictStr
from rasa.mantle.orchestration.turn_context import current_turn_context
from rasa.mantle.tools.decorator import ToolContext,tool
from rasa.mantle.tools.result import ToolResult
from local_transport import HostClient


@dataclass
class Conversation:
    client: object=field(repr=False)
    credential: StrictStr=field(repr=False)
    observed: int=0
    last_seen: float=field(default_factory=time.monotonic)
    pending_request: dict=field(default_factory=dict,repr=False)
    message_ids: set=field(default_factory=set,repr=False)
    outcome: dict=field(default_factory=dict,repr=False)
    lock: object=field(default_factory=asyncio.Lock,repr=False)


_conversations={}
_open_lock=asyncio.Lock()


def _users(context):
    return [event.as_dict() for event in context.events if event.as_dict().get('event')=='user']


def _norm(text):return ' '.join(text.strip().casefold().rstrip('.!?').split())


async def _conversation_for(sender):
    url=os.environ.get('SYMITAR_HOST_URL','')
    capability=os.environ.get('SYMITAR_HOST_CAPABILITY','')
    if not url or len(capability)<32:raise ValueError('host_unavailable')
    key=(url,sender)
    async with _open_lock:
        for old, existing in list(_conversations.items()):
            if time.monotonic()-existing.last_seen>=300 and not existing.lock.locked():
                del _conversations[old]
        conversation=_conversations.get(key)
        if conversation is None:
            client=HostClient(url,capability)
            opened=await asyncio.to_thread(client.control,'open',sender=str(sender))
            conversation=Conversation(client,opened['credential'])
            _conversations[key]=conversation
    conversation.last_seen=time.monotonic()
    return conversation


async def incoming(payload):
    """Awaited only by the SDK incoming-message modifier, never a model tool."""
    conversation=await _conversation_for(payload.sender_id)
    async with conversation.lock:
        # Recover the exact previous private request before observing new input.
        # A lost HTTP reply never rebinds its confirmation to a later raw turn.
        if conversation.pending_request:
            previous=await asyncio.to_thread(conversation.client.control,'turn',**conversation.pending_request)
            conversation.outcome=previous
            conversation.pending_request={}
        if payload.message_id and payload.message_id in conversation.message_ids:return payload
        number=conversation.observed+1
        request=dict(credential=conversation.credential,number=number,text=payload.text,observed_at=time.monotonic(),
            revoked=_norm(payload.text) in {'reset','logout','log out','switch user'},cancelled=False)
        conversation.observed=number
        conversation.pending_request=request
        if payload.message_id:conversation.message_ids.add(payload.message_id)
        result=await asyncio.to_thread(conversation.client.control,'turn',**request)
        conversation.pending_request={}
        if result.get('state')!='observed' or not conversation.outcome:
            conversation.outcome=result
    return payload


async def _conversation(context):
    if context is None or context.is_cancelled:raise ValueError('channel_unavailable')
    conversation=await _conversation_for(current_turn_context().sender_id)
    if not conversation.observed:raise ValueError('incoming_hook_required')
    return conversation


async def _observe(conversation,context):
    if context.is_cancelled:raise ValueError('channel_cancelled')
    result=conversation.outcome
    state=result.get('state')
    if state=='reset':raise ValueError('session_reset')
    if state in {'accepted','rejected','unknown'}:
        text=('The fictional transfer was accepted. This is not a real payment.' if state=='accepted' else
              'The transfer outcome is unknown. Do not retry.' if state=='unknown' else 'The fictional transfer was rejected.')
        await context.send(text)
        conversation.outcome={}
    return result


async def _call(context,name,args):
    try:
        conversation=await _conversation(context)
        async with conversation.lock:
            await _observe(conversation,context)
            result=await conversation.client.call(conversation.credential,name,args)
            if name=='banking_review_transfer' and result.get('state')=='review_pending_delivery':
                review=await asyncio.to_thread(conversation.client.control,'review',credential=conversation.credential)
                try:
                    await context.send(f"Review: transfer {review['currency']} {review['amount']} from {review['source']} to {review['destination']}. Say yes or confirm transfer next to submit exactly this fictional transfer. Anything else cancels it.")
                    if context.is_cancelled:raise asyncio.CancelledError()
                    await asyncio.to_thread(conversation.client.control,'delivered',credential=conversation.credential,review=review['review'])
                except (Exception,asyncio.CancelledError):
                    try:await asyncio.shield(asyncio.to_thread(conversation.client.control,'cancel',credential=conversation.credential))
                    except (Exception,asyncio.CancelledError):pass
                    raise
                return ToolResult(llm_response={'state':'review_delivered','instruction':'The exact review was delivered. Add no question or extra review.'})
            return ToolResult(llm_response=result)
    except (Exception,asyncio.CancelledError):
        return ToolResult(llm_response={'state':'unavailable','reason':'host_or_service_refused; say verify me if simulated assurance expired'})


@tool(description='List permitted fictional deposit and loan aliases. No customer identifiers.')
async def banking_accounts(context: ToolContext=None)->ToolResult:
    return await _call(context,'banking_accounts',{})


@tool(description='Read available funds for one permitted deposit account alias.')
async def banking_balance(account: StrictStr,context: ToolContext=None)->ToolResult:
    return await _call(context,'banking_balance',{'account':account})


@tool(description='Read at most twenty fictional transactions in an explicit inclusive ISO date range.')
async def banking_history(account: StrictStr,start_date: StrictStr,end_date: StrictStr,context: ToolContext=None)->ToolResult:
    return await _call(context,'banking_history',{'account':account,'start_date':start_date,'end_date':end_date})


@tool(description='Read current loan payment due and next due date as separate facts; no regular/minimum fallback.')
async def banking_loan_payment(loan: StrictStr,context: ToolContext=None)->ToolResult:
    return await _call(context,'banking_loan_payment',{'loan':loan})


@tool(description='Request a fictional dated payoff quote for a loan alias and ISO date; never make a payment.')
async def banking_payoff(loan: StrictStr,payoff_date: StrictStr,context: ToolContext=None)->ToolResult:
    return await _call(context,'banking_payoff',{'loan':loan,'payoff_date':payoff_date})


@tool(description='Propose a permitted own-account transfer review, never submit it; amount must be a decimal string with two digits.')
async def banking_review_transfer(source: StrictStr,destination: StrictStr,amount: StrictStr,context: ToolContext=None)->ToolResult:
    return await _call(context,'banking_review_transfer',{'source':source,'destination':destination,'amount':amount})


@tool(description='Read the latest retained local transfer outcome; use after the caller says yes or confirm transfer. Never retry.')
async def banking_transfer_status(context: ToolContext=None)->ToolResult:
    return await _call(context,'banking_transfer_status',{})
