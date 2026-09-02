"""The tools the agent may call, and the one line that matters in each.

Every function that changes the world in this module has the same shape:

    resolve inputs -> classify provenance -> GUARD -> act -> return an Outcome

The guard call is never optional, never conditional on a flag, and never
preceded by the side effect. If you are reading this file to copy the pattern,
that ordering is the pattern.

Two layers, on purpose:

* ``place_reissue`` is the PURE function: every input explicit, including
  ``auth_tier``. It is what ``scripts/prove_guard.py`` exercises, because a
  guard whose inputs are ambient is a guard nobody can reason about — or prove.
* ``reissue_card`` is the thin ``@tool`` wrapper the AGENT calls. It reads
  ``auth_tier`` from project memory, which only the verification tools write
  (``memory.yml`` marks it ``llm_settable: false``), and the engine's tool
  schema exposes only the address arguments. The tier is deliberately NOT a
  tool parameter: the schema generator publishes every non-``context``
  parameter to the model, and a model-fillable ``auth_tier`` would let the
  agent talk itself past the guard — the exact hole this tutorial teaches you
  to close.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any

try:
    from rasa.mantle.tools.decorator import ToolContext, tool
    from rasa.mantle.tools.result import ToolResult
except ModuleNotFoundError:  # pragma: no cover — the bare-python proof path
    # `make policy` runs under bare python3, with no venv and no engine, and
    # exercises only `place_reissue`. These shims exist solely so this module
    # imports there; the agent runtime always has the real engine, and the
    # loader only ever sees these tools through it.
    ToolContext = None  # type: ignore[assignment,misc]

    def tool(*, description):  # type: ignore[no-redef]
        def _wrap(func):
            func._tool_description = description
            return func
        return _wrap

    class ToolResult:  # type: ignore[no-redef]
        def __init__(self, llm_response=None):
            self.llm_response = llm_response

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


@tool(description="List the caller's cards by product and last four digits.")
async def list_cards(context: ToolContext = None) -> ToolResult:
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
    return ToolResult(llm_response={"ok": True, "cards": cards})


@tool(
    description=(
        "List the addresses the bank already holds for this customer. Offer "
        "these before ever asking the caller for an address."
    )
)
async def list_addresses_on_file(context: ToolContext = None) -> ToolResult:
    """Addresses the bank held BEFORE this call started.

    Offered to the caller first, deliberately. The cheapest safe path is the
    one where the caller picks a destination the bank already knew, and an
    agent that asks "what's your address?" before offering the ones on file has
    pushed every caller onto the expensive path for no reason.
    """
    customer = _customer(_load())
    return ToolResult(
        llm_response={
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
    )


async def place_reissue(
    card_id: str,
    line1: str,
    city: str,
    postcode: str,
    auth_tier: str = "none",
) -> dict[str, Any]:
    """Order a replacement card. Irreversible once it returns ok.

    `auth_tier` is passed in rather than read from anything ambient so that
    the guard's input is visible at the call site and in every proof case.
    This is the function `scripts/prove_guard.py` drives.
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


@tool(
    description=(
        "Order a replacement card to the given address. Refuses with "
        "step_up_required when the caller's verification is not strong enough "
        "for where the card is going."
    )
)
async def reissue_card(
    card_id: str,
    line1: str,
    city: str,
    postcode: str,
    context: ToolContext = None,
) -> ToolResult:
    """The agent-facing wrapper: same guard, tier read from memory.

    The tier comes from ``session.project.auth_tier``, written only by the
    verification flow — never from a tool argument the model could fill. See
    the module docstring for why that distinction is the whole point.
    """
    held_tier = "none"
    if context is not None:
        held_tier = str(context.memory.get("auth_tier") or "none")
    return ToolResult(
        llm_response=await place_reissue(
            card_id, line1, city, postcode, auth_tier=held_tier
        )
    )


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
