"""Northgate Bank loan servicing and the payoff-quote guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the three request-phase rules of the casebook contract for
``banking-loan-servicing`` (vendored as ``lib/fixtures/case-contract.json``)
when a payoff quote is presented, and again when payoff instructions are sent,
from the servicing system's own records at that moment:

- ``quote_valid_today``: the servicing clock is before the quote's
  good-through time. Yesterday's quote, good through yesterday at 5 PM, fails.
- ``included_charges_explicit``: the quote lists each included charge, and
  the charges add up to the quoted amount. A lump sum from a module that
  gives no breakdown fails.
- ``servicing_route_available``: the loan has an open servicing route for the
  next step (payoff instructions). A loan mid-way through a servicing
  transfer fails.

The model supplies the caller's words for a loan, a ``quote_ref`` copied from
a tool result, and short notes. It never supplies an amount, a date, a fact,
a customer id or an outcome, so it cannot turn a balance, or a figure the
caller remembers from yesterday, into a quote. A blocked presentation returns
no amount at all.

The receipt is a dated payoff-quote reference with the amount, each included
charge, the good-through time and the next servicing step. Viewing a quote is
not paying it: no tool takes a payment, and a loan closes only after the
payoff is received and posted.

The organisation guard runs at import: the fixture must mark the bank as
fictional and may not name a real lender or servicer.

Servicing state lives in an in-process service with one copy of the fixture
per conversation, so every scripted conversation starts from the same records.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "northgate_loans.json"

# Mantle renders at most this many characters of one memory value to the model
# (rasa.mantle.prompts.memory_lines.MAX_MEMORY_VALUE_LENGTH) and marks the rest
# only "... [truncated]", with no log line. Earlier case builds lost list items
# to it. Every memory value this project writes is one short field, and
# tests/test_guard.py fails if one could exceed the limit.
PROMPT_MEMORY_VALUE_LIMIT = 100

OWNER = "loan servicing owner"

# Real lenders and servicers the fixture must never name. The fixture is public
# teaching data; a real name in it would read as a claim about that company.
# This list is a tripwire, not a register of every lender.
REAL_LENDERS = (
    "chase", "jpmorgan", "wells fargo", "bank of america", "citi", "citibank", "capital one",
    "us bank", "u.s. bank", "pnc", "truist", "td bank", "ally", "santander", "barclays", "hsbc",
    "lloyds", "natwest", "discover", "sofi", "navient", "nelnet", "mr. cooper", "rocket mortgage",
)


class FictionalOrganisationError(RuntimeError):
    """The fixture does not describe a clearly fictional organisation."""


def assert_fictional(data: dict) -> None:
    """Refuse fixture data that is not marked fictional or names a real lender."""
    organisation = str(data.get("organisation") or "")
    if "(fictional" not in organisation.lower():
        raise FictionalOrganisationError(f"organisation must be marked '(fictional)': {organisation!r}")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")
    text = json.dumps(data).lower()
    for name in REAL_LENDERS:
        if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", text):
            raise FictionalOrganisationError(f"the fixture names a real lender: {name!r}")


# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA)

ORGANISATION = _DATA["organisation"].split(" (")[0]
DEMO_CUSTOMER_ID = _DATA["session_customer_id"]
CENT = Decimal("0.01")


# ----------------------------------------------------------------------------
# Wording: the output guard in hooks.py and the case-build metrics use these,
# and tests/test_guard.py keeps the copies in case-build/conversations.json
# identical.
# ----------------------------------------------------------------------------

_AMOUNT = r"\$\s?(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?)"

# A payoff figure: "your payoff is $14,252.82", "payoff amount of $6,878.21",
# "$14,230.08 will pay the loan off", "about $48,900 to close it".
PAYOFF_FIGURE_RE = re.compile(
    r"(?:pay\s?-?off|payoff)\b(?:(?!principal|interest|fee|includ|charge|balance|statement)[^$.?!;\n]){0,60}?"
    r"(?:about|around|roughly|approximately|approx\.?|~)?\s*" + _AMOUNT
    + r"|" + _AMOUNT + r"\s+(?:should|will|would|to)\s+(?:fully\s+)?(?:pay\s+(?:it|the\s+loan|your\s+loan|this)\s+off|pay\s+off|close|settle)",
    re.IGNORECASE,
)
# A figure is not presented as a payoff when the sentence negates or dates it
# first: "yesterday's payoff of $14,230.08 has expired", "not $14,212.55".
PAYOFF_HEDGE_RE = re.compile(
    r"\b(?:not|no|never|yesterday|yesterday's|expired|old|older|earlier|previous|prior|was|"
    r"isn't|wasn't|cannot|can't|won't)\b|n't\b",
    re.IGNORECASE,
)

# A promise that the loan will close, or has closed, from anything the agent did.
CLOSURE_PROMISE_RE = re.compile(
    r"\b(?:your|the|this)\s+(?:\w+\s+)?loan\s+(?:will|would|should)\s+(?:then\s+)?(?:be\s+)?"
    r"(?:closed|close|paid\s+off|paid\s+in\s+full|settled)\b"
    r"|\bloan\s+(?:is|has\s+been)\s+(?:now\s+)?(?:closed|paid\s+off|paid\s+in\s+full|settled)\b"
    r"|\b(?:close|closes|closing)\s+(?:your|the|this)\s+(?:\w+\s+)?loan\s+(?:today|now|immediately|right\s+away)\b",
    re.IGNORECASE,
)
CLOSURE_HEDGE_RE = re.compile(
    r"\b(?:once|when|after|if|until|only|not|never|cannot|can't|won't|unless|before|whether)\b|n't\b",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
# A hedge counts only inside its own clause: "that was yesterday's figure; your
# payoff today is $X" still presents $X.
_CLAUSE_BREAK_RE = re.compile(r"[,;:\u2014]|\s-\s|\b(?:and|but|while|whereas)\b", re.IGNORECASE)


def _clause_before(sentence: str, start: int) -> str:
    head = sentence[:start]
    breaks = list(_CLAUSE_BREAK_RE.finditer(head))
    return head[breaks[-1].end():] if breaks else head


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_RE.split(text or "") if s.strip()]


def _amount(text: str) -> Decimal:
    return Decimal(text.replace(",", "")).quantize(CENT)


def payoff_figures(text: str) -> list[Decimal]:
    """Amounts the text presents as a payoff figure, sentence by sentence.

    Questions and sentences that negate or date the figure before it are skipped.
    """
    found: list[Decimal] = []
    for sentence in _sentences(text):
        if sentence.rstrip().endswith("?"):
            continue
        for match in PAYOFF_FIGURE_RE.finditer(sentence):
            # The hedge may sit before the figure or inside the match ("payoff is not $X").
            if PAYOFF_HEDGE_RE.search(_clause_before(sentence, match.start()) + " " + match.group(0)):
                continue
            value = match.group(1) or match.group(2)
            found.append(_amount(value))
    return found


def closure_promises(text: str) -> list[str]:
    """Phrases that promise the loan will close or has closed, with no condition before them."""
    found = []
    for sentence in _sentences(text):
        if sentence.rstrip().endswith("?"):
            continue
        for match in CLOSURE_PROMISE_RE.finditer(sentence):
            # A condition anywhere earlier in the sentence ("once it posts, ...") makes it conditional.
            if not CLOSURE_HEDGE_RE.search(sentence[: match.start()]):
                found.append(match.group(0))
    return found


# ----------------------------------------------------------------------------
# Contract
# ----------------------------------------------------------------------------


def load_contract() -> dict:
    return json.loads(json.dumps(_CONTRACT))


def load_data() -> dict:
    return json.loads(json.dumps(_DATA))


def request_rules(contract: Optional[dict] = None) -> list[dict]:
    contract = contract or _CONTRACT
    return [rule for rule in contract["rules"] if rule["phase"] == "request"]


def evaluate(facts: dict, contract: Optional[dict] = None) -> Optional[str]:
    """First failing request rule's reason, or None. Exactly ``True`` passes."""
    for rule in request_rules(contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:6].upper()


