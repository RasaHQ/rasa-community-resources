"""HarborCover quote-and-bind service and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the three rules of the casebook contract for
``insurance-quote-bind`` (vendored as ``lib/fixtures/case-contract.json``):

- ``underwritten_offer_current`` (request): the thing being bound is an
  underwritten offer, not an indicative estimate; it belongs to this session's
  customer; it is the current, unexpired, unwithdrawn version of its quote; and
  it is the offer the engine read back to the customer.
- ``material_answers_confirmed`` (request): the customer confirmed the material
  answers, and the confirmed answers are exactly the ones this offer was
  underwritten on and the ones on the quote now.
- ``bind_receipt_verified`` (receipt): the binding service returned a receipt
  whose offer id, offer version and answers hash match the bind request. Without
  one the result is ``pending`` and the offer stays explicitly unbound; there is
  no policy reference.

Three states are kept apart in the data: an indicative estimate (a price range
from the quote screen), an underwritten offer (a versioned price for a set of
answers) and a bound policy (a binding-service receipt). Only the last one has
a policy number.

Facts are computed here from trusted data and session state. The model
supplies a quote id, an offer id, a question id and the customer's answer. It
never supplies a fact, a customer id, a price or a policy number. A fact that is
not exactly ``True`` fails its rule, as in the lab's ``evaluate``.

Quote state lives in an in-process service with one copy of the fixture per
conversation, so every scripted conversation starts from the same quotes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "harborcover_quotes.json"

# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))

DEMO_CUSTOMER_ID = "HC-CUST-5120"

NUMERIC_QUESTIONS = ("contents_value_usd", "prior_claims_3y", "annual_miles", "named_drivers")
YES_NO_QUESTIONS = ("dog_on_premises", "smoke_alarms")
DATE_QUESTIONS = ("start_date",)

NOT_COVER = (
    "An estimate or an offer is not active cover. Nothing is bound until the "
    "HarborCover binding service returns a receipt with a policy number."
)

# Wording that presents cover as active or a policy as bound. Used by the
# output guard in hooks.py; the harness counts the same pattern in bot text as
# the case metric. tests/test_guard.py keeps the copies identical.
ACTIVE_COVER_PATTERN = (
    r"\byou(?:'re| are| will be)(?: now| already| fully| officially)? (?:covered|insured)\b"
    r"|\byour (?:new )?(?:renters |auto |car |condo )?(?:policy|cover|coverage|insurance)"
    r" (?:is|has been) (?:now |already |officially )?(?:active|bound|in force|live|in place|issued)\b"
    r"|\b(?:cover|coverage) (?:is|has) (?:now |already )?(?:active|started|begun|in place)\b"
    r"|\byou (?:now )?have (?:active )?(?:cover|coverage)\b"
    r"|\bthe policy is (?:now |already )?(?:active|bound|in force|live|in place)\b"
)
ACTIVE_COVER_RE = re.compile(ACTIVE_COVER_PATTERN, re.IGNORECASE)
# A match is not a claim when the same sentence negates or conditions it
# before the match: "you are not covered until the binding service confirms".
ACTIVE_COVER_HEDGE_PATTERN = (
    r"\b(?:not|no|never|until|once|after|when|if|whether|cannot|unless|only|before)\b|n't\b"
)
ACTIVE_COVER_HEDGE_RE = re.compile(ACTIVE_COVER_HEDGE_PATTERN, re.IGNORECASE)
POLICY_REFERENCE_PATTERN = r"\bHC-POL-[A-Z]{2}-[0-9A-F]{6,}\b"
POLICY_REFERENCE_RE = re.compile(POLICY_REFERENCE_PATTERN, re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def active_cover_claims(text: str) -> list[str]:
    """Phrases in *text* that present cover as active, sentence by sentence."""
    found = []
    for sentence in _SENTENCE_RE.split(text or ""):
        for match in ACTIVE_COVER_RE.finditer(sentence):
            if not ACTIVE_COVER_HEDGE_RE.search(sentence[: match.start()]):
                found.append(match.group(0))
    return found


def policy_references(text: str) -> list[str]:
    return [m.group(0).upper() for m in POLICY_REFERENCE_RE.finditer(text or "")]


# ----------------------------------------------------------------------------
# Contract
# ----------------------------------------------------------------------------


def load_contract() -> dict:
    return copy.deepcopy(_CONTRACT)


def load_data() -> dict:
    return copy.deepcopy(_DATA)


def rules(phase: str, contract: Optional[dict] = None) -> list[dict]:
    contract = contract or _CONTRACT
    return [rule for rule in contract["rules"] if rule["phase"] == phase]


def evaluate(facts: dict, phase: str, contract: Optional[dict] = None) -> Optional[str]:
    """First failing rule's reason for *phase*, or None. Exactly ``True`` passes."""
    for rule in rules(phase, contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8].upper()


