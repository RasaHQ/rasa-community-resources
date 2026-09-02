"""The allowlist that governs what crosses the agent/human boundary.

Redaction is part of the handoff CONTRACT, not a cleanup step applied to a
package that was already built. The difference is the whole design:

    A denylist asks "is this field one of the bad ones?" and is wrong the first
    time someone adds a field nobody thought of — which, in a live agent, is
    every sprint. A field added to session state on Tuesday is in Tuesday's
    handoff packages whether or not anyone reviewed it.

    An allowlist asks "is this field one of the ones we decided to send?" and
    its failure mode is a MISSING field on the desk, which a human notices and
    reports. The failure modes are not symmetric, and only one of them leaks.

So :func:`build_package_from_session` is the only supported way to turn session
state into a package, and it copies **only** keys named in
:data:`SESSION_ALLOWLIST`. Everything else is dropped, and its NAME (never its
value) is recorded in ``withheld_fields`` so the desk can see that something was
withheld rather than absent.

WHAT THIS DOES NOT DO — read this before claiming a privacy property
--------------------------------------------------------------------
1. It governs **session-state keys only**. It cannot police free text. If a
   caller says their card number aloud and the agent writes that utterance into
   an allowlisted field such as ``handoff_reason``, the allowlist transfers it
   verbatim. See :func:`scan_freetext_risk`, which *detects* the common shapes
   and is a warning, not a guarantee.
2. It is **not a compliance control**. It is a demonstration of where the
   boundary belongs. PCI, HIPAA and equivalents impose obligations on storage,
   transport and retention that a dataclass does not discharge.
3. It does not redact the desk's own notes, the call recording, the ASR
   transcript, or any log written before the handoff. Those are separate
   surfaces with separate boundaries, and each one has leaked in production
   somewhere.
4. Nested structures are copied by value when their top-level key is
   allowlisted. Allowlisting a dict means allowlisting everything inside it, so
   allowlist leaves rather than containers where you can.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from handoffpkg.schema import (
    TIER_ORDER,
    Attempt,
    DoNotRepeat,
    HandoffPackage,
    Identity,
    Intent,
    _str_tuple,
    normalise_tier,
)

# ---------------------------------------------------------------------------
# THE ALLOWLIST
# ---------------------------------------------------------------------------
# Every session key that may cross the boundary, and nothing else. Adding a key
# here is the deliberate act of deciding a human agent may see it; that is the
# review point this pattern is trying to create.
#
# Note what is ABSENT and why it is absent, because the absences are the design:
#   pin_attempt          - a spoken PIN. The caller's live credential.
#   otp_code             - a one-time code. Still valid at the moment of handoff.
#   card_number          - a full PAN. card_last_four is allowlisted instead.
#   passphrase_attempt   - a knowledge factor, in the clear.
#   ssn / national_id    - not needed to serve the caller; needed to impersonate them.
#   auth_token           - a bearer credential.
#   recording_url        - a separate surface with its own retention rules.
SESSION_ALLOWLIST: frozenset[str] = frozenset(
    {
        # --- identity (who, and how strongly) ---------------------------------
        "customer_id",
        "display_name",
        "verified_tier",
        # The sibling pattern voice-auth-stepup holds the tier under this key.
        # Allowlisting both spellings is what makes the two compose without
        # either one renaming its own memory schema.
        "auth_tier",
        "verified_factors",
        "channel",
        # --- intent (what they wanted, structured) ----------------------------
        "goal",
        "goal_label",
        "goal_stage",
        "account_id",
        "account_label",
        # Last four only. The full PAN is deliberately not allowlisted: four
        # digits identify the card to a human, and cannot be used to transact.
        "card_last_four",
        "dispute_amount",
        "dispute_merchant",
        "dispute_date",
        # --- process state ----------------------------------------------------
        "handoff_reason",
        "attempts",
        "questions_answered",
        "factors_verified",
        "confirmed_facts",
    }
)

# Keys whose *names* are still useful to the desk even though their values must
# not cross. Naming them lets the summary say "withheld by policy" rather than
# leaving the desk to wonder, and stops an agent asking the caller to repeat a
# credential the system already has.
ANNOUNCE_WITHHELD = True

# Shapes that must never appear in a package even inside an allowlisted string
# field. This is a DETECTOR, not a redactor — see scan_freetext_risk.
_FREETEXT_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # 13-19 digits, optionally separated, is a card-number shape.
    ("card_number_shape", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    # A 4-8 digit run introduced by a credential word.
    (
        "spoken_credential",
        re.compile(
            r"\b(?:pin|otp|passcode|password|code|cvv|cvc)\b[^0-9a-z]{0,12}[0-9]{3,8}\b",
            re.IGNORECASE,
        ),
    ),
    ("ssn_shape", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
)


def scan_freetext_risk(text: str) -> list[str]:
    """Return names of sensitive SHAPES found in ``text``.

    Deliberately advisory. The allowlist is a guarantee about session KEYS; it
    is not, and cannot be, a guarantee about the contents of a free-text field a
    caller dictated. Calling this a redactor would be claiming a property the
    code does not have — which is precisely the failure mode this pattern's
    README warns about. It catches the common shapes and it will miss others.
    """
    return [name for name, pattern in _FREETEXT_RISK_PATTERNS if pattern.search(text)]


def filter_session(session: Mapping[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Split ``session`` into (allowed, withheld_names).

    The single choke point. Every value in the returned dict is there because
    its key is in :data:`SESSION_ALLOWLIST`; every other key contributes only
    its name to the second element, and its value is not returned at all — not
    hashed, not truncated, not masked. A masked value is still a value, and
    masking is where leaks hide.
    """
    allowed: dict[str, Any] = {}
    withheld: list[str] = []
    for key, value in session.items():
        if key in SESSION_ALLOWLIST:
            allowed[key] = value
        else:
            withheld.append(key)
    return allowed, tuple(sorted(withheld))


