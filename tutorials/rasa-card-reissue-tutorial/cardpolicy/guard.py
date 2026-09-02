"""The check that runs on the line before the side effect.

WHY THIS IS NOT A `tool_constraints` ENTRY
------------------------------------------
Rasa gives you a declarative way to say "this tool needs X":

    tool_constraints:
      - reissue_card:
          requires: session.project.verified

That is a real control and this project uses it — see
`skills/card_reissue/skill.md`. But understand what it controls. The
orchestrator evaluates it against conversation state to decide which tools the
model is OFFERED. It shapes the conversation, so the caller gets asked to
verify instead of being told "no" for reasons they cannot see. That is worth
having and it is a ROUTING control.

It is not an EXECUTION control. It does not run when the function runs. If the
YAML key is misspelled it is silently ignored; if a future skill imports this
tool without the constraint it is simply absent; if the model is swapped for
one that reasons differently the offer set changes. In every one of those
cases the function still gets entered, and the card still gets posted.

So the two layers are both present and they are not redundant:

    tool_constraints   outer, declarative, shapes the dialogue    (can be bypassed)
    guard_reissue()    inner, imperative, gates the side effect   (cannot)

The test for whether you have understood this: `tests/test_guard.py` calls the
tool directly with no model in the loop at all and asserts nothing was posted.
A routing control cannot be tested that way, because there is no route.

THE THREE THINGS THIS GUARD CHECKS
----------------------------------
1. Verification strength reaches what a reissue demands.
2. A STATED destination costs more than an ON_FILE one.
3. A destination added moments ago is not usable yet.

Point 3 is the one people leave out, and it is the one that closes the loop.
Without it an attacker who can reach the "add an address" flow simply adds
their address, which is then ON_FILE, and walks through the front door. A
cooling-off window means the address is on file and still not good enough,
which is the only thing that makes the ON_FILE/STATED distinction worth
carrying.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .outcomes import Outcome, Result, refused
from .provenance import AddressProvenance, ClassifiedAddress

# How long a newly-added address must sit before a card may be posted to it.
#
# Seven days is a policy number, not a technical one, and a real bank sets it
# from its own fraud data. It is named here rather than inlined so that the one
# place it lives is the one place it is argued about.
COOLING_OFF = timedelta(days=7)

# The verification strength a reissue demands, by destination provenance.
#
# Read this table the way `voice-auth-stepup` asks you to read its own: the
# requirement is a property of what the action DOES, and here the action does
# something materially different depending on where the card lands. Posting to
# an address the bank has held for six years is not the same act as posting to
# one supplied ninety seconds ago by a voice on the phone.
REQUIRED_TIER = {
    AddressProvenance.ON_FILE: "medium",
    AddressProvenance.STATED: "high",
    AddressProvenance.UNKNOWN: "high",
}

_TIER_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


class ReissueRefused(Exception):
    """Raised when a reissue must not proceed.

    Carries the `Outcome` rather than a string so the tool layer returns
    exactly what the guard decided, and cannot soften it in transit.
    """

    def __init__(self, outcome: Outcome) -> None:
        self.outcome = outcome
        super().__init__(outcome.message)


@dataclass(frozen=True)
class Decision:
    """One guard evaluation, in a form a test can assert on."""

    allowed: bool
    required_tier: str
    held_tier: str
    provenance: AddressProvenance
    reason: str


def _rank(tier: object) -> int:
    """Read a tier out of memory, failing CLOSED on anything unexpected.

    Memory is text, may be absent on the first turn, may be stale, and may be
    something a model invented. Every one of those resolves to rank 0 rather
    than raising, because a guard that throws on unexpected input is a guard
    that gets wrapped in a bare `except` inside a month.
    """
    if isinstance(tier, str):
        return _TIER_RANK.get(tier.strip().casefold(), 0)
    return 0


def evaluate(
    address: ClassifiedAddress,
    held_tier: object,
    *,
    today: date | None = None,
    on_file_since: date | None = None,
) -> Decision:
    """Decide, without acting. Separated from `guard_reissue` so the decision
    is testable in isolation and loggable whether or not it was enforced."""
    required = REQUIRED_TIER[address.provenance]
    held = held_tier if isinstance(held_tier, str) else "none"

    if _rank(held) < _TIER_RANK[required]:
        return Decision(
            allowed=False,
            required_tier=required,
            held_tier=held,
            provenance=address.provenance,
            reason=(
                "A card sent to an address given during the call needs a "
                "one-time code."
                if address.provenance is not AddressProvenance.ON_FILE
                else "Ordering a replacement card needs the caller verified."
            ),
        )

    # Cooling-off applies to ON_FILE addresses precisely because ON_FILE is the
    # cheaper path. An address that became ON_FILE recently has not yet earned
    # the discount that being ON_FILE buys.
    if (
        address.provenance is AddressProvenance.ON_FILE
        and on_file_since is not None
        and (today or date.today()) - on_file_since < COOLING_OFF
    ):
        return Decision(
            allowed=False,
            required_tier=required,
            held_tier=held,
            provenance=address.provenance,
            reason=(
                "That address was added too recently for a card to be sent to it."
            ),
        )

    return Decision(
        allowed=True,
        required_tier=required,
        held_tier=held,
        provenance=address.provenance,
        reason="Verification and destination both satisfy policy.",
    )


def guard_reissue(
    address: ClassifiedAddress,
    held_tier: object,
    *,
    today: date | None = None,
    on_file_since: date | None = None,
) -> Decision:
    """Enforce. Raises `ReissueRefused` rather than returning False.

    Raising rather than returning a boolean is the point. A boolean can be
    ignored by writing `guard_reissue(...)` on its own line and carrying on —
    which reads, at a glance, exactly like calling a guard. An exception cannot
    be ignored that way. The only route past this function is a return.
    """
    decision = evaluate(
        address, held_tier, today=today, on_file_since=on_file_since
    )
    if decision.allowed:
        return decision

    if decision.reason.startswith("That address was added too recently"):
        raise ReissueRefused(
            refused(
                Result.COOLING_OFF,
                decision.reason
                + " Please use an address that has been on file longer, or"
                " speak to someone who can verify the change.",
                provenance=decision.provenance.value,
            )
        )

    raise ReissueRefused(
        refused(
            Result.STEP_UP_REQUIRED,
            decision.reason,
            required_tier=decision.required_tier,
            held_tier=decision.held_tier,
            provenance=decision.provenance.value,
        )
    )
