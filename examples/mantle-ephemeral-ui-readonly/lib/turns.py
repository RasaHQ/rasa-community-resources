"""Consume retained results; never call the Broker again to render a card.

Canonical byte/schema validation belongs to zeocore in its Python 3.14 process.
This module only enforces consumer binding, freshness and the advertised subset.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import secrets
import threading
from typing import Callable

MAX_BYTES = 262_144
UNAVAILABLE = '<p role="status">The current result is unavailable.</p>'


class Refused(ValueError):
    """Local consumer refusal; carries no result content."""


@dataclass(frozen=True)
class Turn:
    lease: str
    operation: str
    invocation: str


def visible(value: object) -> str:
    """Escape HTML and expose ALL non-ASCII characters, including invisibles.

    This intentionally limited pilot displays Unicode as literal escapes rather
    than duplicating Core's pinned Unicode tables. It never creates links.
    """
    return escape(str(value).encode("ascii", "backslashreplace").decode("ascii"))


def render_card(envelope: dict) -> str:
    """Called only after canonical validation and consumer checks."""
    card = envelope["components"][0]
    props = card["props"]
    facts = "".join(
        f'<dt>{visible(fact["label"])}</dt><dd>{visible(fact["value"])}</dd>'
        for fact in props["facts"]
    )
    evidence = "".join(
        f'<li>{visible(item)}</li>' for item in props["evidence"]
    )
    status = '<p>' + visible(props["status"]) + '</p>' if "status" in props else ""
    progress = '<p>' + visible(props["progress"]) + '</p>' if "progress" in props else ""
    return (
        '<section aria-label="' + visible(card["accessibility_label"]) + '">'
        '<h2>' + visible(card["title"]) + '</h2>'
        '<p>' + visible(props["summary"]) + '</p>'
        '<p>Partial view of the retained result.</p>'
        + status + progress + '<dl>' + facts + '</dl><ul>' + evidence + '</ul></section>'
    )


class TurnView:
    """One instance per authenticated conversation, held only in host memory.

    A new turn clears the current card before any read starts. Completion of an
    older read cannot clear or replace a newer turn. The host, never the model,
    supplies the expected operation/invocation and retained-original lookup.
    """

    def __init__(self, validate: Callable[[bytes], dict], *, max_age: int = 60):
        self._validate = validate
        self._max_age = max_age
        self._turn: Turn | None = None
        self._lock = threading.RLock()
        self.html = ""

    def begin(self, operation: str, invocation: str) -> Turn:
        with self._lock:
            self._turn = Turn(secrets.token_hex(16), operation, invocation)
            self.html = ""
            return self._turn

    def fail(self, turn: Turn) -> None:
        with self._lock:
            if turn == self._turn:
                self.html = UNAVAILABLE

    def accept(
        self,
        turn: Turn,
        raw: bytes,
        *,
        retained_original: Callable[[str, str], bool],
        now: datetime | None = None,
    ) -> bool:
        with self._lock:
            if turn != self._turn:
                return False
        try:
            if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
                raise Refused("response_bound")
            result = self._validate(raw)
            # This is a consumer policy, not a second schema validator.
            if result["schema"] != "zeo.ui-result/v1":
                raise Refused("unsupported_schema")
            if result["in_reply_to"] != {
                "operation": turn.operation, "invocation": turn.invocation
            }:
                raise Refused("wrong_invocation")
            if not retained_original(turn.operation, turn.invocation):
                raise Refused("missing_original")
            if result["complete"] is not False:
                raise Refused("projection_must_be_partial")
            cards = result["components"]
            if len(cards) != 1 or cards[0]["kind"] != "card":
                raise Refused("unsupported_components")
            if cards[0]["props"]["action_refs"] != []:
                raise Refused("actions_not_supported")
            current = now or datetime.now(timezone.utc)
            snapshot = cards[0]["snapshot"]
            if snapshot["source"] != {"kind": "operation", "ref": turn.invocation}:
                raise Refused("wrong_snapshot")
            for timestamp in (result["produced_at"], snapshot["observed_at"]):
                observed = datetime.strptime(
                    timestamp, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
                if not 0 <= (current - observed).total_seconds() <= self._max_age:
                    raise Refused("stale_or_future")
            if "expires_at" in snapshot:
                expires = datetime.strptime(
                    snapshot["expires_at"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
                if expires <= current:
                    raise Refused("expired_snapshot")
            html = render_card(result)
        except Exception:
            # Do not echo untrusted fallback text or validator diagnostics.
            self.fail(turn)
            return False
        with self._lock:
            if turn != self._turn:
                return False
            self.html = html
            return True
