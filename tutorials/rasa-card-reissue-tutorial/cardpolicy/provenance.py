"""Where a delivery address CAME FROM, which is not the same as what it says.

THE DISTINCTION THIS MODULE EXISTS FOR
--------------------------------------
An agent that reissues a card needs a destination. There are exactly two ways
it can get one, and they are not interchangeable:

    ON_FILE     the address was in the customer record before this call began
    STATED      the caller said it out loud during this call

A naive agent treats these as one thing — "the address" — because by the time
the value reaches the tool it is a string either way, and strings do not
remember where they came from. That is the whole vulnerability. Account
takeover does not need to defeat the address check; it needs the agent to
forget that a check was owed, and a bare string forgets by default.

So provenance is not derived, inferred, or guessed. It is CARRIED, as a
separate field, from the moment the address enters the system to the moment the
guard reads it. `classify_address` is the only place a string becomes a
provenance-bearing value, and it decides by looking the address up in the
customer record rather than by trusting anything the caller or the model said
about it.

WHY NOT JUST BAN STATED ADDRESSES
---------------------------------
Because people move, and a customer whose card was stolen along with their
wallet is exactly the customer most likely to have moved recently. Refusing
every new address makes the agent useless for the case it was built for. The
answer is not to ban the harder path but to price it: a STATED address is
allowed, and it costs a stronger factor and a cooling-off period. See
`guard.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AddressProvenance(str, Enum):
    """How the system came to know this address.

    Subclasses `str` so the value round-trips through Rasa memory — which
    stores text — without a conversion layer on either side.
    """

    ON_FILE = "on_file"
    """Present in the customer record before this conversation started."""

    STATED = "stated"
    """Supplied by the caller during this conversation. Unverified."""

    UNKNOWN = "unknown"
    """Provenance was lost or never recorded. Treated as STATED-or-worse.

    This value should never appear in a healthy run. It exists because the
    alternative to representing "we do not know" is pretending we do, and a
    guard that cannot express doubt will resolve doubt in favour of proceeding.
    """


@dataclass(frozen=True)
class ClassifiedAddress:
    """An address together with the thing about it that actually matters."""

    line1: str
    city: str
    postcode: str
    provenance: AddressProvenance
    address_id: str | None = None
    """Set only for ON_FILE addresses. A STATED address has no id because it
    is not yet a record of anything."""

    @property
    def spoken(self) -> str:
        """One line, readable aloud. Used in confirmations, never in logs."""
        return f"{self.line1}, {self.city}, {self.postcode}"


def _normalise(value: str) -> str:
    """Collapse the differences that do not change where the post lands.

    Case and internal whitespace are noise; `BS1 4TR`, `bs1  4tr`, and
    `BS14TR` are the same postcode. Normalising before comparison is what stops
    a caller who reads their own on-file address back slightly differently from
    being treated as if they had supplied a new one — an annoyance, but one
    that pushes them onto the STATED path and costs them a code they did not
    need to enter.
    """
    return " ".join(value.split()).replace(" ", "").casefold()


def classify_address(
    line1: str,
    city: str,
    postcode: str,
    addresses_on_file: list[dict[str, str]],
) -> ClassifiedAddress:
    """Decide provenance by looking it up, never by being told.

    The signature is deliberate: this function takes the customer's real
    address list as an argument and compares against it. It does not accept a
    `provenance` parameter, because a function that accepts the answer to the
    question it is supposed to decide is not a check — it is a formality that
    the caller, the model, or a future refactor can satisfy by passing the
    convenient value.
    """
    target = (_normalise(line1), _normalise(postcode))
    for record in addresses_on_file:
        candidate = (_normalise(record["line1"]), _normalise(record["postcode"]))
        if candidate == target:
            return ClassifiedAddress(
                line1=record["line1"],
                city=record["city"],
                postcode=record["postcode"],
                provenance=AddressProvenance.ON_FILE,
                address_id=record["address_id"],
            )
    return ClassifiedAddress(
        line1=line1,
        city=city,
        postcode=postcode,
        provenance=AddressProvenance.STATED,
    )
