"""The context package: the typed thing that crosses the agent/human boundary.

A handoff is a STATE transfer, not a phone transfer. The measure of a good one
is that the human starts from what the agent already knew, and the caller is
never asked a question they have already answered. That property is a property
of a *schema*, not of prose: if what crosses the boundary is one free-text
``handoff_reason`` string, everything the agent established is discarded at the
moment of handoff and the caller repeats it.

So the package is defined here as five typed sections:

===========================  ====================================================
``identity``                 who the caller is, and the TIER they were verified at
``intent``                   what they were trying to do, structured, not prose
``attempts``                 what was already tried and how each one came out
``do_not_repeat``            questions already answered, factors already verified
``summary``                  human-readable — DERIVED, never authored
===========================  ====================================================

The last one is the part most likely to be faked, so it is worth being blunt
about the mechanism: :func:`HandoffPackage.summary` is a **read-only property
computed from the other four sections on every access**. There is no summary
field, no setter, no constructor argument, and no writer anywhere in this
package. A caller cannot store a summary that disagrees with the fields,
because there is nowhere to store one. See :mod:`handoffpkg.summary`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Literal

from handoffpkg.summary import render_summary

# ---------------------------------------------------------------------------
# Verification tiers
# ---------------------------------------------------------------------------
# DEPENDENCY, declared rather than invented: the sibling pattern
# `patterns/voice-auth-stepup/` owns risk-tiered authentication and defines the
# tiers low / medium / high, chosen by the ACTION being attempted rather than
# asked for up front. This pattern does not decide auth policy and does not
# define a competing scheme — it only records, in the package, the tier the
# caller was verified at so the human desk can see it.
#
# `unverified` is added here and is NOT a fourth auth tier. It is the value the
# field carries before any verification has happened, which a handoff can
# legitimately occur in (a caller who fails auth twice is exactly the caller
# most likely to reach a human). Keeping it distinct from `low` matters: "we
# checked them weakly" and "we never checked them" must not read alike on an
# agent desk.
#
# VERIFIED AGAINST THE SIBLING (2026-09-02): voice-auth-stepup landed
# `authpolicy.tiers.AuthTier` with values none / low / medium / high, held in
# project memory under the key `auth_tier`, and `AuthTier.satisfies` uses `>=`
# on a rank lattice — the same ordering semantics as `tier_at_least` below.
#
# The three real tiers are identical. Two spellings differ, and both are
# ADAPTED here rather than argued about, because a pattern that only interops
# with a name it chose itself does not interop:
#
#   their `none`      == our `unverified`   (see TIER_ALIASES)
#   their `auth_tier` == our `verified_tier` (see redaction.SESSION_ALLOWLIST,
#                                             which allowlists both spellings)
#
# We keep `unverified` as the canonical spelling because a desk reads this word
# on a screen and "none" next to a caller's name is ambiguous — none of what?
VerificationTier = Literal["unverified", "low", "medium", "high"]

TIER_ORDER: tuple[str, ...] = ("unverified", "low", "medium", "high")

#: Spellings from neighbouring patterns, normalised on the way in. Adding an
#: entry here is how this pattern absorbs a vocabulary difference instead of
#: failing closed on a tier that was legitimately established.
TIER_ALIASES: dict[str, str] = {
    "none": "unverified",   # patterns/voice-auth-stepup: AuthTier.NONE
    "": "unverified",
}


def normalise_tier(value: object) -> str:
    """Map a tier from a neighbouring vocabulary onto this pattern's spelling.

    Unknown values are returned unchanged rather than coerced to a default, so
    they reach `tier_at_least` and fail closed there. Silently rewriting an
    unrecognised tier to something valid is how a desk ends up trusting a tier
    nobody defined.
    """
    text = str(value or "").strip().lower()
    return TIER_ALIASES.get(text, text)

# What each tier means to a human agent picking up the call. Wording is
# deliberately about what the DESK may do, not about how auth was performed —
# the desk's question is never "which factor" but "what am I allowed to action".
TIER_MEANING: dict[str, str] = {
    "unverified": "Identity NOT established. Treat every identifying detail as unconfirmed.",
    "low": "Weakly identified (self-asserted or inbound-number match). Do not action account changes.",
    "medium": "Verified with a knowledge factor. Account-specific information is in scope.",
    "high": "Verified with a second factor. Irreversible actions are in scope.",
}


def _str_tuple(value: Any) -> tuple[str, ...]:
    """Coerce a list-ish value to a tuple of strings, defensively.

    A bare string becomes a one-element tuple rather than a tuple of characters:
    ``tuple("solo")`` is ``('s','o','l','o')``, which renders on a desk screen
    as four single letters and is the kind of bug nobody reads carefully enough
    to spot in a review.
    """
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        text = value.decode() if isinstance(value, bytes) else value
        return (text,) if text.strip() else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if str(item).strip())
    return (str(value),)


def tier_at_least(tier: str, minimum: str) -> bool:
    """True when ``tier`` is at or above ``minimum`` in :data:`TIER_ORDER`.

    Ordinal comparison lives here rather than at the call sites so that adding
    or renaming a tier is one edit, not a search for every ``>=`` on a string.
    """
    try:
        return TIER_ORDER.index(tier) >= TIER_ORDER.index(minimum)
    except ValueError:
        # An unknown tier is not silently treated as sufficient. Failing closed
        # is the only safe reading: a desk that mis-reads an unrecognised tier
        # as "verified" is the failure this whole pattern exists to prevent.
        return False


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Identity:
    """Who the caller is, and how strongly that was established.

    `verified_tier` and `display_name` are separate on purpose. An unverified
    caller can still have *said* a name; recording it without the tier next to
    it is how a desk ends up trusting a self-asserted identity.
    """

    customer_id: str | None = None
    display_name: str | None = None
    verified_tier: VerificationTier = "unverified"
    #: Which factors actually succeeded, e.g. ["knowledge_passphrase", "otp_sms"].
    #: Factor NAMES only — never the values. See handoffpkg.redaction.
    verified_factors: tuple[str, ...] = ()
    #: Free-form channel identifier, e.g. "voice:+1-555-0100" or "web".
    channel: str | None = None


@dataclass(frozen=True)
class Intent:
    """What the caller was trying to do, structured rather than narrated.

    The whole point of the section is that ``goal`` is an identifier a desk can
    route, count, and build a queue on — not a sentence a human has to read and
    re-interpret. ``details`` carries the goal's parameters (which account,
    which card, how much) and is subject to the same allowlist as everything
    else in the package.
    """

    #: Machine identifier of the goal, e.g. "dispute_transaction".
    goal: str
    #: Human label for the goal, for the desk header.
    goal_label: str | None = None
    #: Structured parameters of the goal. Redacted like every other field.
    details: dict[str, Any] = field(default_factory=dict)
    #: Where the caller got to. Deliberately coarse — a desk needs "did they
    #: finish" not a state-machine cursor.
    stage: Literal["stated", "in_progress", "blocked", "abandoned"] = "stated"


@dataclass(frozen=True)
class Attempt:
    """One thing the agent already tried, and how it came out.

    This is the section that stops the human retrying a path that has already
    failed — the single most visible waste in a handoff, and the one callers
    complain about by name.
    """

    action: str
    outcome: Literal["succeeded", "failed", "blocked", "abandoned"]
    #: Why it came out that way, in words a human agent can act on.
    detail: str | None = None
    #: Machine-readable failure code where one exists, e.g. "insufficient_tier".
    code: str | None = None


@dataclass(frozen=True)
class DoNotRepeat:
    """What the human must NOT ask again.

    Split into two lists because they fail differently. Re-asking an answered
    question is irritating; re-running a verification the caller already passed
    is irritating AND it retrains callers to hand credentials to whoever asks.
    """

    #: Questions already answered, phrased as the desk would ask them.
    questions_answered: tuple[str, ...] = ()
    #: Verification factors already satisfied. NAMES only, never values.
    factors_verified: tuple[str, ...] = ()
    #: Anything else the desk should not re-litigate, e.g. "consent to record".
    confirmed_facts: tuple[str, ...] = ()


@dataclass(frozen=True)
class HandoffPackage:
    """The complete state transfer.

    Frozen because a package is a snapshot of what was true at the moment of
    handoff. If a desk could mutate it, "what the agent knew" and "what the desk
    edited" would become the same field, and the audit value goes to zero.
    """

    handoff_id: str
    reason: str
    identity: Identity
    intent: Intent
    attempts: tuple[Attempt, ...] = ()
    do_not_repeat: DoNotRepeat = field(default_factory=DoNotRepeat)
    #: Set by handoffpkg.redaction when the package is built from session state.
    #: Names of session fields that were withheld — the NAMES cross, the values
    #: never do. A desk that can see something was withheld will not go hunting
    #: for it by asking the caller.
    withheld_fields: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        """Human-readable summary, DERIVED on every access.

        Not a field. Not settable. Not cached. Every read re-renders from
        ``identity`` / ``intent`` / ``attempts`` / ``do_not_repeat``, so the
        summary and the structured fields are the same information in two
        renderings and cannot drift. Change a field and the next read of
        ``summary`` reflects it; there is no second copy to forget to update.

        This is the SOW's "derived rather than authored separately" requirement
        implemented as a property rather than promised in a docstring.
        """
        return render_summary(self)

    def to_dict(self) -> dict[str, Any]:
        """Serialisable form, as it would cross a real desk boundary.

        ``summary`` is included because the receiving side needs it, but it is
        computed here at serialisation time from the same fields — it is never
        read back in as a field. :func:`package_from_dict` deliberately ignores
        any ``summary`` key it is handed.
        """
        data = asdict(self)
        data["summary"] = self.summary
        return data


def _section(data: Mapping[str, Any], key: str) -> dict[str, Any]:
    """Read one section defensively.

    A missing key, an explicit JSON ``null``, and a value of the wrong type all
    become ``{}``. This is the deserialiser for data that crossed a process
    boundary — a queue file, a webhook body, a CRM field — so "the producer sent
    something odd" is a normal Tuesday, not an exceptional condition.
    """
    value = data.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _known_fields(cls: type, raw: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only the keys ``cls`` actually declares.

    Forward compatibility, in the only direction that matters here: a producer
    running a newer version of this schema adds a field, and an older desk must
    still be able to open the package. ``Cls(**raw)`` would raise ``TypeError``
    on the unknown key and the handoff would be lost entirely — the caller waits
    on hold while a human stares at an error, which is a strictly worse outcome
    than a desk that renders one field fewer.

    Dropping unknown keys is also the safe direction for the redaction contract:
    a field this schema does not declare has nowhere to land, so it cannot be
    smuggled in by a producer that skipped the allowlist.
    """
    allowed = {f.name for f in fields(cls)}
    return {key: value for key, value in raw.items() if key in allowed}