def money(value: Decimal) -> str:
    return f"${value.quantize(CENT):,.2f}"


def when(value: str) -> str:
    """'2026-10-09T17:00:00-04:00' -> 'Oct 9, 2026, 5:00 PM ET'."""
    moment = datetime.fromisoformat(value)
    hour = moment.strftime("%I").lstrip("0")
    return f"{moment.strftime('%b')} {moment.day}, {moment.year}, {hour}:{moment.strftime('%M %p')} ET"


def day(value: str) -> str:
    moment = datetime.fromisoformat(value) if "T" in value else datetime.fromisoformat(value + "T00:00:00")
    return f"{moment.strftime('%b')} {moment.day}, {moment.year}"


def normalise_ref(value: Any) -> str:
    return re.sub(r"[^A-Z0-9-]", "", str(value or "").strip().upper())


def _words(value: Any) -> str:
    return " ".join(re.findall(r"[a-z]+", str(value or "").lower()))


# ----------------------------------------------------------------------------
# The servicing system for one conversation
# ----------------------------------------------------------------------------


class Servicing:
    """Loans, payoff quotes and the servicing log for one conversation (fixture copy)."""

    def __init__(self, data: Optional[dict] = None) -> None:
        data = data or load_data()
        self.clock = datetime.fromisoformat(data["servicing_clock"])
        self.customers: dict = data["customers"]
        self.loans: dict[str, dict] = data["loans"]
        self.quotes: dict[str, dict] = data["quotes"]
        for quote in self.quotes.values():
            quote["amount"] = Decimal(quote["amount"])
        self.presentations: list[dict] = []
        self.instructions: list[dict] = []
        self.callbacks: list[dict] = []
        self.hardship: dict[str, dict] = {}

    def loans_of(self, customer_id: Optional[str]) -> dict[str, dict]:
        return {r: l for r, l in sorted(self.loans.items()) if customer_id and l["customer_id"] == customer_id}

    def latest_quote(self, loan_ref: str) -> Optional[tuple[str, dict]]:
        mine = [(ref, q) for ref, q in self.quotes.items() if q["loan"] == loan_ref]
        if not mine:
            return None
        return max(mine, key=lambda item: datetime.fromisoformat(item[1]["quoted_at"]))

    def facts(self, quote: dict) -> dict:
        """The contract's three facts, computed from servicing records now."""
        loan = self.loans[quote["loan"]]
        charges = quote.get("charges") or []
        explicit = bool(charges) and all(c.get("label") and c.get("amount") for c in charges) and (
            sum((Decimal(c["amount"]) for c in charges), Decimal("0")).quantize(CENT) == quote["amount"]
        )
        return {
            "quote_valid_today": self.clock < datetime.fromisoformat(quote["good_through"]),
            "included_charges_explicit": explicit,
            "servicing_route_available": bool((loan.get("servicing_route") or {}).get("open")),
        }


