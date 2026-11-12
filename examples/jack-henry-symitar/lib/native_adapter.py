# SPDX-License-Identifier: MIT
"""Native Rasa bindings; identity, raw turns and delivery come from the SDK.

Exactly seven tools are exported. The private native adapter consumes actual
channel events before tool execution; no submit/confirm tool exists.
The model cannot supply the host capability, session, review handle or raw turn.
"""
import asyncio
from dataclasses import dataclass,field
import os
import time
import math

from pydantic import StrictStr
from rasa.mantle.orchestration.turn_context import current_turn_context
from rasa.mantle.tools.decorator import ToolContext,tool
from rasa.mantle.tools.result import ToolResult
from lib.host_client import HostClient


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


async def _recover(conversation):
    if conversation.pending_request:
        previous=await asyncio.to_thread(conversation.client.control,'recover',
            credential=conversation.pending_request['credential'],number=conversation.pending_request['number'])
        conversation.outcome=previous
        conversation.pending_request={}


async def _record(conversation,text,message_id=None,observed_at=None):
    await _recover(conversation)
    if message_id and message_id in conversation.message_ids:return
    number=conversation.observed+1
    request=dict(credential=conversation.credential,number=number,text=text,
        observed_at=time.monotonic() if observed_at is None else observed_at,
        revoked=_norm(text) in {'reset','logout','log out','switch user'},cancelled=False)
    conversation.observed=number
    conversation.pending_request=request
    if message_id:conversation.message_ids.add(message_id)
    result=await asyncio.to_thread(conversation.client.control,'turn',**request)
    conversation.pending_request={}
    if result.get('state')!='observed' or not conversation.outcome:conversation.outcome=result


async def incoming(payload):
    """Private channel adapter helper, never a model-discovered tool."""
    conversation=await _conversation_for(payload.sender_id)
    async with conversation.lock:
        await _record(conversation,payload.text,payload.message_id)
    return payload


async def _conversation(context):
    if context is None or context.is_cancelled:raise ValueError('channel_unavailable')
    conversation=await _conversation_for(current_turn_context().sender_id)
    return conversation


async def _observe(conversation,context):
    if context.is_cancelled:raise ValueError('channel_cancelled')
    native=current_turn_context()
    users=_users(context)
    if not users or native.turn.text!=users[-1].get('text') or len(users)<conversation.observed:
        raise ValueError('current_raw_turn_required')
    await _recover(conversation)
    unseen=users[conversation.observed:]
    old_confirmation=len(unseen)>1 and any(_norm(event.get('text','')) in {'yes','confirm','confirmed','confirm transfer'} for event in unseen[:-1])
    if len(unseen)>1:
        # An older yes must never become a late submission merely because the
        # model did not call a tool on that historical turn.
        await asyncio.to_thread(conversation.client.control,'cancel',credential=conversation.credential)
    for event in unseen:
        stamp=event.get('timestamp')
        if type(stamp) not in {int,float} or not math.isfinite(stamp) or stamp>time.time()+1:
            raise ValueError('trusted_event_time_required')
        observed_at=time.monotonic()-max(0,time.time()-stamp)
        await _record(conversation,event['text'],observed_at=observed_at)
    if old_confirmation:
        conversation.outcome={}
        await context.send('The older confirmation was not used. No new transfer was sent.')
        return {'state':'not_submitted','historical_confirmation_refused':True}
    result=conversation.outcome
    state=result.get('state')
    if state=='reset':raise ValueError('session_reset')
    if state in {'accepted','rejected','unknown','not_dispatched'}:
        text=('The earlier request was not dispatched. A new transfer requires a new review.' if state=='not_dispatched' else
              'The fictional transfer was accepted. This is not a real payment.' if state=='accepted' else
              'The transfer outcome is unknown. Do not retry.' if state=='unknown' else 'The fictional transfer was rejected.')
        await context.send(text)
        conversation.outcome={}
    return result


async def _call(context,name,args):
    conversation=None
    try:
        conversation=await _conversation(context)
        async with conversation.lock:
            observed=await _observe(conversation,context)
            result=await conversation.client.call(conversation.credential,name,args)
            if observed.get('historical_confirmation_refused'):
                result=dict(result,historical_confirmation='not_used',instruction='The older confirmation was not used. No new transfer was sent. Do not describe this review as accepted.')
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
        if conversation is not None and conversation.pending_request:
            return ToolResult(llm_response={'state':'unknown','reason':'A prior transfer may have occurred. Do not retry or request another transfer. Check local status when the host returns.'})
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


@tool(description='Read the current review outcome, or the last recorded outcome if there is no current review. Use after yes; never retry.')
async def banking_transfer_status(context: ToolContext=None)->ToolResult:
    return await _call(context,'banking_transfer_status',{})
