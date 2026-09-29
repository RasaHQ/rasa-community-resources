"""Northgate Bank card service and the block-card guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three rules of the casebook contract for ``banking-block-card``
(vendored as ``lib/fixtures/case-contract.json``):

- ``selected_card_owned`` (request): the card belongs to the caller this
  session verified. An unverified session owns no card.
- ``single_card_confirmed`` (request): the card being blocked is the one card
  ``select_card`` resolved and the caller confirmed. The engine's confirmation
  gate asks the question; this module checks the block names the same card.
- ``block_state_read_back`` (receipt): after the block, the same card read
  back from the card service says ``blocked``. When the read fails the block
  is ``pending``, never ``succeeded``.

Facts are computed here from trusted data and session state. The model
supplies a name, a date of birth, a card ending and a card reference copied
from a tool result. It never supplies a fact, a customer id or an outcome.
A fact that is not exactly ``True`` fails its rule, as in the lab's
``evaluate``.

Card state lives in an in-process service with one copy of the fixture per
conversation, so every scripted call starts from the same cards.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "northgate.json"

# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))

CARD_KINDS = ("debit", "credit", "prepaid")
_SPACE_RE = re.compile(r"\s+")
_NAME_DROP_RE = re.compile(r"[^a-z\s'-]")


def load_contract() -> dict:
    return json.loads(json.dumps(_CONTRACT))


def load_data() -> dict:
    return json.loads(json.dumps(_DATA))


def rules(phase: str, contract: Optional[dict] = None) -> list[dict]:
    contract = contract or _CONTRACT
    return [rule for rule in contract["rules"] if rule["phase"] == phase]


def evaluate(facts: dict, phase: str, contract: Optional[dict] = None) -> Optional[str]:
    """First failing rule's reason for *phase*, or None. Exactly ``True`` passes."""
    for rule in rules(phase, contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8].upper()


def spoken_digits(digits: str) -> str:
    """'4417' -> '4 4 1 7', so text-to-speech reads a card ending digit by digit."""
    return " ".join(digits)


def card_label(card: dict) -> str:
    return f"{card['kind']} card ending {spoken_digits(card['last_four'])} on your {card['account']}"


def normalise_name(value: Any) -> str:
    text = _NAME_DROP_RE.sub("", str(value or "").lower())
    return _SPACE_RE.sub(" ", text).strip()


