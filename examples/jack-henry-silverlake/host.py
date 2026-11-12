"""Private, vendor-neutral host review policy for fictional banking examples.

The channel adapter owns these calls. It binds real user turns to a fictional
session; none of these methods is a model tool. This slice produces a consumed
review permit. A dispatcher must persist its journal marker before sending.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from functools import wraps
import math
import re
import time
import threading
import uuid
from typing import Callable


class Refused(Exception):
    """A redacted policy outcome suitable for a generic refusal."""


@dataclass(frozen=True)
class Session:
    principal: str
    revision: str
    aliases: frozenset[str]
    currency: str
    assured_at: float

    def __post_init__(self) -> None:
        if not isinstance(self.principal, str) or not isinstance(self.revision, str) or not self.principal or not self.revision:
            raise Refused("invalid_session")
        if not isinstance(self.currency, str) or not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise Refused("invalid_currency_context")
        if not isinstance(self.aliases, frozenset) or not self.aliases:
            raise Refused("invalid_scope")
        if any(not isinstance(a, str) or not a for a in self.aliases):
            raise Refused("invalid_scope")
        if isinstance(self.assured_at, bool) or not isinstance(self.assured_at, (int, float)):
            raise Refused("invalid_assurance")
        if not math.isfinite(self.assured_at):
            raise Refused("invalid_assurance")


@dataclass(frozen=True)
class TransferIntent:
    source: str
    destination: str
    amount: str
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, str) or len(self.amount) > 32:
            raise Refused("invalid_amount")
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", self.amount):
            raise Refused("invalid_amount")
        value = Decimal(self.amount)
        if value <= 0:
            raise Refused("invalid_amount")
        canonical = format(value, "f")
        if "." in canonical:
            canonical = canonical.rstrip("0").rstrip(".")
        object.__setattr__(self, "amount", canonical)
        if not isinstance(self.currency, str) or not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise Refused("invalid_currency")
        if not isinstance(self.source, str) or not isinstance(self.destination, str) or not self.source or not self.destination or self.source == self.destination:
            raise Refused("invalid_accounts")


@dataclass(frozen=True)
class Review:
    session: Session
    intent: TransferIntent
    created_at: float
    user_turn: int
    operation_id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass(frozen=True)
class ConsumedReview:
    """Private one-turn decision; the journal/dispatcher owns physical send."""
    session: Session
    intent: TransferIntent
    operation_id: str


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


class HostPolicy:
    READ_LIFETIME = 300.0
    TRANSFER_LIFETIME = 60.0
    REVIEW_LIFETIME = 30.0
    CONFIRMATIONS = frozenset({"yes", "confirm", "confirmed", "confirm transfer"})

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._pending: Review | None = None
        self._delivered = False

    def _now(self) -> float:
        now = self._clock()
        if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now):
            raise Refused("invalid_clock")
        return now

    def _assurance(self, session: Session, limit: float, now: float) -> None:
        age = now - session.assured_at
        if age < 0 or age >= limit:
            raise Refused("assurance_expired")

    @staticmethod
    def _turn(turn: int) -> None:
        if isinstance(turn, bool) or not isinstance(turn, int) or turn < 0:
            raise Refused("invalid_turn")

    @staticmethod
    def _scope(session: Session, intent: TransferIntent) -> None:
        if intent.source not in session.aliases or intent.destination not in session.aliases:
            raise Refused("outside_scope")
        if intent.currency != session.currency:
            raise Refused("currency_mismatch")

    def require_read(self, session: Session, alias: str) -> None:
        self._assurance(session, self.READ_LIFETIME, self._now())
        if alias not in session.aliases:
            raise Refused("outside_scope")

    @_serialized
    def review(self, session: Session, intent: TransferIntent, user_turn: int) -> Review:
        # Any new intent invalidates the old pending consent, even if it refuses.
        self.cancel()
        self._turn(user_turn)
        now = self._now()
        self._assurance(session, self.TRANSFER_LIFETIME, now)
        self._scope(session, intent)
        pending = Review(session, intent, now, user_turn)
        self._pending = pending
        return pending

    @_serialized
    def delivered(self, pending: Review) -> None:
        # The actual output adapter calls this only after successful delivery.
        if pending is not self._pending:
            self.cancel()
            raise Refused("review_unavailable")
        self._delivered = True

    @_serialized
    def cancel(self) -> None:
        self._pending = None
        self._delivered = False

    @_serialized
    def confirm(self, session: Session, intent: TransferIntent,
                raw_utterance: str, user_turn: int) -> ConsumedReview:
        pending, delivered = self._pending, self._delivered
        # Consume before any subsequent action; refusal cannot revive a review.
        self.cancel()
        self._turn(user_turn)
        if pending is None or not delivered:
            raise Refused("review_unavailable")
        if pending.session != session or pending.intent != intent:
            raise Refused("review_changed")
        if user_turn != pending.user_turn + 1:
            raise Refused("next_turn_required")
        if not isinstance(raw_utterance, str) or raw_utterance.strip().casefold() not in self.CONFIRMATIONS:
            raise Refused("confirmation_required")
        now = self._now()
        age = now - pending.created_at
        if age < 0 or age >= self.REVIEW_LIFETIME:
            raise Refused("review_expired")
        self._assurance(session, self.TRANSFER_LIFETIME, now)
        self._scope(session, intent)
        return ConsumedReview(session, intent, pending.operation_id)
