"""Willow Shop catalogue and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three request-phase rules of the casebook contract for
``retail-guided-selling`` (vendored as ``lib/fixtures/case-contract.json``):

- ``requirements_confirmed``: the device the recommendation is for is one
  catalogue device, named by the shopper in their own words, and it is still
  the device they named last. A model's guess ("the big Lumen 7 is the Pro")
  is not a declared requirement, and a device the shopper has since corrected
  is not a current one.
- ``compatibility_source_present``: every attribute the product category
  requires has a catalogue value with a named source (a spec sheet or a fit
  test). A product name or description is prose, never a source.
- ``availability_current``: the stock count was observed within the freshness
  window, measured on the fixture clock.

Facts are computed here from the catalogue and the conversation's own shopper
messages. The model supplies only a device model name, a product id and, for
docks, whether the shopper uses a case. It never supplies a fact. A fact that
is not exactly ``True`` fails its rule, as in the lab's ``evaluate``.

A known mismatch is not the same outcome as an unknown fit: when a sourced
attribute contradicts the device, the result is ``not_compatible`` with the
attribute and its source; when a required attribute has no source, the result
is ``blocked`` as ``compatibility_unverified`` and the route is a specialist.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "willowshop.json"

# Read once, at import. Mantle imports tool modules from a temporary snapshot
# of lib/ and removes it after loading, so a file read at dispatch time fails.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))

NAME_IS_NOT_EVIDENCE = (
    "A product's name and description are not compatibility evidence. Only a "
    "catalogue attribute with a named source establishes fit."
)

# Wording that asserts an accessory fits or works with a device. The harness
# counts it in bot text as the case metric (reported, never pass or fail);
# tests/test_guard.py keeps this copy and the spec's identical.
FIT_CLAIM_PATTERN = (
    r"\b(?:(?:it|this|that|the (?:dock|case|cable|charger|pad|mount|cradle|holder|folio))"
    r"(?:'s| is| will| would| should)? (?:definitely |fully |also )?"
    r"(?:fit|fits|work|works|be compatible|compatible)"
    r"(?: fine| perfectly)? (?:with|on|for) (?:your|the|a) )"
    r"|\bis compatible with your\b|\bfits your\b|\bworks with your\b"
)
FIT_HEDGE_PATTERN = (
    r"\b(?:not|no|cannot|unable|whether|if|until|unknown|unverified|confirm|check|"
    r"doesn't|does not|won't|can't|isn't)\b|n't\b"
)

_ID_RE = re.compile(r"[^A-Z0-9-]")


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


def normalise_id(value: Any) -> str:
    """' ws dk l7 ' -> WS-DK-L7."""
    return _ID_RE.sub("", re.sub(r"[\s_]+", "-", str(value or "").strip().upper()))


def _words(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).split()


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8].upper()


def _device_phrases(data: dict) -> list[tuple[list[str], str]]:
    phrases = []
    for device_id, device in data["devices"].items():
        for phrase in [device["name"], *device.get("aliases", [])]:
            phrases.append((_words(phrase), device_id))
    # Longest first, so "lumen 7 pro" claims its words before "lumen 7" can.
    return sorted(phrases, key=lambda p: -len(p[0]))


def device_mentions(text: str, data: Optional[dict] = None) -> list[str]:
    """Device ids a shopper message names, in order of appearance.

    A catalogue product's full name is masked first, so "the Lumen 7 Charging
    Dock" names a product, not a Lumen 7. A shorter phrase ("my Lumen 7 case")
    still counts as the shopper naming their device.
    """
    data = data or _DATA
    words = _words(text)
    taken = [False] * len(words)
    product_names = sorted((_words(p["name"]) for p in data["products"].values()), key=len, reverse=True)
    for phrase in product_names:
        _claim(words, taken, phrase)
    found: list[tuple[int, str]] = []
    for phrase, device_id in _device_phrases(data):
        found.extend((i, device_id) for i in _claim(words, taken, phrase))
    return [device_id for _, device_id in sorted(found)]


def _claim(words: list[str], taken: list[bool], phrase: list[str]) -> list[int]:
    """Mark each free occurrence of *phrase* in *words* as taken; return starts."""
    starts = []
    n = len(phrase)
    for i in range(len(words) - n + 1):
        if words[i : i + n] == phrase and not any(taken[i : i + n]):
            for j in range(i, i + n):
                taken[j] = True
            starts.append(i)
    return starts


def latest_declared_devices(user_texts: Iterable[str], data: Optional[dict] = None) -> list[str]:
    """Devices named in the most recent shopper message that names any device."""
    latest: list[str] = []
    for text in user_texts:
        mentioned = device_mentions(text, data)
        if mentioned:
            latest = mentioned
    return latest


def resolve_device(device_model: Any, data: Optional[dict] = None) -> tuple[Optional[str], list[str]]:
    """Exact catalogue device for a model name, or None with candidate names."""
    data = data or _DATA
    wanted = _words(device_model)
    if not wanted:
        return None, []
    for device_id, device in data["devices"].items():
        if any(_words(p) == wanted for p in [device["name"], *device.get("aliases", [])]):
            return device_id, [device["name"]]
    candidates = [
        device["name"]
        for device in data["devices"].values()
        if all(w in _words(device["name"]) for w in wanted)
    ]
    return None, sorted(candidates)


def _blocked(reason: str, **extra: Any) -> dict:
    next_step = {
        "requirements_ambiguous": (
            "Ask the shopper which device model they have, naming the candidates "
            "if any. Do not pick one for them. Call record_requirements again "
            "with the model exactly as they say it."
        ),
        "compatibility_unverified": (
            "Tell the shopper which recorded requirements match and that the "
            "listed attribute is unknown. Do not say it fits, and do not reason "
            "from the product name or description. Offer request_specialist."
        ),
        "availability_stale": (
            "Say current stock cannot be confirmed right now. Do not say it is in "
            "stock. Offer another option or request_specialist."
        ),
    }[reason]
    return {"status": "blocked", "reason": reason, **extra, "next_step": next_step}


def record_requirements(
    device_model: Any,
    user_texts: list[str],
    uses_case: Optional[bool] = None,
    data: Optional[dict] = None,
) -> dict:
    """Record the shopper's declared device, if they declared exactly one."""
    data = data or load_data()
    device_id, candidates = resolve_device(device_model, data)
    declared = latest_declared_devices(user_texts, data)
    confirmed = device_id is not None and device_id in declared
    facts = {"requirements_confirmed": confirmed}
    if not confirmed:
        detail: dict[str, Any] = {"device_model": str(device_model or "")[:80], "facts": facts}
        if device_id is None:
            detail["candidates"] = candidates or sorted(d["name"] for d in data["devices"].values())
        else:
            detail["declared_by_shopper"] = [data["devices"][d]["name"] for d in declared]
            detail["note"] = (
                "The shopper has not named this device in their latest message "
                "that names a device."
            )
        return _blocked("requirements_ambiguous", **detail)
    device = data["devices"][device_id]
    return {
        "status": "recorded",
        "device_id": device_id,
        "device_name": device["name"],
        "uses_case": uses_case is True,
        "attributes": device["attributes"],
        "facts": facts,
        "next_step": (
            "Use search_catalogue to list products, then recommend_product for "
            "the one you would suggest. Any earlier compatibility result for a "
            "different device no longer applies."
        ),
    }