def answers_hash(answers: dict) -> str:
    return hashlib.sha256(json.dumps(answers, sort_keys=True).encode()).hexdigest()[:12]


def normalise_id(value: Any) -> str:
    """' hc q rn 6120 ' -> HC-Q-RN-6120."""
    return re.sub(r"[^A-Z0-9-]", "", re.sub(r"\s+", "-", str(value or "").strip().upper()))


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _money(value: float) -> str:
    return f"{value:.2f}"


def normalise_answer(question: str, value: Any) -> Optional[str]:
    """Canonical text for one answer, or None when it cannot be read."""
    text = " ".join(str(value if value is not None else "").split())
    if question in NUMERIC_QUESTIONS:
        lowered = text.lower().replace(",", "")
        match = re.search(r"\d+(?:\.\d+)?", lowered)
        if match is None:
            words = {"none": 0, "zero": 0, "no": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
            for word, number in words.items():
                if re.search(rf"\b{word}\b", lowered):
                    return str(number)
            return None
        number = float(match.group(0))
        if re.search(r"\d\s*k\b", lowered):
            number *= 1000
        return str(int(number)) if number == int(number) else str(number)
    if question in YES_NO_QUESTIONS:
        lowered = text.lower()
        if lowered in ("yes", "y", "true", "1") or lowered.startswith("yes"):
            return "yes"
        if lowered in ("no", "n", "false", "0", "none") or lowered.startswith("no"):
            return "no"
        return None
    if question in DATE_QUESTIONS:
        return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else None
    return text or None


# ----------------------------------------------------------------------------
# The service (one per conversation)
# ----------------------------------------------------------------------------


class QuoteService:
    """HarborCover's quote, underwriting and binding services for one conversation."""

    def __init__(self, data: Optional[dict] = None) -> None:
        self.data = data or load_data()
        self.as_of = _parse(self.data["as_of"])
        self.quotes: dict[str, dict] = self.data["quotes"]
        self.offers: dict[str, dict] = {}
        for quote_id, quote in self.quotes.items():
            quote.setdefault("current_offer_id", None)
            quote.setdefault("confirmed_answers_hash", None)
            quote.setdefault("referral", None)
            quote.setdefault("policy", None)
            quote.setdefault("bind_request", None)
            for prior in quote.get("prior_offers", []):
                offer = {
                    **copy.deepcopy(prior),
                    "quote_id": quote_id,
                    "answers_hash": answers_hash(prior["answers"]),
                    "status": "offered",
                }
                self.offers[offer["offer_id"]] = offer
                quote["current_offer_id"] = offer["offer_id"]
        self.binds: dict[str, dict] = {}
        self.callbacks: list[dict] = []

    # -- reads -----------------------------------------------------------

    def quote_of(self, customer_id: Optional[str], quote_id: Any) -> Optional[dict]:
        quote = self.quotes.get(normalise_id(quote_id))
        if quote is None or not customer_id or quote["customer_id"] != customer_id:
            return None
        return quote

    def expired(self, offer: dict) -> bool:
        return self.as_of >= _parse(offer["expires_at"])

    def offer_state(self, offer: dict) -> str:
        if offer["status"] == "offered" and self.expired(offer):
            return "expired"
        return offer["status"]

    def current_offer(self, quote: dict) -> Optional[dict]:
        offer = self.offers.get(quote.get("current_offer_id") or "")
        if offer is None or self.offer_state(offer) not in ("offered", "bound"):
            return None
        return offer

    def quote_state(self, quote: dict) -> str:
        if quote["policy"]:
            return "bound"
        if quote["bind_request"]:
            return "bind_pending"
        if quote["referral"] and quote["referral"] == answers_hash(quote["answers"]):
            return "referred"
        if self.current_offer(quote):
            return "offer"
        return "estimate"

    def next_version(self, quote_id: str) -> int:
        versions = [o["version"] for o in self.offers.values() if o["quote_id"] == quote_id]
        return max(versions, default=0) + 1

    def price(self, product: str, answers: dict) -> float:
        p = self.data["pricing"][product]
        claims = int(answers.get("prior_claims_3y") or 0)
        if product == "renters":
            value = p["base"] + p["per_10k_contents"] * int(answers["contents_value_usd"]) / 10000
            value += p["dog"] if answers.get("dog_on_premises") == "yes" else 0
            value += p["no_smoke_alarms"] if answers.get("smoke_alarms") == "no" else 0
        elif product == "auto":
            value = p["base"] + p["per_10k_miles"] * int(answers["annual_miles"]) / 10000
            value += p["per_extra_driver"] * max(int(answers.get("named_drivers") or 1) - 1, 0)
        else:
            value = p["base"] + p["per_10k_contents"] * int(answers["contents_value_usd"]) / 10000
        return round(value + p["per_prior_claim"] * claims, 2)

    # -- binding service (fixture) -----------------------------------------

    def binding_service(self, quote: dict, offer: dict, request_id: str) -> Optional[dict]:
        """What the binding service returns. None: request accepted, no receipt."""
        behaviour = quote.get("binding_service", "confirms")
        if behaviour == "no_receipt":
            return None
        receipt = {
            "policy_number": f"HC-POL-{offer['quote_id'].split('-')[2]}-{_digest(request_id, offer['offer_id'])[:6]}",
            "offer_id": offer["offer_id"],
            "offer_version": offer["version"],
            "answers_hash": offer["answers_hash"],
            "bound_at": self.data["as_of"],
            "effective_from": offer["answers"].get("start_date"),
        }
        if behaviour == "mismatched_receipt":
            # The service bound an older answer set: the receipt cannot prove this offer.
            receipt["answers_hash"] = "stale-" + offer["answers_hash"][:6]
        return receipt


_SERVICES: dict[str, QuoteService] = {}


def service_for(conversation_id: str) -> QuoteService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = QuoteService()
    return _SERVICES[conversation_id]


# ----------------------------------------------------------------------------
# Views and summaries (what the tools return and what the engine reads back)
# ----------------------------------------------------------------------------


def answers_summary(svc: QuoteService, quote: dict) -> str:
    labels = svc.data["question_labels"]
    return "; ".join(
        f"{labels[q]}: {quote['answers'][q]}" for q in svc.data["questions"][quote["product"]]
    )


def offer_summary(svc: QuoteService, quote: dict, offer: dict) -> str:
    return (
        f"Offer {offer['offer_id']} (version {offer['version']}) for {quote['label']}: "
        f"{_money(offer['monthly_premium_usd'])} USD a month, starting "
        f"{offer['answers'].get('start_date')}, valid until {offer['expires_at'][:10]}."
    )


def offer_view(svc: QuoteService, quote: dict, offer: dict) -> dict:
    return {
        "offer_id": offer["offer_id"],
        "version": offer["version"],
        "state": svc.offer_state(offer),
        "monthly_premium_usd": offer["monthly_premium_usd"],
        "start_date": offer["answers"].get("start_date"),
        "issued_at": offer["issued_at"],
        "expires_at": offer["expires_at"],
        "answers_hash": offer["answers_hash"],
    }


def _not_found(quote_id: Any) -> dict:
    # Someone else's quote and a quote that does not exist get the same answer.
    return {
        "status": "not_found",
        "quote_id": normalise_id(quote_id),
        "bound": False,
        "policy_number": None,
        "next_step": (
            "Say you cannot find that quote on this customer's account and ask them "
            "to check it. Do not say whether it exists for anyone else."
        ),
    }


def _customer_quotes(svc: QuoteService, customer_id: Optional[str]) -> list[dict]:
    return [
        {"quote_id": qid, "product": q["product"], "label": q["label"], "state": svc.quote_state(q)}
        for qid, q in sorted(svc.quotes.items())
        if customer_id and q["customer_id"] == customer_id
    ]


def get_quote(svc: QuoteService, customer_id: Optional[str], quote_id: Optional[str]) -> dict:
    """The quote's state as HarborCover's services record it. Never binds anything."""
    if not quote_id:
        return {"status": "listed", "quotes": _customer_quotes(svc, customer_id), "bound": False,
                "next_step": "Ask which quote the customer means, by product."}
    quote = svc.quote_of(customer_id, quote_id)
    if quote is None:
        return _not_found(quote_id)
    number = normalise_id(quote_id)
    state = svc.quote_state(quote)
    offer = svc.current_offer(quote)
    other_offers = [
        offer_view(svc, quote, o) for o in svc.offers.values()
        if o["quote_id"] == number and (offer is None or o["offer_id"] != offer["offer_id"])
    ]
    view = {
        "status": "found",
        "quote_id": number,
        "product": quote["product"],
        "label": quote["label"],
        "state": state,
        "estimate": {
            **quote["estimate"],
            "kind": "indicative_estimate",
            "is_offer": False,
            "is_cover": False,
        },
        "answers": dict(quote["answers"]),
        "answers_confirmed": quote["confirmed_answers_hash"] == answers_hash(quote["answers"]),
        "current_offer": offer_view(svc, quote, offer) if offer else None,
        "other_offers": other_offers,
        "bound": bool(quote["policy"]),
        "policy_number": (quote["policy"] or {}).get("policy_number"),
        "not_cover": None if quote["policy"] else NOT_COVER,
    }
    view["next_step"] = {
        "estimate": "The estimate is a price range, not an offer. Offer request_underwritten_offer for a firm price.",
        "offer": "Present the current offer as not active cover yet, and ask whether to review the answers before asking to bind it.",
        "referred": "The answers were referred to an underwriter. There is no offer to bind. Offer request_underwriting_callback.",
        "bind_pending": "A bind request has no receipt. Say it is not bound and call check_bind_status.",
        "bound": "Report the policy number and start date from the receipt.",
    }[state]
    return view


def request_underwritten_offer(svc: QuoteService, customer_id: Optional[str], quote_id: str) -> dict:
    """Send the quote's current answers to underwriting. Returns an offer or a referral."""
    quote = svc.quote_of(customer_id, quote_id)
    if quote is None:
        return _not_found(quote_id)
    number = normalise_id(quote_id)
    if quote["policy"]:
        return {"status": "already_bound", "quote_id": number, "bound": True,
                "policy_number": quote["policy"]["policy_number"],
                "next_step": "The quote is already bound. Report the policy number."}
    current_hash = answers_hash(quote["answers"])
    offer = svc.current_offer(quote)
    if offer is not None and offer["answers_hash"] == current_hash:
        return {**_offered(svc, quote, offer), "unchanged": True}
    claims = int(quote["answers"].get("prior_claims_3y") or 0)
    if claims >= svc.data["referral_threshold_prior_claims"]:
        quote["referral"] = current_hash
        return {
            "status": "referred",
            "quote_id": number,
            "offer": None,
            "bound": False,
            "policy_number": None,
            "reference": f"HC-UW-REF-{_digest(number, current_hash)}",
            "reason": "prior claims need an underwriter's review",
            "next_step": (
                "Say underwriting could not make an offer on these answers and an "
                "underwriter will review them. There is nothing to bind. Offer "
                "request_underwriting_callback."
            ),
        }
    version = svc.next_version(number)
    offer = {
        "offer_id": f"HC-OFR-{number.split('-')[-1]}-{version}",
        "quote_id": number,
        "version": version,
        "monthly_premium_usd": svc.price(quote["product"], quote["answers"]),
        "answers": dict(quote["answers"]),
        "answers_hash": current_hash,
        "issued_at": svc.data["as_of"],
        "expires_at": (svc.as_of + timedelta(days=svc.data["offer_validity_days"])).isoformat(),
        "status": "offered",
    }
    previous = svc.offers.get(quote.get("current_offer_id") or "")
    if previous is not None and previous["status"] == "offered":
        previous["status"] = "superseded"
    svc.offers[offer["offer_id"]] = offer
    quote["current_offer_id"] = offer["offer_id"]
    quote["referral"] = None
    return _offered(svc, quote, offer)


def _offered(svc: QuoteService, quote: dict, offer: dict) -> dict:
    return {
        "status": "offered",
        "quote_id": offer["quote_id"],
        "offer": offer_view(svc, quote, offer),
        "offer_id": offer["offer_id"],
        "estimate_range_usd": quote["estimate"]["monthly_premium_range_usd"],
        "answers": dict(offer["answers"]),
        "answers_confirmed": quote["confirmed_answers_hash"] == offer["answers_hash"],
        "bound": False,
        "policy_number": None,
        "not_cover": NOT_COVER,
        "next_step": (
            "Say this is the current offer, not active cover yet, and ask whether to "
            "review the answers before asking to bind it. If they agree, call "
            "confirm_material_answers."
        ),
    }


def update_quote_answer(
    svc: QuoteService, customer_id: Optional[str], quote_id: str, question: str, value: Any
) -> dict:
    """Change one material answer. A change withdraws the current offer."""
    quote = svc.quote_of(customer_id, quote_id)
    if quote is None:
        return _not_found(quote_id)
    number = normalise_id(quote_id)
    questions = svc.data["questions"][quote["product"]]
    key = str(question or "").strip().lower()
    if key not in questions:
        return {"status": "unknown_question", "quote_id": number, "question": key,
                "valid_questions": questions,
                "next_step": "Use one of valid_questions for this product."}
    if quote["policy"]:
        return {"status": "refused", "reason": "policy_already_bound", "quote_id": number,
                "bound": True, "policy_number": quote["policy"]["policy_number"],
                "next_step": ("A bound policy is changed through a policy change, not this quote. "
                              "Offer request_underwriting_callback.")}
    answer = normalise_answer(key, value)
    if answer is None:
        return {"status": "invalid_value", "quote_id": number, "question": key,
                "next_step": "Ask the customer again. Dates go as YYYY-MM-DD, numbers as digits, yes or no as yes or no."}
    before = quote["answers"][key]
    if answer == before:
        return {"status": "unchanged", "quote_id": number, "question": key, "value": answer,
                "offer_withdrawn": None,
                "next_step": "Nothing changed. Continue with the current offer."}
    quote["answers"][key] = answer
    quote["confirmed_answers_hash"] = None
    withdrawn = None
    offer = svc.offers.get(quote.get("current_offer_id") or "")
    if offer is not None and offer["status"] == "offered":
        offer["status"] = "withdrawn"
        offer["withdrawn_reason"] = f"{key} changed"
        withdrawn = offer["offer_id"]
    quote["current_offer_id"] = None
    return {
        "status": "answer_updated",
        "quote_id": number,
        "question": key,
        "previous_value": before,
        "value": answer,
        "offer_withdrawn": withdrawn,
        "answers_confirmed": False,
        "bound": False,
        "policy_number": None,
        "next_step": (
            "Tell the customer the old offer is withdrawn because a material answer "
            "changed. Call request_underwritten_offer for a new offer before any bind."
            if withdrawn else
            "Call request_underwritten_offer before any bind."
        ),
    }


def _blocked(reason: str, detail: str, **extra: Any) -> dict:
    next_step = {
        "estimate_only": (
            "There is no current underwritten offer for this bind. Say nothing is "
            "bound and the customer is not covered by it. Get the quote's current "
            "offer with request_underwritten_offer and present it before any bind."
        ),
        "answers_not_confirmed": (
            "The material answers for this offer are not confirmed. Nothing is "
            "bound. Call confirm_material_answers (the engine reads them back), "
            "then bind the current offer."
        ),
    }[reason]
    return {"status": "blocked", "reason": reason, "detail": detail, "effects": 0,
            "bound": False, "policy_number": None, **extra, "next_step": next_step}


def confirm_material_answers(
    svc: QuoteService,
    customer_id: Optional[str],
    quote_id: str,
    shown_quote_id: Optional[str],
    shown_answers_hash: Optional[str],
) -> dict:
    """Record the customer's confirmation of the answers the engine read back."""
    quote = svc.quote_of(customer_id, quote_id)
    if quote is None:
        return _not_found(quote_id)
    number = normalise_id(quote_id)
    current = answers_hash(quote["answers"])
    if normalise_id(shown_quote_id) != number:
        return _blocked("answers_not_confirmed", "not_the_answers_read_back", quote_id=number)
    if shown_answers_hash != current:
        return _blocked("answers_not_confirmed", "answers_changed_since_read_back", quote_id=number)
    quote["confirmed_answers_hash"] = current
    offer = svc.current_offer(quote)
    matches = offer is not None and offer["answers_hash"] == current
    return {
        "status": "confirmed",
        "quote_id": number,
        "answers_hash": current,
        "offer_id": offer["offer_id"] if offer else None,
        "matches_current_offer": matches,
        "bound": False,
        "policy_number": None,
        "next_step": (
            "Call bind_offer with this offer_id. The engine asks the customer the "
            "separate bind question before anything is sent." if matches else
            "There is no current offer for these answers. Call request_underwritten_offer first."
        ),
    }


def bind_offer(
    svc: QuoteService,
    customer_id: Optional[str],
    offer_id: str,
    shown_offer_id: Optional[str],
    request_key: str,
) -> dict:
    """Bind one current, confirmed offer and prove it from the binding receipt."""
    ref = normalise_id(offer_id)
    offer = svc.offers.get(ref)
    quote = svc.quote_of(customer_id, offer["quote_id"]) if offer else None
    own_estimate = next(
        (q for q in svc.quotes.values()
         if q["estimate"]["reference"] == ref and customer_id and q["customer_id"] == customer_id),
        None,
    )
    if quote is None:
        # Unknown ids and other customers' offers read the same.
        detail = "indicative_estimate" if own_estimate else "no_current_offer"
        facts = {"underwritten_offer_current": False}
        return _blocked(evaluate(facts, "request"), detail, offer_id=ref, facts=facts)
    if quote["policy"] and quote["policy"]["offer_id"] == ref:
        # Replay of a bind that already has a receipt: no second effect.
        return {**_bind_result(svc, quote, offer, quote["policy"], replay=True)}
    state = svc.offer_state(offer)
    current = svc.current_offer(quote)
    is_current = state == "offered" and current is not None and current["offer_id"] == ref
    read_back = normalise_id(shown_offer_id) == ref
    facts = {
        "underwritten_offer_current": is_current and read_back,
        "material_answers_confirmed": (
            quote["confirmed_answers_hash"] is not None
            and quote["confirmed_answers_hash"] == offer["answers_hash"]
            and offer["answers_hash"] == answers_hash(quote["answers"])
        ),
    }
    reason = evaluate(facts, "request")
    if reason:
        if reason == "estimate_only":
            detail = {"withdrawn": "offer_withdrawn", "superseded": "offer_superseded",
                      "expired": "offer_expired"}.get(state, "not_the_offer_read_back")
        else:
            detail = "answers_changed_after_offer" if offer["answers_hash"] != answers_hash(quote["answers"]) \
                else "answers_not_confirmed"
        return _blocked(reason, detail, offer_id=ref, facts=facts)

    request_id = f"{request_key}:{ref}"
    replay = request_id in svc.binds
    if replay:
        receipt = svc.binds[request_id]["receipt"]
    else:
        receipt = svc.binding_service(quote, offer, request_id)
        svc.binds[request_id] = {"offer_id": ref, "receipt": receipt}
    facts["bind_receipt_verified"] = (
        receipt is not None
        and receipt.get("offer_id") == ref
        and receipt.get("offer_version") == offer["version"]
        and receipt.get("answers_hash") == offer["answers_hash"]
    )
    failure = evaluate(facts, "receipt")
    if failure:
        quote["bind_request"] = request_id
        return {
            "status": "pending",
            "reason": failure,
            "offer_id": ref,
            "offer_state": "unbound",
            "bind_request": _digest(request_id),
            "effects": 0 if replay else 1,
            "replay": replay,
            "bound": False,
            "policy_number": None,
            "receipt_received": receipt is not None,
            "facts": facts,
            "next_step": (
                "The bind request was sent but the binding service has not returned a "
                "matching receipt. Say the offer is not bound and the customer is not "
                "covered by it yet. Call check_bind_status for this offer_id, and if it "
                "is still pending offer request_underwriting_callback. Never give a "
                "policy number."
            ),
        }
    offer["status"] = "bound"
    quote["policy"] = receipt
    quote["bind_request"] = None
    return {**_bind_result(svc, quote, offer, receipt, replay=replay), "facts": facts}


def _bind_result(svc: QuoteService, quote: dict, offer: dict, receipt: dict, replay: bool) -> dict:
    return {
        "status": "succeeded",
        "reason": "verified_fixture_receipt",
        "offer_id": offer["offer_id"],
        "offer_version": offer["version"],
        "effects": 0 if replay else 1,
        "replay": replay,
        "bound": True,
        "policy_number": receipt["policy_number"],
        "effective_from": receipt["effective_from"],
        "monthly_premium_usd": offer["monthly_premium_usd"],
        "next_step": (
            "Give the policy number and say cover starts on effective_from, from the "
            "binding receipt."
        ),
    }


def check_bind_status(svc: QuoteService, customer_id: Optional[str], offer_id: str, request_key: str) -> dict:
    """Look up a bind request by offer id. Never sends a new bind."""
    ref = normalise_id(offer_id)
    offer = svc.offers.get(ref)
    quote = svc.quote_of(customer_id, offer["quote_id"]) if offer else None
    record = svc.binds.get(f"{request_key}:{ref}")
    if quote is None or record is None:
        return {"status": "unknown", "reason": "no_bind_request", "offer_id": ref, "bound": False,
                "policy_number": None,
                "next_step": "No bind request exists for this offer in this conversation. Nothing is bound."}
    if quote["policy"] and quote["policy"]["offer_id"] == ref:
        return {**_bind_result(svc, quote, offer, quote["policy"], replay=True), "status": "succeeded"}
    return {
        "status": "pending",
        "reason": "policy_not_bound",
        "offer_id": ref,
        "offer_state": "unbound",
        "bound": False,
        "policy_number": None,
        "next_step": (
            "Still no binding receipt. Say the offer is not bound and the customer is "
            "not covered by it. Offer request_underwriting_callback. Do not bind again."
        ),
    }


def underwriting_callback(svc: QuoteService, customer_id: Optional[str], quote_id: str, reason: str) -> dict:
    quote = svc.quote_of(customer_id, quote_id)
    if quote is None:
        return _not_found(quote_id)
    number = normalise_id(quote_id)
    callback = {
        "status": "routed",
        "quote_id": number,
        "reference": f"HC-UW-CB-{_digest(customer_id, number, 'callback')}",
        "route": "HarborCover underwriting desk",
        "reason": " ".join(str(reason or "").split())[:200],
        "bound": bool(quote["policy"]),
        "policy_number": (quote["policy"] or {}).get("policy_number"),
        "next_step": "Give the reference. The underwriting desk calls back within one business day.",
    }
    svc.callbacks.append(callback)
    return callback


# Mantle cuts every memory value to 100 characters where the model reads it
# (MAX_MEMORY_VALUE_LENGTH in rasa/mantle/prompts/memory_lines.py, for both the
# prompt's memory section and @memory substitution in skill text), and says
# only "... [truncated]". The first version listed each quote with its label,
# 201 characters: the renters quote fell off the end, and the model told
# customers they had no renters quote. Ids and products fit.
MEMORY_VALUE_LIMIT = 100


def saved_quotes_line(quotes: list[dict]) -> str:
    line = "; ".join(f"{q['quote_id']} {q['product']}" for q in quotes)
    if len(line) > MEMORY_VALUE_LIMIT:
        raise ValueError("saved_quotes would be truncated in the model's prompt")
    return line


def caller_profile(svc: QuoteService, customer_id: str = DEMO_CUSTOMER_ID) -> dict:
    person = svc.data["customers"][customer_id]
    return {
        "customer_id": customer_id,
        "first_name": person["first_name"],
        "quotes": _customer_quotes(svc, customer_id),
    }