_SERVICES: dict[str, Servicing] = {}


def servicing_for(conversation_id: str) -> Servicing:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = Servicing()
    return _SERVICES[conversation_id]


def loan_label(loan: dict) -> str:
    return f"{loan['product']} ending {loan['last_four']}"


def profile_memory_lines(customer_id: str = DEMO_CUSTOMER_ID, svc: Optional[Servicing] = None) -> dict[str, str]:
    """Project memory, one short field per loan. Each value stays under the prompt limit."""
    svc = svc or Servicing()
    return {loan["memory_key"]: loan_label(loan) for loan in svc.loans_of(customer_id).values()}


def caller_profile(customer_id: str = DEMO_CUSTOMER_ID, svc: Optional[Servicing] = None) -> dict:
    svc = svc or Servicing()
    customer = svc.customers[customer_id]
    return {
        "customer_id": customer_id,
        "first_name": customer["first_name"],
        "loans": profile_memory_lines(customer_id, svc),
    }


def resolve_loan(svc: Servicing, customer_id: Optional[str], spoken: Any) -> dict:
    """The caller's words to exactly one of their loans, or blocked.

    Another customer's loan number is answered exactly like a number that does
    not exist, so the reply leaks nothing about it.
    """
    mine = svc.loans_of(customer_id)
    text = str(spoken or "")
    ref = normalise_ref(text)
    id_match = re.search(r"NB-?LN-?(\d{4})", ref)
    digits = re.findall(r"\d{4}", text)
    phrase = _words(text)
    hits: list[str] = []
    if id_match:
        hits = [r for r, l in mine.items() if l["last_four"] == id_match.group(1)]
    elif digits:
        hits = [r for r, l in mine.items() if l["last_four"] in digits]
    else:
        for r, loan in mine.items():
            if any(re.search(rf"\b{re.escape(alias)}\b", phrase) for alias in loan["aliases"]):
                hits.append(r)
    if len(hits) == 1:
        return {"status": "resolved", "loan_ref": hits[0], "loan": loan_label(mine[hits[0]])}
    if not hits and (id_match or digits):
        return {"status": "blocked", "reason": "loan_not_found",
                "detail": "No loan with that number on this customer's profile.",
                "next_step": "Ask which of the customer's own loans they mean."}
    return {
        "status": "blocked",
        "reason": "loan_ambiguous",
        "candidates": [loan_label(l) for l in mine.values()] if not hits else [loan_label(mine[r]) for r in hits],
        "next_step": "Ask which loan the customer means. Do not choose for them.",
    }