def search_catalogue(category: Any, data: Optional[dict] = None) -> dict:
    """Products in one category: ids, names and prices only, no fit verdict."""
    data = data or load_data()
    key = re.sub(r"[\s-]+", "_", str(category or "").strip().lower())
    if key not in data["categories"]:
        return {"status": "unknown_category", "categories": sorted(data["categories"])}
    items = [
        {"product_id": pid, "name": p["name"], "price_usd": p["price_usd"]}
        for pid, p in sorted(data["products"].items())
        if p["category"] == key
    ]
    return {
        "status": "listed",
        "category": key,
        "products": items,
        "note": NAME_IS_NOT_EVIDENCE + " Call recommend_product to check one against the shopper's device.",
    }


def _matches(required: Any, catalogue_value: Any) -> bool:
    if isinstance(catalogue_value, dict) and {"min", "max"} <= set(catalogue_value):
        return isinstance(required, (int, float)) and catalogue_value["min"] <= required <= catalogue_value["max"]
    return catalogue_value == required


def compare(device_id: str, uses_case: bool, product: dict, data: dict) -> dict:
    """Required attribute ids against catalogue values, keeping each source."""
    category = data["categories"][product["category"]]
    device_attrs = data["devices"][device_id]["attributes"]
    required = {a: device_attrs[a] for a in category["required_attributes"]}
    unresolved_questions = []
    for attr, spec in category["optional_attributes"].items():
        if spec.get("required_when") == "uses_case" and uses_case:
            required[attr] = spec["required_value"]
    matched, mismatched, unknown = [], [], []
    for attr, want in required.items():
        entry = product["attributes"].get(attr) or {}
        source = entry.get("source")
        row = {"attribute": attr, "required": want, "catalogue_value": entry.get("value"), "source": source}
        if not source or entry.get("value") is None:
            unknown.append(row)
        elif _matches(want, entry["value"]):
            matched.append(row)
        else:
            mismatched.append(row)
    for attr, spec in category["optional_attributes"].items():
        entry = product["attributes"].get(attr) or {}
        if attr not in required and (not entry.get("source") or entry.get("value") is None):
            unresolved_questions.append({"attribute": attr, "question": spec["question"], "status": "unknown"})
    return {
        "matched": matched,
        "mismatched": mismatched,
        "unknown": unknown,
        "unresolved_fit_questions": unresolved_questions,
    }


