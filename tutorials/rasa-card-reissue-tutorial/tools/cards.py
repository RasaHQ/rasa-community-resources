"""The tools the agent may call, and the one line that matters in each.

Every function that changes the world in this module has the same shape:

    resolve inputs -> classify provenance -> GUARD -> act -> return an Outcome

The guard call is never optional, never conditional on a flag, and never
preceded by the side effect. If you are reading this file to copy the pattern,
that ordering is the pattern.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from cardpolicy import (
    ReissueRefused,
    classify_address,
    guard_reissue,
    request_fingerprint,
    succeeded,
)
from cardpolicy.outcomes import Outcome, Result, refused

_DATA = Path(__file__).resolve().parent.parent / "data" / "source" / "customers.json"

# The demo customer. A real deployment resolves this from the authenticated
# session; hardcoding it keeps the tutorial about card policy rather than about
# identity plumbing, and it is stated in the README so nobody ships it.
DEMO_CUSTOMER_ID = "C-40218"

# In-memory ledger of reissues placed during this process, keyed by request
# fingerprint. A real deployment uses the card-issuing system's own
# idempotency key; the shape of the lookup is what the tutorial teaches.
_PLACED: dict[str, str] = {}


def _load() -> dict[str, Any]:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def _customer(data: dict[str, Any]) -> dict[str, Any]:
    for record in data["customers"]:
        if record["customer_id"] == DEMO_CUSTOMER_ID:
            return record
    raise LookupError(f"fixture is missing {DEMO_CUSTOMER_ID}")


async def list_cards() -> dict[str, Any]:
    """The caller's cards, by last four digits.

    Never returns a full card number. The agent has no use for one and a
    transcript is a place numbers leak from.
    """
    data = _load()
    cards = [
        {"card_id": c["card_id"], "last4": c["last4"], "product": c["product"], "status": c["status"]}
        for c in data["cards"]
        if c["customer_id"] == DEMO_CUSTOMER_ID
    ]
    return {"ok": True, "cards": cards}


async def list_addresses_on_file() -> dict[str, Any]:
    """Addresses the bank held BEFORE this call started.

    Offered to the caller first, deliberately. The cheapest safe path is the
    one where the caller picks a destination the bank already knew, and an
    agent that asks "what's your address?" before offering the ones on file has
    pushed every caller onto the expensive path for no reason.
    """
    customer = _customer(_load())
    return {
        "ok": True,
        "addresses": [
            {
                "address_id": a["address_id"],
                "label": a["label"],
                "spoken": f"{a['line1']}, {a['city']}, {a['postcode']}",
            }
            for a in customer["addresses_on_file"]
        ],
    }


async def reissue_card(
    card_id: str,
    line1: str,
    city: str,
    postcode: str,
    auth_tier: str = "none",
) -> dict[str, Any]:
    """Order a replacement card. Irreversible once it returns ok.

    `auth_tier` is passed in rather than read from a global so that the guard's
    input is visible at the call site and in every test. A guard whose inputs
    are ambient is a guard nobody can reason about.
    """
    data = _load()
    customer = _customer(data)

    card = next(
        (c for c in data["cards"] if c["card_id"] == card_id and c["customer_id"] == DEMO_CUSTOMER_ID),
        None,
    )
    if card is None:
        return _as_dict(
            refused(Result.REFUSED, "I could not find that card on this account.")
        )

    address = classify_address(line1, city, postcode, customer["addresses_on_file"])

    on_file_since = None
    if address.address_id is not None:
        record = next(
            a for a in customer["addresses_on_file"] if a["address_id"] == address.address_id
        )
        on_file_since = date.fromisoformat(record["on_file_since"])

    # ---- the line before the side effect --------------------------------
    try:
        guard_reissue(address, auth_tier, on_file_since=on_file_since)
    except ReissueRefused as exc:
        return _as_dict(exc.outcome)
    # ---------------------------------------------------------------------

    fingerprint = request_fingerprint(card_id, postcode, line1)
    if fingerprint in _PLACED:
        return _as_dict(succeeded(_PLACED[fingerprint], duplicate=True))

    reference = f"RC-{uuid.uuid4().hex[:8].upper()}"
    _PLACED[fingerprint] = reference
    return _as_dict(succeeded(reference))


def _as_dict(outcome: Outcome) -> dict[str, Any]:
    """Flatten an Outcome for the tool boundary.

    `ok` is derived from `outcome.acted`, never set by hand. That is the whole
    reason `acted` exists: there is one expression in this project that decides
    whether something happened, and every caller reads it rather than
    re-deriving it from a result code they might get subtly wrong.
    """
    payload: dict[str, Any] = {
        "ok": outcome.acted,
        "result": outcome.result.value,
        "message": outcome.message,
    }
    if outcome.reference is not None:
        payload["reference"] = outcome.reference
    payload.update(outcome.detail)
    return payload