def _resolve_tier(allowed: Mapping[str, Any]) -> str:
    """Resolve the verification tier from whichever spelling the session used.

    Two spellings coexist: this pattern writes `verified_tier`, and the sibling
    `patterns/voice-auth-stepup` writes `auth_tier`. When both are present and
    they DISAGREE, neither key tells you which is fresher — so preferring one by
    position would be arbitrary, and an arbitrary choice is wrong half the time.

    The rule is instead explicit and directional: **take the WEAKER of the two.**
    A handoff that under-states the caller's strength costs them one step-up at
    the desk. A handoff that over-states it hands a human the authority to action
    an irreversible change for someone never verified to that level. Those costs
    are not comparable, and only one of them is a security incident.

    Absence resolves to `unverified`, not `low`: a session with no tier recorded
    is a session where verification did not happen.
    """
    present = [
        normalise_tier(allowed[key])
        for key in ("verified_tier", "auth_tier")
        if allowed.get(key) is not None and str(allowed[key]).strip()
    ]
    if not present:
        return "unverified"
    # An unrecognised tier is returned as-is and sorts ahead of everything: it
    # is not in TIER_ORDER, so it cannot be shown to be strong, and
    # `tier_at_least` fails closed on it downstream.
    unknown = [tier for tier in present if tier not in TIER_ORDER]
    if unknown:
        return unknown[0]
    return min(present, key=TIER_ORDER.index)


def build_package_from_session(
    session: Mapping[str, Any],
    *,
    handoff_id: str,
) -> HandoffPackage:
    """Build the context package from raw session state.

    This is the boundary. Session state goes in — all of it, including whatever
    a skill happened to write there — and a package comes out containing only
    allowlisted keys. The function never sees a reason to trust its input, which
    is the point: the caller of this function is ordinary agent code that has no
    idea which of its fields are sensitive.
    """
    allowed, withheld = filter_session(session)

    identity = Identity(
        customer_id=allowed.get("customer_id"),
        display_name=allowed.get("display_name"),
        verified_tier=_resolve_tier(allowed),
        verified_factors=_str_tuple(allowed.get("verified_factors")),
        channel=allowed.get("channel"),
    )

    # Intent details are assembled from allowlisted leaf keys rather than by
    # copying a `details` dict wholesale. Copying a container would allowlist
    # every key anyone ever puts inside it — the containment problem named in
    # this module's docstring, point 4.
    detail_keys = (
        "account_id",
        "account_label",
        "card_last_four",
        "dispute_amount",
        "dispute_merchant",
        "dispute_date",
    )
    # A fresh dict, never an alias into `session`. `Intent` is frozen, but
    # `frozen=True` stops rebinding the attribute, not mutating the dict behind
    # it — and because `summary` recomputes on every read, a post-handoff
    # mutation would silently rewrite what the desk sees.
    details = {key: allowed[key] for key in detail_keys if allowed.get(key) is not None}

    intent = Intent(
        goal=allowed.get("goal") or "unknown",
        goal_label=allowed.get("goal_label"),
        details=details,
        stage=allowed.get("goal_stage") or "stated",
    )

    # Defensive on shape, not just on keys. This function's entire contract is
    # that it does not trust its input — a caller who hands it a malformed
    # `attempts` (a bare string, a list of strings, a None) must get a package
    # with no attempts, never a traceback. A boundary that crashes on bad input
    # is a boundary that gets wrapped in a bare `except` by the next person, and
    # then it is not a boundary at all.
    raw_attempts = allowed.get("attempts")
    if isinstance(raw_attempts, (str, bytes)) or not isinstance(raw_attempts, (list, tuple)):
        raw_attempts = ()
    attempts = tuple(
        Attempt(
            action=str(item.get("action", "unknown")),
            outcome=item.get("outcome", "failed"),
            detail=item.get("detail"),
            code=item.get("code"),
        )
        for item in raw_attempts
        if isinstance(item, dict)
    )

    do_not_repeat = DoNotRepeat(
        questions_answered=_str_tuple(allowed.get("questions_answered")),
        factors_verified=_str_tuple(allowed.get("factors_verified")),
        confirmed_facts=_str_tuple(allowed.get("confirmed_facts")),
    )

    return HandoffPackage(
        handoff_id=handoff_id,
        reason=allowed.get("handoff_reason") or "Caller asked for a human.",
        identity=identity,
        intent=intent,
        attempts=attempts,
        do_not_repeat=do_not_repeat,
        withheld_fields=withheld if ANNOUNCE_WITHHELD else (),
    )