def current_requirements(tool_results: list[tuple[str, Any]]) -> Optional[dict]:
    """The last successful record_requirements result in this conversation."""
    latest = None
    for name, result in tool_results:
        if name != "record_requirements":
            continue
        value = parse_result(result)
        if value.get("status") == "recorded":
            latest = value
    return latest


def parse_result(value: Any) -> dict:
    """The engine stores a tool result as its serialized JSON text."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def recommend_product(
    product_id: Any,
    requirements: Optional[dict],
    user_texts: list[str],
    data: Optional[dict] = None,
) -> dict:
    """The guarded action: recommend one available product for the declared device."""
    data = data or load_data()
    number = normalise_id(product_id)
    product = data["products"].get(number)
    if product is None:
        return {"status": "unknown_product", "product_id": number, "next_step": "Use search_catalogue for valid ids."}
    declared = latest_declared_devices(user_texts, data)
    device_id = (requirements or {}).get("device_id")
    requirements_ok = device_id in data["devices"] and device_id in declared
    facts: dict[str, Any] = {"requirements_confirmed": requirements_ok}
    base = {"product_id": number, "product_name": product["name"]}
    if not requirements_ok:
        detail = dict(base, facts=facts)
        if device_id and declared and device_id not in declared:
            detail["note"] = (
                "The shopper has named a different device since requirements were "
                "recorded. The earlier result is discarded; record the new device."
            )
        return _blocked("requirements_ambiguous", **detail)

    uses_case = bool(requirements.get("uses_case"))
    result = compare(device_id, uses_case, product, data)
    device_name = data["devices"][device_id]["name"]
    base.update(device_id=device_id, device_name=device_name)
    if result["mismatched"]:
        # A sourced attribute contradicts the device: a known mismatch.
        return dict(
            base,
            status="not_compatible",
            recommended=False,
            mismatched_attributes=result["mismatched"],
            note=NAME_IS_NOT_EVIDENCE,
            next_step=(
                "Tell the shopper it does not fit, naming the attribute and its "
                "source. Offer to look for a product that matches."
            ),
        )
    facts["compatibility_source_present"] = not result["unknown"]
    as_of = datetime.fromisoformat(data["as_of"])
    observed = product["stock"].get("observed_at")
    window = timedelta(hours=data["stock_freshness_hours"])
    facts["availability_current"] = bool(observed) and as_of - datetime.fromisoformat(observed) <= window
    reason = evaluate(facts)
    if reason == "compatibility_unverified":
        return _blocked(
            reason,
            **base,
            facts=facts,
            matched_attributes=result["matched"],
            unknown_attributes=[
                {"attribute": r["attribute"], "required": r["required"], "status": "unknown"}
                for r in result["unknown"]
            ],
            note=NAME_IS_NOT_EVIDENCE,
        )
    if reason == "availability_stale":
        return _blocked(
            reason,
            **base,
            facts=facts,
            last_known_stock={"quantity": product["stock"]["quantity"], "observed_at": observed},
        )
    if reason:
        return _blocked(reason, **base, facts=facts)
    if product["stock"]["quantity"] <= 0:
        return dict(base, status="out_of_stock", recommended=False, facts=facts,
                    stock={"quantity": 0, "observed_at": observed})
    day = as_of.strftime("%Y%m%d")
    return dict(
        base,
        status="recommended",
        recommended=True,
        recommendation_reference=f"WS-REC-{day}-{_digest(device_id, number, str(uses_case), observed)}",
        price_usd=product["price_usd"],
        supporting_attributes=result["matched"],
        unresolved_fit_questions=result["unresolved_fit_questions"],
        stock={"quantity": product["stock"]["quantity"], "observed_at": observed},
        facts=facts,
        next_step=(
            "Recommend it, naming the supporting attributes and their sources. "
            "Say any unresolved fit question is unknown and offer request_specialist for it."
        ),
    )


def request_specialist(
    product_id: Any,
    question: Any,
    requirements: Optional[dict],
    data: Optional[dict] = None,
) -> dict:
    """Route an unknown fit to the product catalogue owner. Never answers it."""
    data = data or load_data()
    number = normalise_id(product_id)
    product = data["products"].get(number)
    if product is None:
        return {"status": "unknown_product", "product_id": number}
    device_id = (requirements or {}).get("device_id")
    text = " ".join(str(question or "").split())[:300]
    return {
        "status": "routed",
        "compatible": None,
        "reference": f"WS-SP-{_digest(number, str(device_id), text.lower())}",
        "product_id": number,
        "product_name": product["name"],
        "device_name": data["devices"][device_id]["name"] if device_id in data["devices"] else None,
        "question": text,
        "owner": "Willow Shop product catalogue owner",
        "next_review_step": "A product specialist replies within one business day. Fit is unknown until then.",
    }
