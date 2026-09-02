"""Risk-tiered authentication step-up for a Rasa Mantle voice agent.

Four modules, in the order they matter:

    tiers.py       the ordered lattice, and the one `satisfies` comparison
    actions.py     WHERE A TIER IS DECLARED — a table keyed by action
    guard.py       WHERE A TIER IS RESOLVED — inside the tool, before the effect
    challenges.py  the factors, the retry budget, and the lockout path

The claim, in one line: authentication strength is a property of the action
being attempted, not of the caller attempting it.
"""

from __future__ import annotations

from .actions import POLICIES, ActionPolicy, reason_for, tier_for
from .challenges import (
    DEMO_OTP,
    DEMO_PASSPHRASE,
    RETRY_BUDGET,
    ChallengeResult,
    Outcome,
    check_otp,
    check_passphrase,
    factor_for,
)
from .guard import (
    METHOD_MEMORY_KEY,
    TIER_MEMORY_KEY,
    Decision,
    StepUpRequired,
    evaluate,
    grant,
    redact,
    require_tier,
    revoke,
)
from .tiers import AuthTier, coerce

__all__ = [
    "POLICIES",
    "ActionPolicy",
    "AuthTier",
    "ChallengeResult",
    "DEMO_OTP",
    "DEMO_PASSPHRASE",
    "Decision",
    "METHOD_MEMORY_KEY",
    "Outcome",
    "RETRY_BUDGET",
    "StepUpRequired",
    "TIER_MEMORY_KEY",
    "check_otp",
    "check_passphrase",
    "coerce",
    "evaluate",
    "factor_for",
    "grant",
    "reason_for",
    "redact",
    "require_tier",
    "revoke",
    "tier_for",
]
