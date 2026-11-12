# SPDX-License-Identifier: MIT
"""Private teaching host: authority, review delivery and one physical send.

Routing is a fictional identity simulator, never bank authentication. The Rasa
adapter supplies actual channel turns through the private control interface.
None of these control operations is an MCP/model tool.
"""
from dataclasses import dataclass, field, replace
from decimal import Decimal
import asyncio
import math
import secrets
import threading
import time
import uuid

from host import HostPolicy, Refused, Session, TransferIntent
from journal import JournalRefused
from vendor_client import ClientError, ErrorCode


def norm(text):
    return ' '.join(text.strip().casefold().rstrip('.!?').split())


@dataclass
class Binding:
    session: Session
    policy: HostPolicy
    turn: int = 0
    pending: object = None
    last_seen: float = 0
    last_result: dict = field(default_factory=dict)
    current_transfer_state: str | None = None


class ConversationHost:
    def __init__(self, gateway, credential):
        self.gateway, self.credential = gateway, credential

    def call(self, name, arguments):
        return self.gateway.call(self.credential, name, arguments)


class Gateway:
    def __init__(self, client, journal, fixture, *, clock=time.monotonic):
        self.client, self.journal, self.fixture, self.clock = client, journal, fixture, clock
        self.sessions = {}
        self._lock = threading.RLock()
        if fixture.get('currency') != 'USD':
            raise Refused('missing_currency_context')
        self.shares = {item['alias']: item['id'] for item in fixture['shares']}
        self.loans = {item['alias']: item['id'] for item in fixture['loans']}
        self.principal = 'fictional-customer'

    def resolve(self, credential):
        with self._lock:
            if credential not in self.sessions:
                raise Refused('session_unavailable')
        return ConversationHost(self, credential)

    def _binding(self, credential):
        if not isinstance(credential, str) or credential not in self.sessions:
            raise Refused('session_unavailable')
        return self.sessions[credential]

    def _cancel(self, binding):
        if binding.pending is not None:binding.current_transfer_state='not_submitted'
        binding.policy.cancel()
        binding.pending = None

    def control(self, action, data):
        with self._lock:
            if type(data) is not dict:
                raise Refused('invalid_control')
            if action == 'open':
                for old, existing in list(self.sessions.items()):
                    if self.clock()-existing.last_seen>=300:
                        self._cancel(existing)
                        del self.sessions[old]
                if set(data) != {'sender'} or not isinstance(data['sender'], str) or not 1 <= len(data['sender']) <= 128 or len(self.sessions) >= 128:
                    raise Refused('invalid_routing_context')
                capability = secrets.token_urlsafe(32)
                session = Session(self.principal, uuid.uuid4().hex,
                    frozenset(self.shares) | frozenset(self.loans), 'USD', self.clock(), data['sender'])
                self.sessions[capability] = Binding(session, HostPolicy(session, self.clock),last_seen=self.clock())
                return {'credential': capability}
            binding = self._binding(data.get('credential'))
            if action == 'recover':
                if set(data) != {'credential','number'} or type(data['number']) is not int or data['number']<1:
                    raise Refused('invalid_recovery')
                if data['number']<=binding.turn:
                    return dict(binding.last_result) if data['number']==binding.turn else {'state':'superseded'}
                # Atomically retire an unseen confirmation. Even a delayed
                # original packet for this number is now a cached no-effect
                # result, never the first physical dispatch.
                self._cancel(binding)
                binding.turn=data['number']
                binding.last_result={'state':'not_dispatched','reason':'unseen_private_turn_retired; new_review_required'}
                return dict(binding.last_result)
            if action == 'turn':
                if set(data)-{'observed_at'} != {'credential','number','text','revoked','cancelled'} or type(data['number']) is not int or data['number'] < 1 or type(data['text']) is not str or len(data['text']) > 8192 or type(data['revoked']) is not bool or type(data['cancelled']) is not bool:
                    raise Refused('invalid_channel_turn')
                observed=data.get('observed_at',self.clock())
                if type(observed) not in {int,float} or not math.isfinite(observed) or observed>self.clock():
                    raise Refused('invalid_channel_event_time')
                if data['number'] <= binding.turn:
                    return dict(binding.last_result) if data['number']==binding.turn else {'state':'observed'}
                binding.turn = data['number']
                binding.last_seen = self.clock()
                result = self._turn(binding,data)
                binding.last_result = dict(result)
                return result
            if action == 'review':
                if set(data) != {'credential'} or binding.pending is None:
                    raise Refused('review_unavailable')
                intent = binding.pending.intent
                return {'review':binding.pending.operation_id,'source':intent.source,
                        'destination':intent.destination,'amount':format(Decimal(intent.amount),'.2f'),'currency':intent.currency}
            if action == 'delivered':
                if set(data) != {'credential','review'} or binding.pending is None or data['review'] != binding.pending.operation_id:
                    self._cancel(binding)
                    raise Refused('review_unavailable')
                binding.policy.delivered(binding.pending)
                binding.current_transfer_state='review_delivered'
                return {'state':'review_delivered'}
            if action == 'cancel':
                if set(data) != {'credential'}:
                    raise Refused('invalid_control')
                self._cancel(binding)
                return {'state':'review_cancelled'}
            raise Refused('unknown_control')

    def _turn(self,binding,data):
        text = norm(data['text'])
        if data['cancelled'] or data['revoked'] or text in {'reset','logout','log out','switch user'}:
            self._cancel(binding)
            binding.session = replace(binding.session, revision=uuid.uuid4().hex, assured_at=self.clock()-301)
            if text not in {'verify me','verify my identity'}:
                return {'state':'reset'}
        if text in {'verify me','verify my identity'}:
            self._cancel(binding)
            binding.session = replace(binding.session, revision=uuid.uuid4().hex, assured_at=data.get('observed_at',self.clock()))
            return {'state':'simulated_assurance_refreshed' if self.clock()-binding.session.assured_at<300 else 'simulated_assurance_expired'}
        if binding.pending is not None:
            pending = binding.pending
            binding.pending = None
            try:
                permit = binding.policy.confirm(binding.session, pending.intent,
                    data['text'].strip().casefold().rstrip('.!?'), binding.turn)
            except Refused:
                binding.current_transfer_state='not_submitted'
                return {'state':'review_cancelled'}
            result=self._dispatch(binding,permit)
            binding.current_transfer_state=result['state']
            return result
        return {'state':'observed'}

    def _dispatch(self, binding, permit):
        # HostPolicy rechecked authority, exact review and immediately next raw
        # user turn. There is no model-supplied confirmation or session field.
        try:
            self.journal.reserve(self.principal, permit.operation_id, self.journal.epoch)
        except JournalRefused:
            return {'state':'refused','reason':'unresolved_or_unavailable_journal'}
        intent = permit.intent
        body = {'donor':{'accountNumber':self.fixture['account_number'],'shareId':self.shares[intent.source]},
                'recipient':{'accountNumber':self.fixture['account_number'],'shareId':self.shares[intent.destination]},
                'amount':format(Decimal(intent.amount),'.2f')}
        outcome = 'unknown'
        try:
            result = asyncio.run(self.client.call('postTransfer',body))
            outcome = 'accepted' if isinstance(result.data,dict) and result.data.get('status') == 'success' else 'unknown'
        except ClientError as error:
            if error.code in {ErrorCode.INVALID_REQUEST,ErrorCode.VENDOR_REJECTED}:
                outcome = 'rejected'
        except Exception:
            pass
        try:
            self.journal.result(permit.operation_id,outcome)
        except JournalRefused:
            outcome = 'unknown'
        return {'state':outcome,'source':intent.source,'destination':intent.destination,
                'amount':format(Decimal(intent.amount),'.2f'),'currency':intent.currency}

    def _read(self, binding, operation, body, alias):
        binding.policy.require_read(binding.session,alias)
        return asyncio.run(self.client.call(operation,body)).data

    @staticmethod
    def _money(value):
        if not isinstance(value,str):return None
        try:
            amount=Decimal(value)
            return format(amount,'.2f') if amount.is_finite() and amount == amount.quantize(Decimal('.01')) else None
        except Exception:return None

    def call(self, credential, name, args):
        # The protocol layer has already checked raw argument types/keys. The
        # host enforces account scope and freshness independently every time.
        with self._lock:
            binding = self._binding(credential)
            if name == 'banking_transfer_status':
                binding.policy.require_read(binding.session,'checking')
                latest=self.journal.latest(self.principal)
                if self.journal.held(self.principal):
                    return {'state':latest or 'unknown','reason':'unresolved_transfer_no_retry'}
                state=binding.current_transfer_state or latest or 'none'
                return {'state':state}
            if name == 'banking_review_transfer':
                self._cancel(binding)
                binding.current_transfer_state='not_submitted'
                if self.journal.held(self.principal):
                    return {'state':'refused','reason':'unresolved_transfer_no_retry'}
                if args['source'] not in self.shares or args['destination'] not in self.shares:
                    raise Refused('outside_scope')
                intent=TransferIntent(args['source'],args['destination'],args['amount'],binding.session.currency)
                binding.pending=binding.policy.review(binding.session,intent,binding.turn)
                binding.current_transfer_state='review_pending_delivery'
                return {'state':'review_pending_delivery','source':intent.source,'destination':intent.destination,
                        'amount':format(Decimal(intent.amount),'.2f'),'currency':intent.currency}
            number=self.fixture['account_number']
            if name == 'banking_accounts':
                self._read(binding,'findAccountBy',{'accountNumber':number},'checking')
                return {'state':'available','accounts':list(self.shares),'loans':list(self.loans),'currency':'USD'}
            if name == 'banking_balance':
                alias=args['account']
                if alias not in self.shares:raise Refused('outside_scope')
                data=self._read(binding,'findAccountByWithBalances',{'accountNumber':number},alias)
                row=next((r for r in data.get('shares',[]) if r.get('shareId')==self.shares[alias]),{})
                amount=self._money(row.get('availableBalance'))
                return {'state':'available' if amount is not None else 'unavailable','account':alias,'amount':amount,'currency':'USD','balance_type':'available'}
            if name == 'banking_history':
                alias=args['account']
                if alias not in self.shares:raise Refused('outside_scope')
                data=self._read(binding,'searchAccountTransactions',{'accountNumber':number,'shareId':self.shares[alias],
                    'startDate':args['start_date'],'endDate':args['end_date'],'count':20,'offset':'0'},alias)
                entries=[{'date':row.get('postDate'),'description':row.get('description'),'amount':self._money(row.get('amount'))} for row in data.get('transactions',[])]
                return {'state':'available','account':alias,'entries':entries,'more':bool(data['paging']['nextOffset']),'currency':'USD'}
            alias=args.get('loan')
            if alias not in self.loans:raise Refused('outside_scope')
            if name == 'banking_loan_payment':
                rows=self._read(binding,'searchLoans',{'accountNumber':number,'loanId':self.loans[alias]},alias)
                row=next((r for r in rows if r.get('loanId')==self.loans[alias]),{})
                return {'state':'available' if row else 'unavailable','loan':alias,'current_payment_due':self._money(row.get('paymentDue')),
                        'next_due_date':row.get('dueDate'),'currency':'USD','meaning':'current payment due and next due date are separate facts'}
            if name == 'banking_payoff':
                data=self._read(binding,'calculateLoanPayoffQuote',{'accountNumber':number,'loanId':self.loans[alias],'payoffDate':args['payoff_date']},alias)
                return {'state':'available','loan':alias,'amount':self._money(data.get('totalPayoffAmount')),'as_of':data.get('payoffDate'),'currency':'USD','scope':'dated fictional quote, not a payment'}
            raise Refused('unsupported_tool')