def normalise_last_four(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


class CardService:
    """The authoritative card service for one conversation (fixture copy)."""

    def __init__(self, data: Optional[dict] = None) -> None:
        data = data or load_data()
        self.cards: dict[str, dict] = data["cards"]
        self.customers: dict[str, dict] = data["customers"]
        self.replacements: list[dict] = []

    def cards_of(self, customer_id: Optional[str]) -> dict[str, dict]:
        return {ref: c for ref, c in self.cards.items() if customer_id and c["customer_id"] == customer_id}

    def snapshot(self, customer_id: Optional[str]) -> dict[str, Optional[str]]:
        """Every card of the customer as the service reads it back (None: unreadable)."""
        return {ref: self.read_back(ref) for ref in sorted(self.cards_of(customer_id))}

    def set_blocked(self, card_ref: str) -> None:
        self.cards[card_ref]["state"] = "blocked"

    def read_back(self, card_ref: str) -> Optional[str]:
        """The card's state as the service reports it, or None when unavailable."""
        card = self.cards.get(card_ref)
        if card is None or card.get("read_back") != "ok":
            return None
        return card["state"]


_SERVICES: dict[str, CardService] = {}


def service_for(conversation_id: str) -> CardService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = CardService()
    return _SERVICES[conversation_id]


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------


def verify_caller(service: CardService, full_name: str, date_of_birth: str) -> dict:
    """Match a spoken name and date of birth against the customer records."""
    name = normalise_name(full_name)
    dob = str(date_of_birth or "").strip()
    for customer_id, person in service.customers.items():
        expected = normalise_name(f"{person['first_name']} {person['last_name']}")
        if name == expected and dob == person["date_of_birth"]:
            return {
                "status": "verified",
                "customer_id": customer_id,
                "first_name": person["first_name"],
                "card_count": len(service.cards_of(customer_id)),
                "next_step": "Ask which card, by its last four digits, if the caller has not said.",
            }
    return {
        "status": "not_verified",
        "reason": "identity_mismatch",
        "next_step": (
            "Say the details did not match and ask the caller to repeat their full "
            "name and date of birth. Do not list, select or block any card."
        ),
    }


def _blocked(reason: str, **extra: Any) -> dict:
    next_step = {
        "card_not_owned": (
            "Say you cannot find a card with that ending for the verified caller "
            "and ask them to check it. Never say whether it belongs to anyone else. "
            "If the caller is not verified, verify them first."
        ),
        "ambiguous_card_selection": (
            "More than one card could match, or the card to block is not the one "
            "the caller confirmed. Read the candidates by kind and account and ask "
            "which one. Do not block anything yet."
        ),
    }[reason]
    return {"status": "blocked", "reason": reason, "effects": 0, **extra, "next_step": next_step}


def select_card(
    service: CardService,
    customer_id: Optional[str],
    card_last_four: str,
    card_kind: Optional[str] = None,
) -> dict:
    """Resolve a spoken card ending to exactly one of the verified caller's cards."""
    ending = normalise_last_four(card_last_four)
    kind = (card_kind or "").strip().lower() or None
    if not customer_id:
        return _blocked("card_not_owned", caller_verified=False, card_last_four=ending)
    owned = [
        (ref, c)
        for ref, c in sorted(service.cards_of(customer_id).items())
        if c["last_four"] == ending and (kind is None or c["kind"] == kind)
    ]
    if not owned:
        # Someone else's card and a card that does not exist get the same
        # answer, so the tool never confirms a number belongs to another customer.
        return _blocked("card_not_owned", caller_verified=True, card_last_four=ending)
    if len(owned) > 1:
        return _blocked(
            "ambiguous_card_selection",
            card_last_four=ending,
            candidates=[card_label(c) for _, c in owned],
        )
    ref, card = owned[0]
    return {
        "status": "selected",
        "card_ref": ref,
        "card_label": card_label(card),
        "state": card["state"],
        "next_step": (
            "Call block_card with this card_ref. The engine asks the caller to "
            "confirm this card before anything changes."
        ),
    }


def block_card(
    service: CardService,
    customer_id: Optional[str],
    selected_card_ref: Optional[str],
    card_ref: str,
    request_id: str,
) -> dict:
    """Block one confirmed card and prove it from a read-back of every card."""
    ref = str(card_ref or "").strip().upper()
    card = service.cards.get(ref)
    facts = {
        "selected_card_owned": bool(customer_id) and card is not None and card["customer_id"] == customer_id,
        "single_card_confirmed": bool(selected_card_ref) and ref == selected_card_ref,
    }
    reason = evaluate(facts, "request")
    if reason:
        return _blocked(reason, card_ref=ref, facts=facts)

    before = service.snapshot(customer_id)
    replay = card["state"] == "blocked"
    if not replay:
        service.set_blocked(ref)
    read_state = service.read_back(ref)
    after_reads = service.snapshot(customer_id)
    # An unreadable card counts as changed: the evidence cannot show it was not.
    unselected_changed = sorted(r for r in before if r != ref and after_reads[r] != before[r])
    facts["block_state_read_back"] = read_state == "blocked"
    receipt_failure = evaluate(facts, "receipt")
    reference = f"NB-BLK-{_digest(request_id, ref)}"
    result = {
        "status": "pending" if receipt_failure else "succeeded",
        "reason": receipt_failure or "verified_fixture_receipt",
        "card_ref": ref,
        "card_label": card_label(card),
        "reference": reference,
        "effects": 0 if replay else 1,
        "replay": replay,
        "read_back_state": read_state,
        "cards_before": before,
        "cards_after": after_reads,
        "unselected_cards_changed": len(unselected_changed),
        "replacement_ordered": False,
        "facts": facts,
    }
    if receipt_failure:
        result["next_step"] = (
            "The block was sent but the card service did not confirm it. Say the "
            "block is not confirmed yet, call check_card_status for this same card, "
            "and if it is still unknown call route_urgent_support. Do not order a "
            "replacement."
        )
    else:
        result["next_step"] = (
            "Say this one card is blocked, give the reference, and say the other "
            "cards are unchanged. Blocking does not order a replacement; offer one "
            "only if the caller asks."
        )
    return result


def check_card_status(service: CardService, customer_id: Optional[str], card_ref: str) -> dict:
    ref = str(card_ref or "").strip().upper()
    card = service.cards.get(ref)
    if card is None or not customer_id or card["customer_id"] != customer_id:
        return _blocked("card_not_owned", card_ref=ref)
    state = service.read_back(ref)
    return {
        "status": "read" if state else "unknown",
        "card_ref": ref,
        "card_label": card_label(card),
        "state": state,
        "next_step": (
            "Report the state." if state else
            "The card service cannot confirm this card's state. Call route_urgent_support."
        ),
    }


def route_urgent_support(service: CardService, customer_id: Optional[str], card_ref: str, reason: str) -> dict:
    ref = str(card_ref or "").strip().upper()
    card = service.cards.get(ref)
    if card is None or not customer_id or card["customer_id"] != customer_id:
        return _blocked("card_not_owned", card_ref=ref)
    return {
        "status": "routed",
        "card_ref": ref,
        "reference": f"NB-URG-{_digest(customer_id, ref, 'urgent')}",
        "route": "card services urgent desk",
        "reason": " ".join(str(reason or "").split())[:200],
        "next_step": "Give the reference. The urgent desk calls back within 15 minutes.",
    }


def order_replacement_card(service: CardService, customer_id: Optional[str], card_ref: str) -> dict:
    """A separate request, only for a card whose block the service confirmed."""
    ref = str(card_ref or "").strip().upper()
    card = service.cards.get(ref)
    if card is None or not customer_id or card["customer_id"] != customer_id:
        return _blocked("card_not_owned", card_ref=ref)
    if service.read_back(ref) != "blocked":
        return {
            "status": "refused",
            "reason": "block_not_verified",
            "card_ref": ref,
            "next_step": "A replacement needs a confirmed block. Do not order one.",
        }
    order = {"card_ref": ref, "reference": f"NB-REP-{_digest(customer_id, ref, 'replace')}"}
    service.replacements.append(order)
    return {
        "status": "ordered",
        **order,
        "card_label": card_label(card),
        "delivery": "5 to 7 business days to the address on file",
    }
