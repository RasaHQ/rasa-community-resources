"""The tier lattice, and the one comparison the whole pattern rests on.

Three tiers, ordered. `LOW < MEDIUM < HIGH`. Everything else in this package is
bookkeeping around a single question:

    does the auth the caller has already satisfied reach the tier the action
    they are attempting demands?

Keeping that question in one place — `AuthTier.satisfies` — is deliberate. The
failure mode this pattern exists to prevent is a codebase where the comparison
is re-implemented per skill, so that eleven call sites agree and the twelfth
uses `>=` on a string and silently lets `"low"` past `"high"` (it does not; `"l"`
sorts before `"h"` is false, and that is exactly the kind of thing nobody
notices until it is a breach).
"""

from __future__ import annotations

from enum import Enum


class AuthTier(str, Enum):
    """Ordered authentication strength.

    Subclasses `str` so a tier round-trips through Rasa memory — which stores
    text — without a conversion layer. `AuthTier("medium")` reconstructs it.
    """

    NONE = "none"
    """No factor satisfied. The state every call starts in."""

    LOW = "low"
    """Informational. The caller is anonymous and that is fine."""

    MEDIUM = "medium"
    """Account-specific. A knowledge factor (passphrase) was satisfied."""

    HIGH = "high"
    """Irreversible or fraud-attractive. A one-time code was satisfied."""

    @property
    def rank(self) -> int:
        """Position in the lattice. The only place the ordering is written down."""
        return _RANK[self]

    def satisfies(self, required: "AuthTier") -> bool:
        """True when auth at this tier is enough for an action requiring `required`.

        This is the guard's whole semantics. Note it is `>=`, not `==`: a caller
        who stepped up to HIGH for a card reissue does not get re-challenged for
        their balance in the same call. Step-up is monotonic within a session —
        strength is earned once and retained, while *requirement* is evaluated
        per action.
        """
        return self.rank >= required.rank


_RANK: dict[AuthTier, int] = {
    AuthTier.NONE: 0,
    AuthTier.LOW: 1,
    AuthTier.MEDIUM: 2,
    AuthTier.HIGH: 3,
}


def coerce(value: object) -> AuthTier:
    """Read a tier out of whatever memory handed back, failing CLOSED.

    Memory is text and may be `None` on the first turn, may be a stale value
    written by an older build, or may be something the LLM invented. Every one
    of those resolves to `NONE` rather than raising, because a guard that throws
    on unexpected input is a guard that gets wrapped in a bare `except` within a
    month. Unknown input is unauthenticated input.
    """
    if isinstance(value, AuthTier):
        return value
    if isinstance(value, str):
        try:
            return AuthTier(value.strip().lower())
        except ValueError:
            return AuthTier.NONE
    return AuthTier.NONE
