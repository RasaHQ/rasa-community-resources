"""Where a tier is DECLARED: one table, keyed by action, not by caller.

This table is the pattern's central claim in executable form. Read down the
`tier` column and notice what it is a function of: what the action *does* if it
succeeds. Not who is asking, not which skill they entered through, not how far
into the call they are.

Two rows are worth comparing before you copy this:

    check_balance   MEDIUM   reads an account
    reissue_card    HIGH     mails a card to an address the caller just supplied

Same customer, same call, same voice on the line. Different tiers, because the
blast radius of getting it wrong is different by three orders of magnitude. An
agent that authenticates "the caller" once at the top of the call cannot express
that difference — it has already spent its only decision.

ADDING AN ACTION: add a row. The guard reads this table, so a tool with no row
is refused at HIGH (see `tier_for`) rather than waved through. Forgetting to
classify a new action is the most likely human error here, so the default is the
strict one.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tiers import AuthTier


@dataclass(frozen=True)
class ActionPolicy:
    """The declared risk of one action, and how to talk about it out loud."""

    action: str
    tier: AuthTier
    reason: str
    """Why this tier. Shown in the refusal payload so a caller — and a log
    reader six months later — can see the classification, not just the denial."""

    irreversible: bool = False
    """True when a success cannot be undone by the caller. Not used by the
    guard; used by the tutorial's argument for why HIGH is HIGH."""


# The declaration table. `tier` is a property of the row, i.e. of the action.
_POLICIES: tuple[ActionPolicy, ...] = (
    # ---- LOW: public information. Nothing here identifies a caller. --------
    ActionPolicy(
        action="get_store_hours",
        tier=AuthTier.LOW,
        reason="Branch opening hours are published on the public website.",
    ),
    ActionPolicy(
        action="get_fee_schedule",
        tier=AuthTier.LOW,
        reason="The fee schedule is public and identical for every customer.",
    ),
    # ---- MEDIUM: account-specific reads. A knowledge factor is proportionate.
    ActionPolicy(
        action="get_balance",
        tier=AuthTier.MEDIUM,
        reason="Reveals an account balance tied to one customer.",
    ),
    ActionPolicy(
        action="get_recent_bill",
        tier=AuthTier.MEDIUM,
        reason="Reveals billing history tied to one customer.",
    ),
    # ---- HIGH: irreversible, or the thing an attacker actually wants. ------
    ActionPolicy(
        action="reissue_card",
        tier=AuthTier.HIGH,
        reason=(
            "Mails a payment instrument to an address supplied during this "
            "call. Irreversible once posted, and the classic account-takeover "
            "objective."
        ),
        irreversible=True,
    ),
    ActionPolicy(
        action="transfer_funds",
        tier=AuthTier.HIGH,
        reason="Moves money out of the account and cannot be recalled by the caller.",
        irreversible=True,
    ),
)

POLICIES: dict[str, ActionPolicy] = {policy.action: policy for policy in _POLICIES}


def tier_for(action: str) -> AuthTier:
    """The tier an action demands. Unknown actions demand HIGH.

    Failing closed on an unlisted action is the single most important line in
    this module. The alternative — defaulting to LOW, or to "no policy means no
    check" — means that the day someone adds `close_account` and forgets the
    table, the guard waves it through and reports success. A registry that is
    permissive by omission is not a registry; it is an allowlist that anyone can
    join by accident.
    """
    policy = POLICIES.get(action)
    return policy.tier if policy is not None else AuthTier.HIGH


def reason_for(action: str) -> str:
    """Human-readable justification for an action's tier."""
    policy = POLICIES.get(action)
    if policy is None:
        return (
            f"{action!r} has no declared risk tier, so it is treated as "
            f"high risk until one is declared."
        )
    return policy.reason