def package_from_dict(data: Mapping[str, Any]) -> HandoffPackage:
    """Rebuild a package from its serialised form.

    Any ``summary`` key in ``data`` is DISCARDED rather than restored — at the
    top level, and inside every section, since ``_known_fields`` drops keys no
    dataclass declares. This is the second half of the anti-drift mechanism: a
    package that made a round trip through a queue, a webhook, or someone's
    clipboard cannot smuggle in a summary that disagrees with its fields,
    because the summary is recomputed from the fields on the far side.

    Total on any mapping. Missing sections, null sections, unknown keys and
    malformed attempts all degrade to a thinner package rather than raising:
    this runs on the desk's deserialisation path, and a desk that crashes on a
    malformed package has lost the handoff outright.
    """
    identity_raw = _section(data, "identity")
    identity = Identity(
        **{
            **_known_fields(Identity, identity_raw),
            "verified_factors": _str_tuple(identity_raw.get("verified_factors")),
        }
    )

    intent_raw = _section(data, "intent")
    intent_kwargs = _known_fields(Intent, intent_raw)
    # `goal` has no default, so a section without it must be given one rather
    # than raising. "unknown" is honest and is what `unanswered_questions`
    # already treats as unanswered.
    intent_kwargs.setdefault("goal", "unknown")
    details = intent_kwargs.get("details")
    # Defensive COPY, not an alias. Without it the package holds a reference
    # into the caller's dict and a downstream mutation silently rewrites the
    # derived summary — drift by a different route than storage.
    intent_kwargs["details"] = dict(details) if isinstance(details, Mapping) else {}
    intent = Intent(**intent_kwargs)

    raw_attempts = data.get("attempts")
    if isinstance(raw_attempts, (str, bytes)) or not isinstance(raw_attempts, (list, tuple)):
        raw_attempts = ()
    attempts = tuple(
        Attempt(**{**_known_fields(Attempt, item), "action": str(item.get("action", "unknown"))})
        for item in raw_attempts
        if isinstance(item, Mapping)
    )

    dnr_raw = _section(data, "do_not_repeat")
    do_not_repeat = DoNotRepeat(
        questions_answered=_str_tuple(dnr_raw.get("questions_answered")),
        factors_verified=_str_tuple(dnr_raw.get("factors_verified")),
        confirmed_facts=_str_tuple(dnr_raw.get("confirmed_facts")),
    )
    return HandoffPackage(
        handoff_id=str(data.get("handoff_id") or "unknown"),
        reason=str(data.get("reason") or "Caller asked for a human."),
        identity=identity,
        intent=intent,
        attempts=attempts,
        do_not_repeat=do_not_repeat,
        withheld_fields=_str_tuple(data.get("withheld_fields")),
    )