def get_loan_balance(svc: Servicing, customer_id: Optional[str], loan: Any) -> dict:
    resolved = resolve_loan(svc, customer_id, loan)
    if resolved["status"] != "resolved":
        return resolved
    record = svc.loans[resolved["loan_ref"]]
    return {
        "status": "read",
        "loan": resolved["loan"],
        "principal_balance": money(Decimal(record["principal_balance"])),
        "balance_as_of": day(record["balance_as_of"]),
        "next_payment_due": day(record["next_payment"]["due"]),
        "next_payment_amount": money(Decimal(record["next_payment"]["amount"])),
        "not_a_payoff": (
            "This is the principal balance at the last statement. It is not a payoff amount: a payoff "
            "adds interest accrued to the payoff date and any fees, and only a dated payoff quote from "
            "present_payoff_quote states it."
        ),
    }


_BLOCKED_NEXT_STEP = {
    "quote_expired": "Call refresh_payoff_quote for this loan, then present_payoff_quote again. Give no figure from the expired quote.",
    "quote_scope_missing": "Call refresh_payoff_quote for this loan, then present_payoff_quote again. Give no figure from this quote.",
    "no_servicing_route": "Offer schedule_servicing_callback with the loan servicing team. Give no payoff figure.",
}


def present_payoff_quote(svc: Servicing, customer_id: Optional[str], loan: Any) -> dict:
    """Present the latest payoff quote on file for one loan, if the contract allows it.

    A blocked result carries no amount, so a stale or unscoped figure never
    reaches the caller through this tool.
    """
    resolved = resolve_loan(svc, customer_id, loan)
    if resolved["status"] != "resolved":
        return {**resolved, "effects": 0}
    loan_ref = resolved["loan_ref"]
    latest = svc.latest_quote(loan_ref)
    if latest is None:
        return {"status": "blocked", "reason": "quote_expired", "loan": resolved["loan"], "effects": 0,
                "detail": "No payoff quote on file.", "next_step": _BLOCKED_NEXT_STEP["quote_expired"]}
    quote_ref, quote = latest
    facts = svc.facts(quote)
    reason = evaluate(facts)
    if reason:
        result = {
            "status": "blocked",
            "reason": reason,
            "loan": resolved["loan"],
            "quote_ref": quote_ref,
            "quoted_at": when(quote["quoted_at"]),
            "good_through": when(quote["good_through"]),
            "facts": facts,
            "effects": 0,
            "next_step": _BLOCKED_NEXT_STEP[reason],
        }
        if reason == "no_servicing_route":
            result["detail"] = svc.loans[loan_ref]["servicing_route"].get("detail")
        return result
    svc.presentations.append({"quote_ref": quote_ref, "loan_ref": loan_ref})
    return {
        "status": "presented",
        "reason": "verified_fixture_receipt",
        "loan": resolved["loan"],
        "quote_ref": quote_ref,
        "payoff_amount": money(quote["amount"]),
        "quoted_at": when(quote["quoted_at"]),
        "good_through": when(quote["good_through"]),
        "included_charges": [f"{c['label']}: {money(Decimal(c['amount']))}" for c in quote["charges"]],
        "next_step": (
            "Payoff instructions can be sent to the customer's secure message inbox "
            "(send_payoff_instructions). Viewing a quote is not a payment: the loan closes only after "
            "the payoff is received and posted by the good-through time."
        ),
        "facts": facts,
        "effects": 1,
    }


def refresh_payoff_quote(svc: Servicing, customer_id: Optional[str], loan: Any) -> dict:
    """Ask the servicing system for a new quote. It moves no money and states no amount."""
    resolved = resolve_loan(svc, customer_id, loan)
    if resolved["status"] != "resolved":
        return resolved
    loan_ref = resolved["loan_ref"]
    record = svc.loans[loan_ref]
    refresh = record["refresh"]
    if refresh["outcome"] != "issued":
        return {
            "status": "unavailable",
            "reason": "quote_source_unavailable",
            "loan": resolved["loan"],
            "detail": refresh.get("detail"),
            "next_step": "Offer schedule_servicing_callback. Do not estimate or compute a payoff figure.",
        }
    quote_ref = f"PQ-{record['last_four']}-{_digest(loan_ref, svc.clock.isoformat())}"
    if quote_ref not in svc.quotes:
        charges = refresh["charges"]
        svc.quotes[quote_ref] = {
            "loan": loan_ref,
            "quoted_at": svc.clock.isoformat(),
            "good_through": refresh["good_through"],
            "amount": sum((Decimal(c["amount"]) for c in charges), Decimal("0")).quantize(CENT),
            "charges": charges,
        }
    return {
        "status": "issued",
        "loan": resolved["loan"],
        "quote_ref": quote_ref,
        "next_step": "Call present_payoff_quote for this loan to present the new quote.",
    }


