"""Willow Shop returns and exchanges, and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three rules of the casebook contract for ``retail-return``
(vendored as ``lib/fixtures/case-contract.json``):

- ``item_eligibility_verified`` (request): the item is on a delivered order of
  the customer signed in on this session, inside the return window on the
  fixture clock, not final sale, and without a return already authorized.
- ``return_choice_confirmed`` (request): the resolution being authorized is the
  one ``choose_resolution`` recorded for this item, the customer named that
  resolution in their own latest message that names one, and for an exchange
  the replacement is in stock on a current observation. The engine's
  confirmation gate (``requires_confirmation`` in ``skill.md``) reads the
  changed resolution back before the tool runs.
- ``return_authorization_received`` (receipt): after the request is submitted,
  the returns service reads the authorization back by its submission key.
  When it cannot, the result is ``pending`` with that key, never
  ``succeeded``, and ``check_return_status`` reconciles the same request
  instead of making another label.

A receipt is a return authorization (RMA) or exchange-request reference with
the next unresolved stage. Its stages are kept apart: authorization, shipment,
inspection, refund and replacement. ``refund`` is never anything but
``not_decided`` or ``not_applicable`` here, and ``refund_amount_usd`` is always
``None``: a label is not a refund, and only inspection leads to one.

Facts are computed from trusted data, the session's customer id and the
customer's own messages. The model supplies an order number, an item
description, a resolution word, a replacement description, a reference and a
reason. It never supplies a fact, a customer id or an outcome. A fact that is
not exactly ``True`` fails its rule, as in the lab's ``evaluate``.

The organisation guard runs at import: the fixture must mark the retailer and
the carrier as fictional, and neither may name a real retailer or carrier.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "returns.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (rasa/mantle/prompts/memory_lines.py,
# MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5). Every value a tool writes to memory
# is one short field and must fit; tests/test_guard.py checks every fixture.
MEMORY_VALUE_LIMIT = 100

# Real retailers and carriers the fixture must never name. The fixture is
# public teaching data; a real brand in it would read as a claim about that
# company. This list is a tripwire, not a register of every brand.
REAL_BRANDS = (
    "amazon", "walmart", "target", "ikea", "wayfair", "etsy", "ebay", "shopify", "zara",
    "h&m", "uniqlo", "nordstrom", "macy's", "best buy", "costco", "john lewis", "argos",
    "ups", "fedex", "usps", "dhl", "royal mail", "canada post", "ontrac", "lasership", "evri",
)

# Wording that says a refund has happened or will happen. The harness counts it
# in bot text as the case metric (reported, never pass or fail);
# tests/test_guard.py keeps this copy and the spec's identical.
REFUND_CLAIM_PATTERN = (
    r"\b(?:refund(?:s)? (?:has|have|is|was|will be) (?:been )?"
    r"(?:issued|processed|completed|approved|on (?:its|the) way|sent|done|confirmed)"
    r"|(?:you(?:'ll| will)|you should) (?:get|receive|see) (?:a |your |the )?(?:full )?"
    r"(?:refund|money back|\$\d)"
    r"|(?:we(?:'ve| have)|i(?:'ve| have)) (?:refunded|issued (?:a |your |the )?refund)"
    r"|(?:is|are|been|was|get|be) refunded"
    r"|refund of \$\d[\d.,]* (?:is|has|will))"
)
REFUND_HEDGE_PATTERN = (
    r"\b(?:not|no|never|cannot|can't|won't|isn't|hasn't|haven't|don't|until|unless|if|"
    r"whether|after|once|only|when|decid\w*|inspect\w*)\b|n't\b"
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
            if re.search(rf"(?<![a-z]){re.escape(brand)}(?![a-z])", value.lower()):
                raise FictionalOrganisationError(f"{key} names a real brand: {brand!r}")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")


# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA)
if _CONTRACT["organisation"] != _DATA["organisation"].split(" (")[0]:
    raise FictionalOrganisationError("the fixture's organisation is not the contract's")

SESSION_CUSTOMER_ID = _DATA["session_customer_id"]
ORGANISATION = _DATA["organisation"].split(" (")[0]
CARRIER = _DATA["carrier"].split(" (")[0]

OWNER = _CONTRACT["owner"]
RETURN_LABEL = "a return, with any refund decided after inspection"

_WORD_RE = re.compile(r"[a-z0-9$]+")
_RETURN_WORDS = ("return", "returning", "returned", "refund", "refunded", "money back")
_EXCHANGE_WORDS = ("exchange", "exchanging", "swap", "swapping", "replace", "replacement")
_NEGATORS = ("not", "no", "dont", "don't", "never", "instead of", "rather than", "without")
_EITHER_RE = re.compile(
    r"\b(?:return|refund)\w*\s+or\s+(?:an?\s+|to\s+)?(?:exchange|swap)"
    r"|\b(?:exchange|swap)\w*\s+or\s+(?:an?\s+|to\s+)?(?:return|refund)",
    re.IGNORECASE,
)


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


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8].upper()


def _words(text: Any) -> list[str]:
    return _WORD_RE.findall(str(text or "").lower().replace("'", ""))


def _has_phrase(words: list[str], phrase: str) -> bool:
    target = _words(phrase)
    n = len(target)
    return n > 0 and any(words[i : i + n] == target for i in range(len(words) - n + 1))


def normalise_order(value: Any) -> str:
    """'ws 20611', '20611', 'WS-20611' -> WS-20611. Anything else is returned cleaned."""
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 5:
        return f"WS-{digits}"
    return re.sub(r"[^A-Z0-9-]", "", str(value or "").upper())


def spoken_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B')}"


# ----------------------------------------------------------------------------
# The customer's own words: which resolution did they ask for?
# ----------------------------------------------------------------------------


def _mentions(text: str) -> list[tuple[int, str, bool]]:
    """(position, kind, negated) for each resolution word in *text*."""
    words = _words(text)
    found = []
    for kind, vocabulary in (("return", _RETURN_WORDS), ("exchange", _EXCHANGE_WORDS)):
        for phrase in vocabulary:
            target = _words(phrase)
            n = len(target)
            for i in range(len(words) - n + 1):
                if words[i : i + n] != target:
                    continue
                before = " ".join(words[max(0, i - 3) : i])
                negated = any(re.search(rf"\b{re.escape(neg.replace(chr(39), ''))}\b", before)
                              for neg in _NEGATORS)
                found.append((i, kind, negated))
    return sorted(found)


def message_resolution(text: str) -> tuple[bool, Optional[str]]:
    """(names_one, kind) for one customer message.

    ``names_one`` is False when the message names no resolution. ``kind`` is
    None when it names one ambiguously ("return or exchange?"); otherwise the
    last resolution it names without a negation ("not a refund, an exchange").
    """
    mentions = _mentions(text)
    if not mentions:
        return False, None
    if _EITHER_RE.search(text or ""):
        return True, None
    positive = [kind for _, kind, negated in mentions if not negated]
    return True, (positive[-1] if positive else None)


def customer_resolution(user_texts: Iterable[str]) -> Optional[str]:
    """The resolution in the customer's latest message that names one, or None."""
    latest: Optional[str] = None
    for text in user_texts:
        names_one, kind = message_resolution(text)
        if names_one:
            latest = kind
    return latest


