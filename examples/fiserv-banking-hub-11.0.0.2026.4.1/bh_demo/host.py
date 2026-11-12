# SPDX-License-Identifier: MIT
"""Trusted host state: sessions, simulated assurance and permitted reads.

None of the host methods is an MCP tool. A fabricated context or a direct Python
call is not authentication: this is an identity and assurance simulator for a
fictional teaching host, not bank sign-in.

This release example makes no transfer. The release does not declare a transfer
type value, so the review and status tools answer plainly that transfers are not
available here, and no host path can send one.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from threading import RLock
from time import monotonic
from uuid import uuid4

from .client import BankingHubClient, Unavailable

READ_GRANT_SECONDS = 300

# Facts the release cannot supply with a sourced code (see the README).
UNSOURCED = {
    "balance": "available_balance_code_not_in_release",
    "history": "release_history_schema_defect",
    "payment_amount": "payment_amount_code_not_in_release",
    "payoff": "payoff_code_not_in_release",
    "transfer": "transfer_type_not_in_release",
}


class Refused(ValueError):
    """A closed, non-sensitive reason suitable for a caller."""


@dataclass(frozen=True)
class SessionContext:
    """Host-only. Never build this from model or tool arguments."""

    session: str
    principal: str
    party: str
    accounts: tuple  # ((alias, account id, account type), ...)


class BankingHubService:
    def __init__(self, client: BankingHubClient, permissions: dict, *, clock=monotonic):
        self.client, self.permissions, self.clock = client, permissions, clock
        self._sessions, self._assured = {}, {}
        self._lock = RLock()

    # -- host-only ---------------------------------------------------------
    def open_session(self, caller):
        if caller not in self.permissions:
            raise Refused("unknown_simulated_caller")
        spec = self.permissions[caller]
        try:
            related = set(self.client.party_accounts(spec["party"]))
        except Unavailable:
            raise Refused("service_unavailable") from None
        # A relationship result never authorizes by itself: intersect it with
        # the private permission table and the expected account types.
        accounts = tuple((alias, ident, kind) for alias, ident, kind in spec["accounts"]
                         if (ident, kind) in related)
        context = SessionContext(uuid4().hex, caller, spec["party"], accounts)
        with self._lock:
            if len(self._sessions) >= 32:
                raise Refused("session_limit")
            self._sessions[context.session] = context
            self._assured[context.session] = self.clock()
        return context

    def assure(self, context, age_seconds=0):
        """Simulated step-up, dated by when the raw phrase was actually said."""
        if (isinstance(age_seconds, bool) or not isinstance(age_seconds, (int, float))
                or not math.isfinite(age_seconds) or age_seconds < 0 or age_seconds > 86400):
            raise Refused("invalid_assurance_event")
        with self._lock:
            self._bound(context)
            self._assured[context.session] = self.clock() - age_seconds

    def reset(self, context):
        with self._lock:
            self._bound(context)
            del self._sessions[context.session]
            self._assured.pop(context.session, None)

    def _bound(self, context):
        if not isinstance(context, SessionContext) or self._sessions.get(context.session) != context:
            raise Refused("stale_session")

    def _read_ok(self, context):
        self._bound(context)
        if self.clock() - self._assured[context.session] >= READ_GRANT_SECONDS:
            raise Refused("assurance_required")

    def _account(self, context, alias, kinds):
        self._read_ok(context)
        for name, ident, kind in context.accounts:
            if name == alias and kind in kinds:
                return ident
        # Do not tell the caller whether a different account exists.
        raise Refused("account_unavailable")

    def _unavailable(self, context, alias, kinds, fact):
        """Check the alias is the caller's, then say plainly the fact is missing."""
        with self._lock:
            self._account(context, alias, kinds)
            return {"state": "unavailable", "reason": UNSOURCED[fact]}

    # -- model-visible reads (through MCP) -----------------------------------
    def accounts(self, context):
        with self._lock:
            self._read_ok(context)
            return {"accounts": sorted(alias for alias, _, _ in context.accounts)}

    def balance(self, context, account):
        return self._unavailable(context, account, {"DDA", "SDA"}, "balance")

    def history(self, context, account, page=1):
        if type(page) is not int or not 1 <= page <= 20:
            raise Refused("invalid_page")
        return self._unavailable(context, account, {"DDA", "SDA"}, "history")

    def loan_payment(self, context, account):
        with self._lock:
            ident = self._account(context, account, {"LOAN"})
            try:
                due = self.client.next_payment_date(ident)
            except Unavailable:
                return {"state": "unavailable"}
            # The date is a plain field; the amount would need an unsourced code.
            return {"state": "supplied", "due_date": due, "reason": UNSOURCED["payment_amount"]}

    def payoff(self, context, account):
        return self._unavailable(context, account, {"LOAN"}, "payoff")

    def review_transfer(self, context, source, destination, amount, currency):
        with self._lock:
            self._read_ok(context)
            return {"state": "refused", "reason": UNSOURCED["transfer"]}

    def status(self, context):
        """No transfer can exist in this release example."""
        with self._lock:
            self._read_ok(context)
            return {"state": "none", "reason": UNSOURCED["transfer"]}

    # -- host-only transfer steps: none can send in this release ---------------
    def confirm(self, context, identifier, exact):
        self._bound(context)
        raise Refused(UNSOURCED["transfer"])

    def cancel(self, context, identifier):
        self._bound(context)
        return {"state": "none"}

    def submit(self, context, identifier):
        self._bound(context)
        raise Refused(UNSOURCED["transfer"])
