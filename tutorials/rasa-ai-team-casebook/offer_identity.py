"""Alternative invented offers are not cumulative updates to the selected offer."""
import json

from renewal_terms import BASE, resolve


OFFERS = {
    "low-deductible": {"mode": "patch", "base_revision": "r1",
                       "terms": {"deductible": {"value": 100}}},
    "higher-limit": {"mode": "patch", "base_revision": "r1",
                     "terms": {"limit": {"value": 20000}}},
}


def field_cache(events):
    """Plausible patch cache: preserves valid base/fields but drops offer identity."""
    terms = dict(BASE["terms"])
    for offer_id, patch in events:
        resolved = resolve(BASE, patch)
        for field in patch["terms"]:
            terms[field] = resolved[field]
    return terms


def selected_offer(events, selected):
    """Resolve complete candidates separately; never fill from another alternative."""
    candidates = {}
    for offer_id, patch in events:
        if not isinstance(offer_id, str) or not offer_id:
            raise ValueError("Offer identity required")
        terms = resolve(BASE, patch)
        if offer_id in candidates and candidates[offer_id] != terms:
            raise ValueError("Same offer identity has conflicting terms")
        candidates[offer_id] = terms
    if selected not in candidates:
        return {"status": "unresolved", "offer_id": selected}
    return {"status": "resolved", "offer_id": selected,
            "base_revision": BASE["revision"], "terms": candidates[selected]}


def demo():
    events = list(OFFERS.items())
    issued = {offer_id: resolve(BASE, patch) for offer_id, patch in events}
    hybrid = field_cache(events)
    return {"base": BASE, "issued_alternatives": issued,
            "field_cache": hybrid, "equals_an_issued_offer": hybrid in issued.values(),
            "selected_low_deductible": selected_offer(events, "low-deductible"),
            "missing_selection": selected_offer(events, "not-received")}


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2, sort_keys=True))
