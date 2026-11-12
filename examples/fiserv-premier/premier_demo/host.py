# SPDX-License-Identifier: MIT
"""Trusted host state: sessions, review, confirmation, one send and a journal.

None of the host methods is an MCP tool. A fabricated context or a direct Python
call is not authentication: this is an identity and assurance simulator for a
fictional teaching host, not bank sign-in.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import fcntl
import math
import hashlib
from pathlib import Path
import re
import sqlite3
from threading import RLock
from time import monotonic
from uuid import uuid4

from .client import PremierClient, Unavailable, UnknownOutcome

READ_GRANT_SECONDS = 300
TRANSFER_GRANT_SECONDS = 60
REVIEW_SECONDS = 30


class Refused(ValueError):
    """A closed, non-sensitive reason suitable for a caller."""


@dataclass(frozen=True)
class SessionContext:
    """Host-only. Never build this from model or tool arguments."""

    session: str
    revision: int
    principal: str
    party: str
    accounts: tuple  # ((alias, account id, account type), ...)
    epoch: int


@dataclass
class _Review:
    context: SessionContext
    source: str
    destination: str
    amount: str
    expires: float
    state: str = "pending"


def _money(value):
    if (not isinstance(value, str) or len(value) > 18
            or re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value) is None):
        raise Refused("invalid_amount")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise Refused("invalid_amount") from None
    if not amount.is_finite() or amount <= 0:
        raise Refused("invalid_amount")
    return amount.quantize(Decimal("0.01"))


class Journal:
    """Private SQLite journal, synchronous=FULL, one owner at a time.

    It stores a principal, an opaque review id, a state and an epoch. It never
    stores an amount, an account, a credential or a transcript. A pending or
    unknown marker blocks every new transfer for that principal, across restarts.
    """

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock_file = open(path.with_suffix(".lock"), "a+")
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock_file.close()
            raise Refused("journal_in_use") from None
        try:
            self._db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.execute("CREATE TABLE IF NOT EXISTS epoch(id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER)")
            self._db.execute("INSERT OR IGNORE INTO epoch VALUES(1, 1)")
            self._db.execute("CREATE TABLE IF NOT EXISTS marker(principal TEXT, review TEXT, state TEXT, epoch INTEGER)")
            self._db.execute("CREATE TABLE IF NOT EXISTS audit(at TEXT DEFAULT CURRENT_TIMESTAMP, "
                             "reason TEXT, prior_sha256 TEXT, old_epoch INTEGER, new_epoch INTEGER)")
            self._db.execute("SELECT count(*) FROM marker").fetchone()
        except sqlite3.Error:
            self._lock_file.close()
            raise Refused("journal_unreadable") from None

    def close(self) -> None:
        self._db.close()
        self._lock_file.close()  # releases the exclusive lock

    @property
    def epoch(self) -> int:
        return self._db.execute("SELECT value FROM epoch").fetchone()[0]

    def held(self, principal: str) -> bool:
        row = self._db.execute("SELECT 1 FROM marker WHERE principal=? AND state IN ('pending','unknown')",
                               (principal,)).fetchone()
        return row is not None

    def mark_pending(self, principal: str, review: str, epoch: int) -> None:
        # One atomic statement: refuses when any open marker exists.
        self._db.execute("BEGIN IMMEDIATE")
        try:
            if self.held(principal):
                raise Refused("outcome_unresolved")
            self._db.execute("INSERT INTO marker VALUES(?,?,'pending',?)", (principal, review, epoch))
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def settle(self, review: str, state: str) -> None:
        self._db.execute("UPDATE marker SET state=? WHERE review=?", (state, review))

    def latest(self, principal: str):
        row = self._db.execute("SELECT state FROM marker WHERE principal=? ORDER BY rowid DESC LIMIT 1",
                               (principal,)).fetchone()
        return row[0] if row else None

    def reset_fixture(self, reason: str) -> int:
        """Out-of-band, mock only, with the backend stopped (we hold the lock)."""
        if not isinstance(reason, str) or not reason.strip():
            raise Refused("reason_required")
        prior = hashlib.sha256(self.path.read_bytes()).hexdigest()
        old = self.epoch
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._db.execute("INSERT INTO audit(reason, prior_sha256, old_epoch, new_epoch) VALUES(?,?,?,?)",
                             (reason.strip()[:200], prior, old, old + 1))
            # Old unknown entries stay as history. This starts a new fictional
            # exercise; it never says the old effect failed or succeeded.
            self._db.execute("UPDATE marker SET state='historical_unknown' WHERE state IN ('pending','unknown')")
            self._db.execute("UPDATE epoch SET value=?", (old + 1,))
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise Refused("audit_failed") from None
        return old + 1


class PremierService:
    def __init__(self, client: PremierClient, journal: Journal, permissions: dict, *, clock=monotonic):
        self.client, self.journal, self.permissions, self.clock = client, journal, permissions, clock
        self._sessions, self._assured, self._reviews = {}, {}, {}
        self._cursors = {}
        self._lock = RLock()

    # -- host-only ---------------------------------------------------------
    def open_session(self, caller):
        if caller not in self.permissions:
            raise Refused("unknown_simulated_caller")
        spec = self.permissions[caller]
        try:
            related = set(self.client.party_accounts(spec["party"]))
        except (Unavailable, UnknownOutcome):
            raise Refused("service_unavailable") from None
        # A relationship result never authorizes by itself: intersect it with
        # the private permission table and the expected account types.
        accounts = tuple((alias, ident, kind) for alias, ident, kind in spec["accounts"]
                         if (ident, kind) in related)
        context = SessionContext(uuid4().hex, 1, caller, spec["party"], accounts, self.journal.epoch)
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

    def _bound(self, context):
        if not isinstance(context, SessionContext) or self._sessions.get(context.session) != context:
            raise Refused("stale_session")
        if context.epoch != self.journal.epoch:
            raise Refused("stale_session")

    def _age(self, context):
        return self.clock() - self._assured[context.session]

    def _read_ok(self, context):
        self._bound(context)
        if self._age(context) >= READ_GRANT_SECONDS:
            raise Refused("assurance_required")

    def _account(self, context, alias, kinds):
        self._read_ok(context)
        for name, ident, kind in context.accounts:
            if name == alias and kind in kinds:
                return ident
        # Do not tell the caller whether a different account exists.
        raise Refused("account_unavailable")

    def reset(self, context):
        with self._lock:
            self._bound(context)
            del self._sessions[context.session]
            for review in self._reviews.values():
                if review.context == context and review.state in {"pending", "confirmed"}:
                    review.state = "canceled"

    def confirm(self, context, identifier, exact):
        with self._lock:
            review = self._review(context, identifier)
            if review.state != "pending" or review.expires <= self.clock():
                raise Refused("review_not_pending")
            if exact != {"source": review.source, "destination": review.destination,
                         "amount": review.amount, "currency": "USD"} or self._age(context) >= TRANSFER_GRANT_SECONDS:
                review.state = "canceled"
                raise Refused("review_changed")
            review.state = "confirmed"

    def cancel(self, context, identifier):
        with self._lock:
            review = self._review(context, identifier)
            if review.state in {"pending", "confirmed"}:
                review.state = "canceled"
            return {"state": review.state}

    def _review(self, context, identifier):
        self._bound(context)
        review = self._reviews.get(identifier) if isinstance(identifier, str) else None
        if review is None or review.context != context:
            raise Refused("review_unavailable")
        return review

    def submit(self, context, identifier):
        """The one physical send. Rechecks authority and deadlines right here."""
        with self._lock:
            review = self._review(context, identifier)
            if (review.state != "confirmed" or review.expires <= self.clock()
                    or self._age(context) >= TRANSFER_GRANT_SECONDS):
                raise Refused("confirmation_required")
            review.state = "dispatched"  # consume before anything effectful
            source = self._account(context, review.source, {"DDA"})
            destination = self._account(context, review.destination, {"DDA"})
            self.journal.mark_pending(context.principal, identifier, context.epoch)  # BEFORE sending
            try:
                state = self.client.transfer(source, destination, Decimal(review.amount))
            except Exception:  # unknown: keep the hold, never resend, never echo the error
                self.journal.settle(identifier, "unknown")
                return {"state": "unknown"}
            self.journal.settle(identifier, state)
            return {"state": state}

    # -- model-visible reads (through MCP) -----------------------------------
    def accounts(self, context):
        with self._lock:
            self._read_ok(context)
            return {"accounts": sorted(alias for alias, _, _ in context.accounts)}

    def _read(self, context, alias, kinds, call):
        with self._lock:
            ident = self._account(context, alias, kinds)
            try:
                return {"state": "supplied", **call(ident)}
            except (Unavailable, UnknownOutcome):
                return {"state": "unavailable"}

    def balance(self, context, account):
        return self._read(context, account, {"DDA"}, lambda ident: {
            "amount": format(self.client.available_balance(ident), "f"), "currency": "USD",
            "balance_type": "available"})

    def history(self, context, account, page=1):
        if type(page) is not int or not 1 <= page <= 20:
            raise Refused("invalid_page")

        def call(ident):
            key = (context.session, ident)
            cursors = self._cursors.setdefault(key, {1: None})
            if page not in cursors:
                raise Unavailable("page_not_reached")
            rows, nxt = self.client.transactions(ident, cursors[page])
            if nxt:
                cursors[page + 1] = nxt
            return {"entries": rows, "page": page, "more": bool(nxt), "scope": "this_returned_page"}
        return self._read(context, account, {"DDA"}, call)

    def loan_payment(self, context, account):
        return self._read(context, account, {"LOAN"}, lambda ident: self.client.loan_payment(ident))

    def payoff(self, context, account):
        return self._read(context, account, {"LOAN"}, lambda ident: {
            **self.client.current_payoff(ident), "as_of": "current"})

    def review_transfer(self, context, source, destination, amount, currency):
        with self._lock:
            self._account(context, source, {"DDA"})
            self._account(context, destination, {"DDA"})
            if self._age(context) >= TRANSFER_GRANT_SECONDS:
                raise Refused("assurance_required")
            if source == destination or currency != "USD":
                raise Refused("unsupported_transfer")
            if self.journal.held(context.principal):
                raise Refused("outcome_unresolved")
            cleaned = _money(amount)
            identifier = uuid4().hex
            self._reviews[identifier] = _Review(context, source, destination, format(cleaned, "f"),
                                                self.clock() + REVIEW_SECONDS)
            return {"review": identifier, "source": source, "destination": destination,
                    "amount": format(cleaned, "f"), "currency": "USD", "state": "pending"}

    def status(self, context):
        """The latest retained local outcome for this principal, no vendor call."""
        with self._lock:
            self._read_ok(context)
            state = self.journal.latest(context.principal)
            return {"state": state if state in {"pending", "unknown", "accepted", "refused"} else "none"}