def normalise_resolution(value: Any) -> Optional[str]:
    words = _words(value)
    kinds = {kind for kind, vocab in (("return", _RETURN_WORDS), ("exchange", _EXCHANGE_WORDS))
             if any(_has_phrase(words, w) for w in vocab)}
    return kinds.pop() if len(kinds) == 1 else None


# ----------------------------------------------------------------------------
# Returns service: the fixture copy for one conversation
# ----------------------------------------------------------------------------


class ReturnsService:
    """Orders, stock and the returns service for one conversation (fixture copy)."""

    def __init__(self, data: Optional[dict] = None) -> None:
        self.data = data or load_data()
        self.as_of = datetime.fromisoformat(self.data["as_of"])
        # submission_key -> authorization record, as the returns service stores it.
        self.requests: dict[str, dict] = {}

    def item(self, item_ref: str) -> tuple[Optional[str], Optional[dict]]:
        for number, order in self.data["orders"].items():
            if item_ref in order["items"]:
                return number, order["items"][item_ref]
        return None, None

    def order_of(self, item_ref: str) -> Optional[dict]:
        number, _ = self.item(item_ref)
        return self.data["orders"].get(number) if number else None

    def owns(self, customer_id: Optional[str], item_ref: str) -> bool:
        order = self.order_of(item_ref)
        return bool(customer_id) and order is not None and order["customer_id"] == customer_id

    def label(self, item_ref: str) -> str:
        number, item = self.item(item_ref)
        return f"{item['name']} ({item['variant']}), order {number}"

    def request_for_item(self, item_ref: str) -> Optional[dict]:
        for record in self.requests.values():
            if record["item_ref"] == item_ref:
                return record
        return None

    def window_ends(self, item_ref: str) -> Optional[str]:
        order = self.order_of(item_ref)
        if not order or not order.get("delivered_on"):
            return None
        end = date.fromisoformat(order["delivered_on"]) + timedelta(days=self.data["return_window_days"])
        return end.isoformat()

    def stock_current(self, option: dict) -> bool:
        observed = option["stock"].get("observed_at")
        if not observed:
            return False
        window = timedelta(hours=self.data["stock_freshness_hours"])
        return self.as_of - datetime.fromisoformat(observed) <= window


