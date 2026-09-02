"""Policy for an action that leaves the building.

Reissuing a card is not a database write. It is a physical object posted to an
address, and once it is in the post nothing this agent can do recalls it. That
single property — irreversibility with a caller-supplied destination — is what
the four modules here exist to handle.

    provenance.py   is this address a fact ON FILE, or a fact SAID ON THE CALL?
    guard.py        the check that runs on the line before the side effect
    idempotency.py  the same request twice must post one card, not two
    outcomes.py     the vocabulary of results, including the ones that must
                    never be dressed up as success
"""

from .guard import ReissueRefused, guard_reissue
from .idempotency import request_fingerprint
from .outcomes import Outcome, refused, succeeded
from .provenance import AddressProvenance, classify_address

__all__ = [
    "AddressProvenance",
    "Outcome",
    "ReissueRefused",
    "classify_address",
    "guard_reissue",
    "refused",
    "request_fingerprint",
    "succeeded",
]
