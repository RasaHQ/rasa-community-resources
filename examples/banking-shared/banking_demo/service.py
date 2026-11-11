"""Server-owned review state. None of the host methods is an MCP tool.

The caller must supply a genuinely trusted host adapter. A fabricated context or
direct Python invocation is not authentication. This module makes no network
calls and contains no vendor wire schema.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re
from threading import RLock
from time import monotonic
from uuid import uuid4


class Refused(ValueError):
    """A closed, non-sensitive reason suitable for a caller."""


@dataclass(frozen=True)
class SessionContext:
    """Host-only context; never deserialize this from model/tool arguments."""

    session: str
    revision: int
    principal: str
    accounts: frozenset[str]
    assurance_until: float


@dataclass(frozen=True)
class Transfer:
    source: str
    destination: str
    amount: str
    currency: str


@dataclass
class _Review:
    context: SessionContext
    transfer: Transfer
    expires: float
    state: str = "pending"
    outcome: dict | None = field(default=None)


def _money(value):
    if (not isinstance(value, str) or len(value) > 18
            or re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value) is None):
        raise Refused("invalid_amount")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise Refused("invalid_amount") from None
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise Refused("invalid_amount")
    return format(amount.quantize(Decimal("0.01")), "f")


class BankingService:
    """One shared action surface with an injected adapter and trusted host state.

    Host calls open_session/confirm/cancel/reset; curated tool wrappers may call
    accounts/balance/review_transfer/submit/status with a host-resolved context.
    No method accepts a model-provided confirmed/verified flag.
    """

    def __init__(self, adapter, *, clock=monotonic, review_seconds=120):
        if review_seconds <= 0 or review_seconds > 300:
            raise ValueError("review_seconds must be between zero and 300")
        self.adapter = adapter
        self.clock = clock
        self.review_seconds = review_seconds
        self._sessions = {}
        self._reviews = {}
        self._lock = RLock()

    def open_session(self, context):
        """Trusted-host registration only, after channel identity resolution."""
        with self._lock:
            if not isinstance(context, SessionContext) or not context.session:
                raise Refused("invalid_session")
            if context.session in self._sessions:
                raise Refused("session_already_bound")
            self._sessions[context.session] = context

    def _bound(self, context):
        if not isinstance(context, SessionContext):
            raise Refused("invalid_session")
        if self._sessions.get(context.session) != context:
            raise Refused("stale_session")

    def _context(self, context):
        self._bound(context)
        if context.assurance_until <= self.clock():
            raise Refused("assurance_required")

    def _account(self, context, account):
        self._context(context)
        if not isinstance(account, str) or account not in context.accounts:
            # Do not ask the adapter whether a different account exists.
            raise Refused("account_unavailable")

    def accounts(self, context):
        with self._lock:
            self._context(context)
            return {"accounts": sorted(context.accounts)}

    def balance(self, context, account):
        with self._lock:
            self._account(context, account)
            try:
                result = self.adapter.balance(account)
            except Exception:
                return {"state": "unavailable"}
            # Only the typed domain fields cross the adapter boundary.
            if not isinstance(result, dict) or set(result) != {"amount", "currency"}:
                return {"state": "unavailable"}
            amount = result["amount"]
            if (not isinstance(amount, str) or len(amount) > 18
                    or re.fullmatch(r"-?[0-9]+(?:\.[0-9]{1,2})?", amount) is None
                    or result["currency"] != "USD"):
                return {"state": "unavailable"}
            return {"state": "supplied", "amount": amount, "currency": "USD"}

    def review_transfer(self, context, source, destination, amount, currency):
        with self._lock:
            self._account(context, source)
            self._account(context, destination)
            if source == destination or currency != "USD":
                raise Refused("unsupported_transfer")
            transfer = Transfer(source, destination, _money(amount), currency)
            identifier = uuid4().hex
            self._reviews[identifier] = _Review(
                context, transfer, self.clock() + self.review_seconds
            )
            return {"review": identifier, **vars(transfer), "state": "pending"}

    def _review(self, context, identifier):
        self._context(context)
        review = self._reviews.get(identifier) if isinstance(identifier, str) else None
        if review is None or review.context != context:
            raise Refused("review_unavailable")
        return review

    def confirm(self, context, identifier, exact_transfer):
        """Host-only: called for a real deterministic user-confirmation event.

        A flow must independently observe that event and carry this exact review;
        a language-model boolean is insufficient. The host adapter is not yet
        implemented here. Repeated confirmation never re-arms a consumed review.
        """
        with self._lock:
            review = self._review(context, identifier)
            if review.state != "pending" or review.expires <= self.clock():
                raise Refused("review_not_pending")
            if exact_transfer != vars(review.transfer):
                review.state = "canceled"
                raise Refused("review_changed")
            review.state = "confirmed"

    def cancel(self, context, identifier):
        with self._lock:
            review = self._review(context, identifier)
            if review.outcome is not None:
                # Cancellation cannot erase an already dispatched operation.
                return dict(review.outcome)
            review.state = "canceled"
            return {"state": "canceled"}

    def reset(self, context):
        """Logout/reset invalidates context and pending consent, retaining outcomes."""
        with self._lock:
            self._bound(context)
            del self._sessions[context.session]
            for review in self._reviews.values():
                if review.context == context and review.outcome is None:
                    review.state = "canceled"

    def submit(self, context, identifier):
        with self._lock:
            review = self._review(context, identifier)
            self._account(context, review.transfer.source)
            self._account(context, review.transfer.destination)
            if review.outcome is not None:
                return dict(review.outcome)
            if review.state != "confirmed" or review.expires <= self.clock():
                raise Refused("confirmation_required")
            # Consume BEFORE dispatch, including a timeout or ambiguous error.
            review.state = "dispatched"
            review.outcome = {"state": "unknown", "operation": identifier}
            try:
                state = self.adapter.submit(identifier, review.transfer)
                if state in {"accepted", "queued", "posted", "refused", "unsupported"}:
                    review.outcome = {"state": state, "operation": identifier}
            except Exception:
                pass  # Never return, log or chain the provider exception.
            return dict(review.outcome)

    def status(self, context, identifier):
        with self._lock:
            review = self._review(context, identifier)
            if review.outcome is None:
                return {"state": review.state}
            # No vendor inquiry is invented; no status call repeats submit.
            return dict(review.outcome)
