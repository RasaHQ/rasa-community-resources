# SPDX-License-Identifier: MIT
"""Trusted host service: the example's own host policy and journal, plus the SOAP client.

It composes the reviewed `host.HostPolicy` (assurance, review, next-turn
confirmation) and `journal.Journal` (durable pre-send marker, principal-wide
hold) that sit next to this package. None of these methods is an MCP tool.
A fabricated context is not authentication: this is a fictional teaching host.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from threading import RLock
import time
import uuid

from host import HostPolicy, Refused, Session, TransferIntent
from journal import JournalRefused

from .client import SilverLakeClient, Unavailable, UnknownOutcome


def _spoken_date(iso: str) -> str:
    from datetime import date
    try:
        value = date.fromisoformat(iso)
    except ValueError:
        return "unavailable"
    return value.strftime("%B ") + str(value.day) + value.strftime(", %Y")


class _Conversation:
    def __init__(self, session: Session, policy: HostPolicy, accounts: dict, customer: str):
        self.session, self.policy, self.accounts, self.customer = session, policy, accounts, customer
        self.draft = None
        self.cursors = {}


class SilverLakeService:
    def __init__(self, client: SilverLakeClient, journal, permissions: dict, *, clock=time.monotonic):
        self.client, self.journal, self.permissions, self.clock = client, journal, permissions, clock
        self._conversations = {}
        self._outcomes = {}  # principal -> latest local outcome (journal keeps the durable hold)
        self._lock = RLock()

    # -- host-only ---------------------------------------------------------------
    def open_session(self, caller: str) -> str:
        if caller not in self.permissions:
            raise Refused("unknown_simulated_caller")
        spec = self.permissions[caller]
        try:
            related = set(self.client.accounts(spec["customer"]))
        except (Unavailable, UnknownOutcome):
            raise Refused("service_unavailable") from None
        # A search result never authorizes by itself: intersect with private permissions.
        accounts = {alias: (ident, kind) for alias, ident, kind in spec["accounts"] if (ident, kind) in related}
        if not accounts:
            raise Refused("no_permitted_accounts")
        session = Session(principal=caller, revision=uuid.uuid4().hex, aliases=frozenset(accounts),
                          currency="USD", assured_at=self.clock(), conversation=uuid.uuid4().hex)
        with self._lock:
            if len(self._conversations) >= 32:
                raise Refused("session_limit")
            token = uuid.uuid4().hex
            self._conversations[token] = _Conversation(session, HostPolicy(session, self.clock), accounts,
                                                       spec["customer"])
        return token

    def _get(self, token) -> _Conversation:
        conversation = self._conversations.get(token)
        if conversation is None:
            raise Refused("stale_session")
        return conversation

    def assure(self, token):
        """Simulated step-up on an exact raw user phrase seen by the host."""
        with self._lock:
            conversation = self._get(token)
            conversation.policy.cancel()
            conversation.session = replace(conversation.session, assured_at=self.clock(),
                                           revision=uuid.uuid4().hex)

    def reset(self, token):
        with self._lock:
            conversation = self._conversations.pop(token, None)
            if conversation is not None:
                conversation.policy.cancel()

    # -- model-visible reads (through MCP) ---------------------------------------------
    def _read(self, token, alias, kinds, call):
        with self._lock:
            conversation = self._get(token)
            conversation.policy.require_read(conversation.session, alias)
            ident, kind = conversation.accounts[alias]
            if kind not in kinds:
                raise Refused("unsupported_account_type")
            try:
                return {"state": "supplied", **call(conversation, ident, kind)}
            except Unavailable:
                return {"state": "unavailable"}

    def accounts(self, token):
        with self._lock:
            conversation = self._get(token)
            for alias in conversation.accounts:  # assurance applies to the list as well
                conversation.policy.require_read(conversation.session, alias)
                break
            return {"accounts": sorted(conversation.accounts)}

    def balance(self, token, account):
        return self._read(token, account, {"D", "S"}, lambda c, ident, kind: {
            "amount": self.client.available_balance(ident, kind), "currency": "USD",
            "balance_type": "available"})

    def history(self, token, account, page=1):
        if type(page) is not int or not 1 <= page <= 20:
            raise Refused("invalid_page")

        def call(conversation, ident, kind):
            cursors = conversation.cursors.setdefault(ident, {1: None})
            if page not in cursors:
                raise Unavailable("page_not_reached")
            rows, nxt = self.client.history(ident, kind, cursors[page])
            if nxt:
                cursors[page + 1] = nxt
            return {"entries": rows, "page": page, "more": bool(nxt), "scope": "this_returned_page"}
        return self._read(token, account, {"D", "S"}, call)

    def loan_payment(self, token, account):
        def call(conversation, ident, kind):
            result = self.client.loan_payment(ident)
            # Two separate facts; a missing one is reported as unavailable, never paired or inferred.
            due = f"USD {result['amount_due']}" if result["amount_due"] else "unavailable"
            date = _spoken_date(result["next_due_date"]) if result["next_due_date"] else "unavailable"
            return {"amount_due": result["amount_due"] or "unavailable",
                    "next_due_date": result["next_due_date"] or "unavailable", "currency": "USD",
                    "say": f"Current payment due: {due}. Next due date: {date}."}
        return self._read(token, account, {"L"}, call)

    def payoff(self, token, account, date):
        if not isinstance(date, str) or len(date) != 10:
            raise Refused("invalid_date")
        return self._read(token, account, {"L"}, lambda c, ident, kind: self.client.payoff(ident, date))

    def review_transfer(self, token, source, destination, amount, currency):
        """Prepare a draft. No policy state changes until the host arms it after delivery."""
        with self._lock:
            conversation = self._get(token)
            intent = TransferIntent(source, destination, amount, currency)
            for alias in (source, destination):
                if alias not in conversation.accounts or conversation.accounts[alias][1] not in {"D", "S"}:
                    raise Refused("outside_scope")
            if self.journal.held(conversation.session.principal):
                raise Refused("outcome_unresolved")
            conversation.policy.cancel()
            draft = uuid.uuid4().hex
            conversation.draft = (draft, intent)
            return {"review": draft, "source": source, "destination": destination,
                    "amount": format(Decimal(intent.amount), ".2f"), "currency": currency, "state": "pending"}

    def arm(self, token, draft, user_turn):
        """Host-only, after the canonical review text was actually delivered."""
        with self._lock:
            conversation = self._get(token)
            if conversation.draft is None or conversation.draft[0] != draft:
                raise Refused("review_unavailable")
            pending = conversation.policy.review(conversation.session, conversation.draft[1], user_turn)
            conversation.policy.delivered(pending)
            return {"state": "armed"}

    def cancel(self, token):
        with self._lock:
            conversation = self._get(token)
            conversation.policy.cancel()
            conversation.draft = None
            return {"state": "canceled"}

    def confirm_and_send(self, token, raw_utterance, user_turn):
        """The one physical send, only for the next raw confirming turn."""
        with self._lock:
            conversation = self._get(token)
            if conversation.draft is None:
                raise Refused("review_unavailable")
            intent = conversation.draft[1]
            conversation.draft = None
            # Speech-to-text and typing add end punctuation; the words must still match exactly.
            spoken = raw_utterance.strip().rstrip(".!") if isinstance(raw_utterance, str) else raw_utterance
            consumed = conversation.policy.confirm(conversation.session, intent, spoken, user_turn)
            source = conversation.accounts[intent.source]
            destination = conversation.accounts[intent.destination]
            principal = consumed.session.principal
            try:
                self.journal.reserve(principal, consumed.operation_id, self.journal.epoch)  # BEFORE sending
            except JournalRefused:
                raise Refused("outcome_unresolved") from None
            try:
                state = self.client.transfer(source, destination, Decimal(intent.amount))
            except Exception:
                state = "unknown"
            self.journal.result(consumed.operation_id, {"accepted": "accepted", "refused": "rejected"}.get(state, "unknown"))
            self._outcomes[principal] = state
            return {"state": state}

    def status(self, token):
        with self._lock:
            conversation = self._get(token)
            principal = conversation.session.principal
            if self.journal.held(principal):
                return {"state": "unknown"}
            return {"state": self._outcomes.get(principal, "none")}