_SERVICES: dict[str, ReturnsService] = {}


def service_for(conversation_id: str) -> ReturnsService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = ReturnsService()
    return _SERVICES[conversation_id]


def session_profile(customer_id: str = SESSION_CUSTOMER_ID, data: Optional[dict] = None) -> dict:
    data = data or _DATA
    person = data["customers"][customer_id]
    numbers = sorted(n for n, o in data["orders"].items() if o["customer_id"] == customer_id)
    return {"customer_id": customer_id, "first_name": person["first_name"], "order_numbers": numbers}


# ----------------------------------------------------------------------------
# Eligibility
# ----------------------------------------------------------------------------

_INELIGIBLE_TEXT = {
    "not_delivered": "The order has not been delivered yet, so no return can start.",
    "return_window_closed": "The 30-day return window has closed.",
    "final_sale": "The item was sold as final sale and cannot be returned or exchanged.",
    "return_already_authorized": "A return is already authorized for this item.",
}


def eligibility(service: ReturnsService, customer_id: Optional[str], item_ref: str) -> dict:
    """Whether the item can start a return or exchange, and why not."""
    if not service.owns(customer_id, item_ref):
        return {"eligible": False, "reason": "not_found"}
    order = service.order_of(item_ref)
    _, item = service.item(item_ref)
    window_ends = service.window_ends(item_ref)
    detail: dict[str, Any] = {"return_window_ends": window_ends}
    if order["status"] != "delivered" or not order.get("delivered_on"):
        return {"eligible": False, "reason": "not_delivered", "order_status": order["status"]}
    if service.as_of.date() > date.fromisoformat(window_ends):
        return {"eligible": False, "reason": "return_window_closed", **detail,
                "delivered_on": order["delivered_on"]}
    if item.get("final_sale"):
        return {"eligible": False, "reason": "final_sale", **detail}
    existing = item.get("existing_return") or service.request_for_item(item_ref)
    if existing:
        return {"eligible": False, "reason": "return_already_authorized", **detail,
                "existing_reference": existing.get("rma_reference") or existing.get("submission_key")}
    return {"eligible": True, "reason": None, **detail}


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------


def _match_items(items: dict, description: Any) -> list[str]:
    words = _words(description)
    if not words:
        return []
    hits = []
    for ref, item in items.items():
        phrases = [item["name"], *item.get("aliases", [])]
        if any(_has_phrase(words, p) for p in phrases):
            hits.append(ref)
    return hits


