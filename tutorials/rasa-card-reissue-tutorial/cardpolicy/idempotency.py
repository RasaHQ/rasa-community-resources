"""Making an irreversible action safe to attempt twice.

THE PROBLEM
-----------
Voice is a lossy channel. The caller says "yes, send it", the tool posts the
card, and the confirmation is cut off by a dropped packet or the caller talking
over it. The model does not know the tool succeeded, so it does the reasonable
thing and tries again. Two cards are now in the post to the same address, and
the bank has two live card numbers where it intended one.

Nothing about that sequence is a bug in any single component. Every part
behaved correctly. It is a bug in the ASSUMPTION that calling a tool twice is
the same as calling it twice as much.

THE FIX, AND WHY IT IS A FINGERPRINT AND NOT A FLAG
---------------------------------------------------
A boolean `already_reissued` would be wrong, because a caller genuinely can
need two different cards replaced on one call — the debit card and the credit
card, both in the stolen wallet. What must not happen twice is the SAME
request, not any second request.

So the key is a fingerprint of what makes a request distinct: which card, to
which address. Same fingerprint, same reference, no second card. Different
fingerprint, a real second order.

The fingerprint deliberately includes the destination. Replacing card 9931 to
the home address and then to a newly-stated address are different requests, and
the second one must go through the guard again rather than inheriting the
first's success.
"""

from __future__ import annotations

import hashlib


def request_fingerprint(card_id: str, postcode: str, line1: str) -> str:
    """A stable id for "this exact reissue request".

    Hashed rather than concatenated for one reason: this value is written to
    conversation memory, which is a place a transcript may end up. A hash of an
    address is not an address.

    Truncated to 16 hex characters — 64 bits. Collision risk within a single
    phone call, where the number of distinct requests is in the single digits,
    is not a real quantity.
    """
    canonical = "|".join(
        part.strip().casefold() for part in (card_id, postcode, line1)
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
