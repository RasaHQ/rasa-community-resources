"""Willow Shop order tracking and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three request-phase rules of the casebook contract for
``retail-order-status`` (vendored as ``lib/fixtures/case-contract.json``):

- ``order_subject_resolved``: the order belongs to the customer signed in on
  this session, and the question resolves to exactly one parcel of it.
- ``carrier_event_current``: the carrier's tracking feed was observed within
  the freshness window, measured on the fixture clock.
- ``milestone_type_explicit``: the parcel's latest event names its milestone
  (label created, carrier accepted, in transit, out for delivery, delivered)
  and comes from the source that can observe it: a label from the warehouse,
  everything after it from a carrier scan.

Facts are computed here from trusted data and the session's customer id. The
model supplies an order number and, for a split order, a parcel number. It
never supplies a fact, a customer id or a milestone. A fact that is not
exactly ``True`` fails its rule, as in the lab's ``evaluate``.

The organisation guard runs at import: the fixture must mark the retailer and
the carrier as fictional, and neither may name a real retailer or carrier.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "orders.json"

# Milestones and the only source that can observe each one. A warehouse can
# print a label; only a carrier scan can say the carrier has the parcel.
MILESTONE_SOURCES = {
    "label_created": "warehouse",
    "carrier_accepted": "carrier",
    "in_transit": "carrier",
    "out_for_delivery": "carrier",
    "delivered": "carrier",
}
CARRIER_MILESTONES = frozenset(m for m, s in MILESTONE_SOURCES.items() if s == "carrier")
SPOKEN_MILESTONE = {
    "label_created": "shipping label created; the carrier has not collected the parcel",
    "carrier_accepted": "collected by the carrier",
    "in_transit": "in transit with the carrier",
    "out_for_delivery": "out for delivery",
    "delivered": "delivered, according to the carrier",
}
ESTIMATE_KIND = {
    "checkout_estimate": "the delivery estimate shown at checkout, not a carrier event",
    "carrier_estimate": "the carrier's estimated delivery date, not a carrier event",
}

# Real retailers and carriers the fixture must never name. The fixture is
# public teaching data; a real brand in it would read as a claim about that
# company. This list is a tripwire, not a register of every brand.
REAL_BRANDS = (
    "amazon", "walmart", "target", "ikea", "wayfair", "etsy", "ebay", "shopify",
    "ups", "fedex", "usps", "dhl", "royal mail", "canada post", "ontrac", "lasership",
)


class FictionalOrganisationError(RuntimeError):
    """The fixture does not describe a clearly fictional organisation."""


def assert_fictional(data: dict) -> None:
    """Refuse fixture data that is not marked fictional or names a real brand."""
    for key in ("organisation", "carrier"):
        value = str(data.get(key) or "")
        if "(fictional" not in value.lower():
            raise FictionalOrganisationError(f"{key} must be marked '(fictional ...)': {value!r}")
        for brand in REAL_BRANDS:
            if re.search(rf"\b{re.escape(brand)}\b", value.lower()):
                raise FictionalOrganisationError(f"{key} names a real brand: {brand!r}")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")


# Read once, at import. Mantle imports tool modules from a temporary snapshot
# of lib/ and removes it after loading, so a file read at dispatch time fails.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA)

SESSION_CUSTOMER_ID = _DATA["session_customer_id"]
ORGANISATION = _DATA["organisation"].split(" (")[0]
CARRIER = _DATA["carrier"].split(" (")[0]


def load_contract() -> dict:
    return json.loads(json.dumps(_CONTRACT))


def load_data() -> dict:
    return json.loads(json.dumps(_DATA))


def request_rules(contract: Optional[dict] = None) -> list[dict]:
    contract = contract or load_contract()
    return [rule for rule in contract["rules"] if rule["phase"] == "request"]


def evaluate(facts: dict, contract: Optional[dict] = None) -> Optional[str]:
    """First failing rule's reason, or None. A fact must be exactly ``True``."""
    for rule in request_rules(contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


_DIGIT_WORDS = {
    "zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2", "three": "3",
    "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}


def normalise_order(value: Any) -> str:
    """'WS-10482', 'ws 10482', '10482' and 'one oh four eight two' -> 'WS-10482'.

    Anything that does not reduce to exactly five digits is returned upper-cased
    and stripped, so it fails the subject rule as an unknown order.
    """
    text = str(value or "").lower()
    tokens = re.findall(r"[a-z]+|\d+", text)
    digits = "".join(_DIGIT_WORDS.get(t, t if t.isdigit() else "") for t in tokens)
    if len(digits) == 5:
        return f"WS-{digits}"
    return re.sub(r"[^A-Z0-9-]", "", text.upper())


_ORDINALS = {"first": 1, "one": 1, "1": 1, "second": 2, "two": 2, "2": 2, "third": 3, "three": 3, "3": 3}


def normalise_parcel(value: Any) -> Optional[int]:
    """1, '2', 'second', 'parcel two' -> int; None or '' -> None; nonsense -> 0."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    for token in re.findall(r"[a-z]+|\d+", str(value).lower()):
        if token in _ORDINALS:
            return _ORDINALS[token]
    return 0


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def spoken_time(ts: str) -> str:
    """'2026-09-28T14:12:00-04:00' -> 'Monday, September 28 at 2:12 PM'."""
    t = _parse(ts)
    hour = t.strftime("%I").lstrip("0")
    return f"{t.strftime('%A, %B')} {t.day} at {hour}:{t.strftime('%M %p')}"


def spoken_date(day: str) -> str:
    t = datetime.fromisoformat(day)
    return f"{t.strftime('%A, %B')} {t.day}"


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8].upper()


def status_reference(data: dict, customer_id: str, order: str, parcel: int, observed_at: str) -> str:
    """A dated reference for one status answer: the case's receipt."""
    day = _parse(data["as_of"]).strftime("%Y%m%d")
    return f"WS-ST-{day}-{_digest(customer_id, order, str(parcel), observed_at)}"


def _age_hours(data: dict, ts: str) -> float:
    return round((_parse(data["as_of"]) - _parse(ts)).total_seconds() / 3600, 1)


def resolve_parcel(order: Optional[dict], customer_id: str, parcel_number: Any) -> tuple[Optional[dict], Optional[str]]:
    """The one parcel this question is about, or (None, why not)."""
    if order is None or order.get("customer_id") != customer_id:
        return None, "not_on_account"
    parcels = order["parcels"]
    wanted = normalise_parcel(parcel_number)
    if wanted is None:
        if len(parcels) == 1:
            return parcels[0], None
        return None, "parcel_not_selected"
    for parcel in parcels:
        if parcel["parcel_number"] == wanted:
            return parcel, None
    return None, "no_such_parcel"


def milestone_explicit(event: Optional[dict]) -> bool:
    if not event:
        return False
    milestone = event.get("milestone")
    return milestone in MILESTONE_SOURCES and event.get("source") == MILESTONE_SOURCES[milestone]


def facts_for(order: Optional[dict], parcel: Optional[dict], customer_id: str, data: dict) -> dict:
    """Compute the three contract facts from trusted data only."""
    if order is None or order.get("customer_id") != customer_id or parcel is None:
        # Unknown orders and someone else's orders fail the same rule with the
        # same payload, so the answer never confirms that a number exists for
        # another customer, nor anything about its tracking.
        return {"order_subject_resolved": False}
    window = timedelta(hours=data["carrier_freshness_hours"])
    observed = parcel.get("carrier_observed_at")
    latest = parcel["events"][-1] if parcel.get("events") else None
    return {
        "order_subject_resolved": True,
        "carrier_event_current": bool(observed) and _parse(data["as_of"]) - _parse(observed) <= window,
        "milestone_type_explicit": milestone_explicit(latest),
    }


NEXT_STEP = {
    "wrong_order": (
        "Say you cannot find that order number on this account and ask the "
        "customer to check it. Do not say whether it exists for anyone else."
    ),
    "no_such_parcel": (
        "That order has no parcel with that number. Say how many parcels it has "
        "and ask which one they mean."
    ),
    "parcel_not_selected": (
        "This order was split into more than one parcel, and each has its own "
        "tracking. Ask which parcel they mean, naming the items, or check each "
        "parcel with its own parcel_number. Never give one parcel's status for another."
    ),
    "stale_carrier_event": (
        "Say the carrier's tracking is not current. Give the last observed event, "
        "its time and how many hours old the observation is. Do not predict an "
        "arrival date. Offer open_delivery_help."
    ),
    "label_as_delivery": (
        "The latest record has no milestone type, so it cannot tell whether the "
        "carrier has the parcel or delivered it. Do not say it shipped, is on its "
        "way or was delivered. Offer open_delivery_help."
    ),
}


def _blocked(reason: str, detail: Optional[str] = None, **extra: Any) -> dict:
    return {
        "status": "blocked",
        "reason": reason,
        **({"detail": detail} if detail else {}),
        **extra,
        "next_step": NEXT_STEP[detail or reason],
    }


def _event_view(data: dict, event: dict) -> dict:
    source = event["source"]
    return {
        "milestone": event["milestone"],
        "milestone_spoken": SPOKEN_MILESTONE[event["milestone"]],
        "milestone_source": f"{ORGANISATION} warehouse" if source == "warehouse" else f"{CARRIER} carrier scan",
        "event_at": event["at"],
        "event_at_spoken": spoken_time(event["at"]),
        **({"event_location": event["location"]} if event.get("location") else {}),
    }


def track_order(customer_id: str, order_number: Any, parcel_number: Any = None,
                data: Optional[dict] = None) -> dict:
    """Status of one parcel of one order: the guarded read."""
    data = data or load_data()
    number = normalise_order(order_number)
    order = data["orders"].get(number)
    parcel, why_not = resolve_parcel(order, customer_id, parcel_number)
    facts = facts_for(order, parcel, customer_id, data)
    reason = evaluate(facts)
    if reason == "wrong_order":
        extra: dict = {"order_number": number, "facts": facts}
        if why_not in ("parcel_not_selected", "no_such_parcel"):
            extra["parcels"] = [{"parcel_number": p["parcel_number"], "items": p["items"]} for p in order["parcels"]]
        return _blocked(reason, None if why_not == "not_on_account" else why_not, **extra)
    base = {"order_number": number, "parcel_number": parcel["parcel_number"],
            "parcel_count": len(order["parcels"]), "items": parcel["items"], "facts": facts}
    latest = parcel["events"][-1]
    if reason == "stale_carrier_event":
        observed = parcel.get("carrier_observed_at")
        known = [e for e in parcel["events"] if milestone_explicit(e)]
        return _blocked(
            reason,
            **base,
            last_observed=_event_view(data, known[-1]) if known else None,
            carrier_observed_at=observed,
            carrier_observed_at_spoken=spoken_time(observed) if observed else None,
            observation_age_hours=_age_hours(data, observed) if observed else None,
            arrival_prediction=None,
        )
    if reason:
        # The raw record is not passed on: an unlabelled "SHIPPED" is exactly the
        # text the failure turns into a delivery claim.
        return _blocked(reason, **base, record_at=latest.get("at"), milestone=None)
    view = _event_view(data, latest)
    estimate = parcel.get("estimate")
    answer = {
        "status": "answered",
        **base,
        **view,
        "carrier_observed_at": parcel["carrier_observed_at"],
        "carrier_observed_at_spoken": spoken_time(parcel["carrier_observed_at"]),
        "carrier_has_parcel": any(e.get("milestone") in CARRIER_MILESTONES for e in parcel["events"]),
        "delivered": latest["milestone"] == "delivered",
        "estimate": (
            {"date": estimate["date"], "date_spoken": spoken_date(estimate["date"]),
             "kind": estimate["kind"], "meaning": ESTIMATE_KIND[estimate["kind"]]}
            if estimate and latest["milestone"] != "delivered" else None
        ),
        "status_reference": status_reference(data, customer_id, number, parcel["parcel_number"],
                                             parcel["carrier_observed_at"]),
        "next_step": (
            "Say the milestone, who observed it (the milestone_source) and when, "
            "and the status reference. Call an estimate an estimate. If the "
            "customer wants help with a delay, call open_delivery_help."
        ),
    }
    if latest["milestone"] == "label_created":
        answer["not_collected"] = (
            "Only a shipping label exists. The carrier has not scanned this parcel, "
            "so it is not in transit and has not been delivered."
        )
    if len(order["parcels"]) > 1:
        answer["scope"] = (
            f"This status is for parcel {parcel['parcel_number']} of {len(order['parcels'])} "
            "only. Each other parcel needs its own track_order call."
        )
    return answer


def delivery_help(customer_id: str, order_number: Any, parcel_number: Any = None,
                  data: Optional[dict] = None) -> dict:
    """Recovery route: hand a parcel to delivery support, never predict arrival.

    Only the subject rule applies: the parcel must be the customer's, and
    unambiguous. Freshness and milestone type govern status answers, and this
    gives none; it passes on the last explicit event with its age.
    """
    data = data or load_data()
    number = normalise_order(order_number)
    order = data["orders"].get(number)
    parcel, why_not = resolve_parcel(order, customer_id, parcel_number)
    facts = facts_for(order, parcel, customer_id, data)
    if facts.get("order_subject_resolved") is not True:
        extra: dict = {"order_number": number, "facts": {"order_subject_resolved": False}}
        if why_not in ("parcel_not_selected", "no_such_parcel"):
            extra["parcels"] = [{"parcel_number": p["parcel_number"], "items": p["items"]} for p in order["parcels"]]
        return _blocked("wrong_order", None if why_not == "not_on_account" else why_not, **extra)
    known = [e for e in parcel["events"] if milestone_explicit(e)]
    last = known[-1] if known else None
    return {
        "status": "routed",
        "reference": f"WS-DH-{_digest(customer_id, number, str(parcel['parcel_number']), 'delivery-help')}",
        "order_number": number,
        "parcel_number": parcel["parcel_number"],
        "route": f"{ORGANISATION} delivery support",
        "last_observed": ({**_event_view(data, last), "age_hours": _age_hours(data, last["at"])} if last else None),
        "arrival_prediction": None,
        "next_review_step": f"{ORGANISATION} delivery support emails the customer within one business day.",
    }


def list_orders(customer_id: str, data: Optional[dict] = None) -> dict:
    """The session customer's orders: numbers, items and parcel counts, no status."""
    data = data or load_data()
    orders = [
        {"order_number": number, "items": o["summary"], "parcel_count": len(o["parcels"]),
         "placed_on": spoken_date(o["placed_at"][:10])}
        for number, o in sorted(data["orders"].items()) if o["customer_id"] == customer_id
    ]
    return {"status": "listed", "orders": orders,
            "note": "No tracking status here. Call track_order for the order the customer means."}


def session_profile(customer_id: str = SESSION_CUSTOMER_ID, data: Optional[dict] = None) -> dict:
    data = data or load_data()
    person = data["customers"][customer_id]
    numbers = sorted(n for n, o in data["orders"].items() if o["customer_id"] == customer_id)
    return {"customer_id": customer_id, "first_name": person["first_name"], "order_numbers": numbers}