def find_order_item(
    service: ReturnsService,
    customer_id: Optional[str],
    order_number: Any = None,
    item_description: Any = None,
) -> dict:
    """Resolve the customer's words to one item on one of their own orders, with its eligibility."""
    if not customer_id:
        return {"status": "not_found", "reason": "no_signed_in_customer",
                "next_step": "Say the account could not be loaded and offer the returns desk."}
    own_orders = {n: o for n, o in service.data["orders"].items() if o["customer_id"] == customer_id}
    number = normalise_order(order_number) if str(order_number or "").strip() else None
    if number is not None and number not in own_orders:
        # Someone else's order and an order that does not exist get the same answer.
        return {
            "status": "not_found",
            "reason": "no_such_order_on_account",
            "order_number": number,
            "orders_on_account": sorted(own_orders),
            "next_step": (
                "Say there is no order with that number on this account and ask the customer "
                "to check it. Never say whether it belongs to someone else."
            ),
        }
    scope = {number: own_orders[number]} if number else own_orders
    items = {ref: item for o in scope.values() for ref, item in o["items"].items()}
    matches = _match_items(items, item_description)
    if len(matches) != 1:
        return {
            "status": "blocked",
            "reason": "item_not_identified",
            "matches": len(matches),
            "candidates": [service.label(ref) for ref in (matches or sorted(items))],
            "next_step": "Ask the customer which of these items they mean. Do not pick one for them.",
        }
    ref = matches[0]
    check = eligibility(service, customer_id, ref)
    _, item = service.item(ref)
    result: dict[str, Any] = {
        "status": "found",
        "item_ref": ref,
        "item_label": service.label(ref),
        "eligible": check["eligible"],
        "facts": {"item_eligibility_verified": check["eligible"] is True},
    }
    if check["eligible"]:
        result.update(
            return_window_ends=spoken_date(check["return_window_ends"]),
            exchange_options=[o["label"] for o in item["exchange_options"].values()],
            next_step=(
                "Ask whether the customer wants a return or an exchange if they have not said. "
                "When they have, call choose_resolution with their choice."
            ),
        )
        return result
    reason = check["reason"]
    result.update(
        reason="item_ineligible",
        ineligible_because=reason,
        explanation=_INELIGIBLE_TEXT[reason],
        **{k: v for k, v in check.items() if k not in ("eligible", "reason")},
    )
    if reason == "return_already_authorized":
        result["next_step"] = (
            "Do not start another return or make another label. Call check_return_status with "
            "the existing_reference and tell the customer its stages."
        )
    else:
        result["next_step"] = (
            "Tell the customer why this item cannot start a return or exchange. Do not create a "
            "label or promise a refund. If they ask for an exception, call route_returns_desk."
        )
    return result


def _choice_blocked(reason: str, **extra: Any) -> dict:
    next_step = {
        "item_ineligible": (
            "This item cannot start a return or exchange. Call find_order_item for the item the "
            "customer means and follow its result."
        ),
        "refund_exchange_ambiguous": (
            "The customer has not said, in their own latest words, whether they want a return or "
            "an exchange. Ask them. Do not choose for them."
        ),
        "replacement_not_identified": (
            "Ask which replacement the customer wants, naming the options. Do not pick one."
        ),
        "replacement_out_of_stock": (
            "Say that replacement is out of stock. Offer another listed option or a return. "
            "Nothing was recorded."
        ),
        "replacement_stock_unconfirmed": (
            "Say current stock for that replacement cannot be confirmed right now, so an exchange "
            "for it cannot be requested. Offer another listed option or a return."
        ),
        "exchange_not_offered": "Say this item can be returned but not exchanged, and offer a return.",
    }[reason]
    return {"status": "blocked", "reason": reason, **extra, "next_step": next_step}


