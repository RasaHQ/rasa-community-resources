"""Fixture-backed factors, and the failure paths that make a guard honest.

A guard that only ever says yes is untested. Most of the interesting behaviour
in an auth step-up is what happens on the way to *no*: how many attempts, what
happens when they run out, and — the one that matters — what the agent does
next.

THE DOWNGRADE BUG THIS PREVENTS
-------------------------------
The failure this module is shaped around: a caller fails the OTP for a card
reissue, the agent apologises, and then — still in the same skill, still holding
only MEDIUM — completes the reissue anyway, because the prose said "if
verification fails, offer to help another way" and the model read "help" as
"do the thing they asked for". The action succeeded on auth that was never
satisfied, and every log line says the call went fine.

Two mechanisms stop it, and they are independent on purpose:

1. `outcome()` returns `LOCKED_OUT`, never a tier. Exhausting the budget cannot
   produce an authenticated state, because this function has no code path that
   returns one.
2. `guard.require_tier` runs inside the tool regardless. Even if the
   conversation somehow arrives at the reissue tool after a lockout, the tier in
   memory is still MEDIUM (or NONE, post-revoke) and the tool refuses.

Belt and braces, because the first is a policy decision and the second is a fact
about the process, and only the second survives someone rewriting the prose.

NO REAL FACTORS LIVE HERE
-------------------------
The passphrase and the one-time code below are hard-coded fixtures for a demo
that must run with no accounts and no vendor. `tutorial/TUTORIAL.md` marks the
two functions a real deployment replaces, and what each must not log.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .tiers import AuthTier

# ---------------------------------------------------------------------------
# Fixtures. NOT credentials. See the README before copying this file anywhere.
# ---------------------------------------------------------------------------

# The demo passphrase, spelled as a caller would say it on a voice channel.
# Real deployments do not store a passphrase in cleartext, do not store it in
# source, and do not compare it with `==`. This one does all three, because it
# guards nothing.
DEMO_PASSPHRASE = "blue harbor"

# The demo one-time code. A real OTP is generated per attempt, delivered out of
# band, expires in single-digit minutes, and is single-use. This one is none of
# those things.
DEMO_OTP = "one nine three seven"

# Attempts allowed per challenge before lockout. Deliberately small and equal
# for both factors — a larger budget on the high-tier factor would be exactly
# backwards, since that is the one an attacker is guessing against.
RETRY_BUDGET = 2


class Outcome(str, Enum):
    """What a challenge attempt produced. Note there are three, not two."""

    PASSED = "passed"
    RETRY = "retry"
    """Wrong, but budget remains. The caller gets another go."""

    LOCKED_OUT = "locked_out"
    """Budget exhausted. Terminal — the only exit is a human."""


@dataclass(frozen=True)
class ChallengeResult:
    outcome: Outcome
    attempts_used: int
    attempts_remaining: int
    granted: AuthTier | None
    """The tier this attempt earned, or None. `LOCKED_OUT` and `RETRY` both
    carry None — there is no path from a failed challenge to a tier."""

    handoff: bool = False
    """True when the conversation must go to a human. Set only on lockout."""


def _normalize(spoken: str) -> str:
    """Compare what a caller SAID, not how the ASR punctuated it.

    Voice input arrives with inconsistent casing, trailing periods, and variable
    inter-word spacing between runs of the same audio. Comparing raw strings
    gives you a factor that fails for reasons the caller cannot perceive or fix,
    which trains agents to widen the match until it accepts anything.

    This normalization is doing real work in a voice context and is also a
    reminder of the limit: it makes the factor easier to say correctly, and
    equally easier to say correctly *by someone who overheard it*.
    """
    return " ".join(spoken.lower().replace(".", " ").replace(",", " ").split())


def check_passphrase(spoken: str, attempts_used: int) -> ChallengeResult:
    """Knowledge factor. Earns MEDIUM. Never earns HIGH, no matter how correct.

    The ceiling is the point. A passphrase is a shared secret that the caller
    says out loud, over a channel that records it — it cannot bear the weight of
    an irreversible action, and this function structurally cannot grant one.
    """
    return _evaluate(spoken, DEMO_PASSPHRASE, AuthTier.MEDIUM, attempts_used)


def check_otp(spoken: str, attempts_used: int) -> ChallengeResult:
    """Possession factor. Earns HIGH.

    "Possession" is doing a lot of work in that sentence and the README says so
    plainly: a code read aloud on the same call is closer to a second knowledge
    factor than to real possession, because a caller who has been socially
    engineered will read it out to the attacker.
    """
    return _evaluate(spoken, DEMO_OTP, AuthTier.HIGH, attempts_used)


def _evaluate(
    spoken: str, expected: str, grants: AuthTier, attempts_used: int
) -> ChallengeResult:
    """Shared attempt accounting for both factors."""
    used = attempts_used + 1
    remaining = max(RETRY_BUDGET - used, 0)

    if _normalize(spoken) == _normalize(expected):
        return ChallengeResult(
            outcome=Outcome.PASSED,
            attempts_used=used,
            attempts_remaining=remaining,
            granted=grants,
        )

    if remaining > 0:
        return ChallengeResult(
            outcome=Outcome.RETRY,
            attempts_used=used,
            attempts_remaining=remaining,
            granted=None,
        )

    return ChallengeResult(
        outcome=Outcome.LOCKED_OUT,
        attempts_used=used,
        attempts_remaining=0,
        granted=None,
        handoff=True,
    )


def factor_for(required: AuthTier) -> str:
    """Which factor a caller must satisfy to reach `required`.

    Used by the step-up skill to ask the right question. MEDIUM wants the
    passphrase; HIGH wants the one-time code.
    """
    if required is AuthTier.HIGH:
        return "otp"
    if required is AuthTier.MEDIUM:
        return "passphrase"
    return "none"