def send_payoff_instructions(svc: Servicing, customer_id: Optional[str], presented_quote_ref: Optional[str],
                             quote_ref: Any) -> dict:
    """Send payoff instructions for the quote this conversation presented. Takes no payment."""
    ref = normalise_ref(quote_ref)
    presented = normalise_ref(presented_quote_ref)
    quote = svc.quotes.get(ref)
    if not presented or ref != presented or quote is None or \
            svc.loans[quote["loan"]]["customer_id"] != customer_id:
        return {"status": "blocked", "reason": "quote_not_presented", "effects": 0,
                "next_step": "Present a current quote with present_payoff_quote first."}
    loan = svc.loans[quote["loan"]]
    if quote["loan"] in svc.hardship:
        return {"status": "blocked", "reason": "hardship_referral_open", "effects": 0,
                "referral": svc.hardship[quote["loan"]]["reference"],
                "next_step": "The payoff flow is stopped. The hardship specialist covers the customer's options."}
    facts = svc.facts(quote)
    reason = evaluate(facts)
    if reason:
        return {"status": "blocked", "reason": reason, "facts": facts, "effects": 0,
                "next_step": _BLOCKED_NEXT_STEP[reason]}
    reference = f"PI-{loan['last_four']}-{_digest('instructions', ref)}"
    svc.instructions.append({"reference": reference, "quote_ref": ref})
    return {
        "status": "sent",
        "reference": reference,
        "quote_ref": ref,
        "loan": loan_label(loan),
        "channel": "secure message inbox",
        "payoff_amount": money(quote["amount"]),
        "good_through": when(quote["good_through"]),
        "payment_taken": False,
        "effects": 1,
        "next_step": (
            "The instructions explain how to pay the quoted amount by the good-through time. No payment "
            "was taken. The loan closes only after the payoff is received and posted."
        ),
    }


def schedule_servicing_callback(svc: Servicing, customer_id: Optional[str], loan: Any, reason: Any) -> dict:
    resolved = resolve_loan(svc, customer_id, loan)
    if resolved["status"] != "resolved":
        return resolved
    reference = f"CB-{svc.loans[resolved['loan_ref']]['last_four']}-{_digest('callback', resolved['loan_ref'], len(svc.callbacks))}"
    svc.callbacks.append({"reference": reference, "loan_ref": resolved["loan_ref"], "reason": str(reason or "")[:200]})
    return {
        "status": "scheduled",
        "reference": reference,
        "loan": resolved["loan"],
        "owner": OWNER,
        "window": "Oct 1, 2026, 9 AM to 12 PM ET, to the phone number on file",
        "next_step": "Loan servicing calls back with a confirmed figure. Give no estimate in the meantime.",
    }


def route_hardship_support(svc: Servicing, customer_id: Optional[str], loan: Any, note: Any) -> dict:
    """Refer the customer to the hardship team and stop the payoff flow for that loan."""
    resolved = resolve_loan(svc, customer_id, loan) if str(loan or "").strip() else {"status": "general"}
    loan_ref = resolved.get("loan_ref")
    reference = f"HS-{_digest('hardship', customer_id, loan_ref, len(svc.hardship))}"
    entry = {"reference": reference, "note": str(note or "")[:200]}
    if loan_ref:
        svc.hardship[loan_ref] = entry
    else:
        for ref in svc.loans_of(customer_id):
            svc.hardship.setdefault(ref, entry)
    return {
        "status": "routed",
        "reference": reference,
        "loan": resolved.get("loan") or "all of the customer's loans",
        "owner": f"{OWNER} (hardship support team)",
        "contact": "A hardship specialist contacts the customer within 1 business day.",
        "payoff_flow": "stopped",
        "next_step": (
            "Tell the customer the reference and who will contact them. Give no financial advice and "
            "promise no outcome; the specialist reviews the options."
        ),
    }