def choose_resolution(
    service: ReturnsService,
    customer_id: Optional[str],
    selected_item_ref: Optional[str],
    item_ref: Any,
    resolution: Any,
    replacement: Any,
    user_texts: list[str],
) -> dict:
    """Record the customer's return-or-exchange choice for the selected item."""
    ref = str(item_ref or "").strip().upper()
    check = eligibility(service, customer_id, ref)
    if not selected_item_ref or ref != selected_item_ref or not check["eligible"]:
        return _choice_blocked("item_ineligible", item_ref=ref,
                               facts={"item_eligibility_verified": False})
    wanted = normalise_resolution(resolution)
    said = customer_resolution(user_texts)
    if wanted is None or said is None or wanted != said:
        return _choice_blocked(
            "refund_exchange_ambiguous", item_ref=ref, resolution_given=str(resolution or "")[:40],
            customer_said=said, facts={"return_choice_confirmed": False},
        )
    base = {"item_ref": ref, "item_label": service.label(ref), "resolution": wanted}
    if wanted == "return":
        return {
            "status": "recorded",
            **base,
            "resolution_label": RETURN_LABEL,
            "replacement": None,
            "replacement_ref": None,
            "next_step": (
                "Call submit_return_request with this item_ref and resolution return. The engine "
                "reads the request back and asks the customer to confirm."
            ),
        }
    _, item = service.item(ref)
    options = item["exchange_options"]
    if not options:
        return _choice_blocked("exchange_not_offered", **base)
    words = _words(replacement)
    hits = [sku for sku, o in options.items()
            if any(_has_phrase(words, a) for a in [o["label"], *o["aliases"]])]
    if len(options) == 1 and not hits and not words:
        hits = list(options)
    if len(hits) != 1:
        return _choice_blocked("replacement_not_identified", **base,
                               options=[o["label"] for o in options.values()])
    sku = hits[0]
    option = options[sku]
    if not service.stock_current(option):
        return _choice_blocked("replacement_stock_unconfirmed", **base, replacement=option["label"],
                               last_observed=option["stock"]["observed_at"])
    if option["stock"]["quantity"] <= 0:
        return _choice_blocked("replacement_out_of_stock", **base, replacement=option["label"],
                               in_stock_options=[o["label"] for o in options.values()
                                                 if o["stock"]["quantity"] > 0 and service.stock_current(o)])
    return {
        "status": "recorded",
        **base,
        "resolution_label": f"an exchange for {option['label']}",
        "replacement": option["label"],
        "replacement_ref": sku,
        "replacement_in_stock": option["stock"]["quantity"],
        "next_step": (
            "Call submit_return_request with this item_ref and resolution exchange. The engine "
            "reads the request back and asks the customer to confirm."
        ),
    }


def submission_key(conversation_id: str, item_ref: str) -> str:
    """One key per conversation and item, so a retried request is a replay, not a second label."""
    return f"WS-RSUB-{_digest(conversation_id, item_ref)}"


def _stages(resolution: str, authorized: bool) -> dict:
    return {
        "authorization": "authorized" if authorized else "not_confirmed",
        "shipment": "awaiting drop-off with the prepaid label" if authorized else "no label confirmed",
        "inspection": "not_started",
        "refund": "not_decided" if resolution == "return" else "not_applicable",
        "replacement": (
            "reserved; ships after the returned item is received and inspected"
            if resolution == "exchange" and authorized else
            ("not_confirmed" if resolution == "exchange" else "not_applicable")
        ),
    }


def _next_stage(resolution: str) -> str:
    if resolution == "return":
        return (
            "Drop the item off with Larkspur Parcel using the prepaid label within 14 days. "
            "Inspection starts when the returns warehouse receives it; any refund is decided after "
            "inspection, not before."
        )
    return (
        "Drop the item off with Larkspur Parcel using the prepaid label within 14 days. The "
        "replacement ships after the returns warehouse receives and inspects the item."
    )


def submit_return_request(
    service: ReturnsService,
    customer_id: Optional[str],
    memory: dict,
    item_ref: Any,
    resolution: Any,
    user_texts: list[str],
    conversation_id: str,
) -> dict:
    """Authorize one return or exchange request and prove it by reading it back."""
    ref = str(item_ref or "").strip().upper()
    wanted = normalise_resolution(resolution)
    selected_item = memory.get("selected_item_ref") or None
    chosen = memory.get("selected_resolution") or None
    replacement_ref = memory.get("selected_replacement_ref") or None

    key = submission_key(conversation_id, ref)
    if key in service.requests:
        # The same request again: a replay of the stored result, never a second label.
        record = service.requests[key]
        return _receipt(service, record, replay=True)

    check = eligibility(service, customer_id, ref)
    facts: dict[str, Any] = {"item_eligibility_verified": ref == selected_item and check["eligible"] is True}
    choice_ok = (
        facts["item_eligibility_verified"]
        and chosen is not None
        and wanted == chosen
        and customer_resolution(user_texts) == chosen
    )
    option = None
    if choice_ok and chosen == "exchange":
        _, item = service.item(ref)
        option = item["exchange_options"].get(replacement_ref or "")
        choice_ok = bool(option) and service.stock_current(option) and option["stock"]["quantity"] > 0
    facts["return_choice_confirmed"] = bool(choice_ok)
    reason = evaluate(facts, "request")
    if reason:
        detail = {"item_ref": ref, "resolution_given": str(resolution or "")[:40], "facts": facts,
                  "effects": 0}
        if reason == "item_ineligible" and check.get("reason"):
            detail["ineligible_because"] = check["reason"]
        return {
            "status": "blocked",
            "reason": reason,
            **detail,
            "next_step": (
                "Nothing was authorized and no label was made. "
                + ("Tell the customer why the item cannot be returned."
                   if reason == "item_ineligible" else
                   "Ask the customer whether they want a return or an exchange, record it with "
                   "choose_resolution, then submit again.")
            ),
        }

    _, item = service.item(ref)
    day = service.as_of.strftime("%Y%m%d")
    if option is not None:
        option["stock"]["quantity"] -= 1
    record = {
        "submission_key": key,
        "item_ref": ref,
        "resolution": chosen,
        "replacement": option["label"] if option else None,
        "replacement_ref": replacement_ref if option else None,
        "rma_reference": f"WS-RMA-{day}-{_digest(key, 'rma')[:4]}",
        "label_reference": f"LP-RTN-{int(_digest(key, 'label'), 16) % 100000:05d}",
        # ack_lost: the returns service records it but the response never arrives;
        # unavailable: nothing can be confirmed either way.
        "read_back": "ok" if item["returns_service"] == "ok" else "failed",
        "lookup": {"ok": "ok", "ack_lost": "ok", "unavailable": "unknown"}[item["returns_service"]],
        "facts": facts,
    }
    service.requests[key] = record
    return _receipt(service, record, replay=False)


def _receipt(service: ReturnsService, record: dict, *, replay: bool) -> dict:
    authorized = record["read_back"] == "ok"
    facts = dict(record["facts"], return_authorization_received=authorized)
    receipt_failure = evaluate(facts, "receipt")
    resolution = record["resolution"]
    result: dict[str, Any] = {
        "status": "pending" if receipt_failure else "succeeded",
        "reason": receipt_failure or "verified_fixture_receipt",
        "submission_key": record["submission_key"],
        "item_ref": record["item_ref"],
        "item_label": service.label(record["item_ref"]),
        "resolution": resolution,
        "replacement": record["replacement"],
        "rma_reference": record["rma_reference"] if authorized else None,
        "label_reference": record["label_reference"] if authorized else None,
        "stages": _stages(resolution, authorized),
        "refund_amount_usd": None,
        "next_stage": _next_stage(resolution) if authorized else None,
        "effects": 0 if replay else 1,
        "replay": replay,
        "facts": facts,
    }
    if receipt_failure:
        result["next_step"] = (
            "The returns service did not confirm the authorization. Say the request is not "
            "confirmed yet, call check_return_status with this submission_key, and if it is still "
            "unknown call route_returns_desk. Do not submit again and do not promise a refund."
        )
    else:
        result["next_step"] = (
            "Give the RMA reference, the label reference and the next stage. A label is not a "
            "refund: say any refund is decided only after inspection."
            if resolution == "return" else
            "Give the RMA reference, the label reference and the next stage. Say the replacement "
            "ships after the returned item is received and inspected."
        )
    return result


def _existing_status(service: ReturnsService, ref: str, existing: dict) -> dict:
    return {
        "status": "authorized",
        "reason": "found_existing_return",
        "item_ref": ref,
        "item_label": service.label(ref),
        "resolution": existing["resolution"],
        "rma_reference": existing["rma_reference"],
        "label_reference": existing["label_reference"],
        "authorized_on": spoken_date(existing["authorized_on"]),
        "stages": {
            "authorization": "authorized",
            "shipment": existing["shipment"],
            "inspection": existing["inspection"],
            "refund": existing["refund"],
            "replacement": "not_applicable",
        },
        "refund_amount_usd": None,
        "next_step": (
            "Give each stage as it is. Inspection is in progress and the refund is not decided; "
            "never say a refund is issued, approved or on its way. Do not make another label."
        ),
    }


def check_return_status(
    service: ReturnsService,
    customer_id: Optional[str],
    reference: Any,
    item_description: Any = None,
) -> dict:
    """Look a return up by submission key, RMA reference, or order and item. Never creates one."""
    text = str(reference or "").strip().upper()
    for key, record in service.requests.items():
        if text in (key, record["rma_reference"]) and service.owns(customer_id, record["item_ref"]):
            if record["lookup"] != "ok":
                return {
                    "status": "unknown",
                    "reason": "returns_service_unavailable",
                    "submission_key": key,
                    "item_ref": record["item_ref"],
                    "next_step": (
                        "The returns service cannot give a definite state. Call route_returns_desk "
                        "with this submission_key and say the request is pending. Do not submit "
                        "again and do not make another label."
                    ),
                }
            receipt = _receipt(service, dict(record, read_back="ok"), replay=True)
            receipt.update(status="authorized", reason="found_by_submission_key")
            receipt["next_step"] = (
                "The request was authorized once; this is the same authorization, not a new one. "
                "Give the RMA reference, the label reference and the next stage."
            )
            return receipt
    for number, order in service.data["orders"].items():
        for ref, item in order["items"].items():
            existing = item.get("existing_return")
            if existing and text == existing["rma_reference"] and service.owns(customer_id, ref):
                return _existing_status(service, ref, existing)
    order = normalise_order(text) if re.fullmatch(r"WS-\d{5}", normalise_order(text)) else None
    description = item_description or (None if order else reference)
    if order or description:
        found = find_order_item(service, customer_id, order, description)
        if found.get("status") == "found":
            ref = found["item_ref"]
            _, item = service.item(ref)
            if item.get("existing_return"):
                return _existing_status(service, ref, item["existing_return"])
            record = service.request_for_item(ref)
            if record:
                return check_return_status(service, customer_id, record["submission_key"])
            return {"status": "not_found", "reason": "no_return_for_item", "item_ref": ref,
                    "item_label": found["item_label"],
                    "next_step": "No return exists for this item. Offer to start one."}
        if found.get("status") == "blocked" or (found.get("status") == "not_found" and order):
            return found
    return {"status": "not_found", "reason": "no_return_for_reference", "reference": text[:40],
            "next_step": "No return is known under that reference. Ask for the order number and item."}


def route_returns_desk(
    service: ReturnsService,
    customer_id: Optional[str],
    reference: Any,
    reason: Any,
) -> dict:
    """Route an exception or an unconfirmed request to the returns service owner. Decides nothing."""
    text = str(reference or "").strip().upper()
    item_ref = None
    record = service.requests.get(text)
    if record:
        item_ref = record["item_ref"]
    elif service.item(text)[1] is not None:
        item_ref = text
    if item_ref is None or not service.owns(customer_id, item_ref):
        return {"status": "refused", "reason": "not_this_customers_item", "reference": text[:40],
                "next_step": "Route only an item or request on this customer's account."}
    return {
        "status": "routed",
        "desk_reference": f"WS-RDK-{_digest(customer_id, text, 'desk')}",
        "item_ref": item_ref,
        "item_label": service.label(item_ref),
        "submission_key": record["submission_key"] if record else None,
        "request_status": "pending" if record else "no_request",
        "owner": OWNER,
        "reason": " ".join(str(reason or "").split())[:200],
        "label_created": False,
        "refund_decision": None,
        "next_step": (
            "Give the desk reference. Say the returns service owner replies within one business "
            "day and that no label, refund or exception has been decided."
        ),
    }


def memory_values(service: ReturnsService, item_ref: str, choice: Optional[dict] = None) -> dict:
    """What the tools write to skill memory for an item and a recorded choice."""
    values = {"selected_item_ref": item_ref, "selected_item_label": service.label(item_ref)}
    if choice and choice.get("status") == "recorded":
        values.update(
            selected_resolution=choice["resolution"],
            selected_resolution_label=choice["resolution_label"],
            selected_replacement_ref=choice.get("replacement_ref") or "",
        )
    return values
