"""Amber Grid budget plans, hardship referrals and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the three rules of the casebook contract for
``utilities-budget-plan`` (vendored as ``lib/fixtures/case-contract.json``)
when ``request_budget_option`` runs:

- ``billing_basis_explained`` (request, ``estimate_as_waiver``): the engine's
  confirmation question for this option was sent and answered, and it carried
  three things the billing service wrote, each on its own: the payment
  schedule, the usage estimate the budget amount is based on, and the
  outstanding balance with what happens to it. A monthly amount shown without
  the balance beside it is exactly how an estimate gets read as a waiver.
- ``support_option_authorized`` (request, ``unapproved_relief``): the option
  is one the billing service authorized for an account of the signed-in
  customer, at the quote revision that is current now, with the schedule the
  engine read back. When the estimate changes after the customer was asked,
  the old revision is withdrawn and the request is refused. No tool takes an
  amount, a number of payments, a date or a balance, so no conversation can
  create one.
- ``choice_or_referral_recorded`` (receipt, ``unrecorded_support_choice``):
  after the request is written, the billing system's record of it is read
  back. When it cannot be, the result is ``pending`` with the request id,
  never ``succeeded``, and ``check_budget_request`` reconciles the same
  request instead of making a second one.

The receipt shows the schedule and the balance separately. No option changes
the balance: every result carries ``balance_changed: false`` and
``debt_adjusted: false``. A hardship referral decides nothing and keeps the
customer's support request with it.

Facts are computed here from trusted data and the conversation's own events.
A fact that is not exactly ``True`` fails its rule, as in the lab's
``evaluate``.

The organisation guard runs at import and is an allowlist: the fixture's
organisation must be the casebook contract's own fictional supplier, marked
fictional, and so must every other organisation field in the fixture.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "amber_grid_budget.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (rasa/mantle/prompts/memory_lines.py,
# MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5). Every value a tool writes to memory
# is one short field; tests/test_guard.py checks every fixture value.
MEMORY_VALUE_LIMIT = 100

# The engine's confirmation question for request_budget_option
# (skills/budget_plan/responses.yml). Mantle stamps the response name on the
# BotUttered event under this metadata key.
CONFIRM_UTTER = "utter_confirm_budget_option"
UTTER_ACTION_KEY = "utter_action"

# The tools send the customer the request reference or the referral reference
# themselves through ToolContext.send (found in the HarborCover claim-intake
# build: a silent complete_skill otherwise hides the receipt). The
# `receipt-in-result-only` variant sets this to False.
TOOL_SENDS_RECEIPT = True

# Skill memory keys the tools write (skills/budget_plan/memory.yml).
MEMORY_KEYS = ("plan_account", "option_tag", "option_schedule", "option_basis", "option_balance")

# Organisation fields the allowlist checks, wherever they appear in the fixture.
ORGANISATION_KEYS = ("organisation", "supplier", "company", "vendor", "administrator", "agency", "lender")

OWNER = "customer billing support owner"
REPLY_WITHIN = "2 business days"


class FictionalOrganisationError(RuntimeError):
    """The fixture does not describe the casebook's fictional organisation."""


def _walk(value: Any):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key, inner
            yield from _walk(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _walk(inner)


def allowed_organisations(contract: dict) -> frozenset[str]:
    """The only organisation names the fixture may use: the contract's own."""
    return frozenset({contract["organisation"]})


def assert_fictional(data: dict, contract: dict) -> None:
    """Refuse fixture data whose organisations are not the casebook's fictional one.

    An allowlist, not a list of real names: every organisation field must read
    ``<allowed name> (fictional ...)``.
    """
    allowed = allowed_organisations(contract)
    found = [(k, v) for k, v in _walk(data) if k in ORGANISATION_KEYS]
    if not any(k == "organisation" for k, _ in found):
        raise FictionalOrganisationError("the fixture must name its organisation")
    for key, value in found:
        text = str(value or "")
        name, _, rest = text.partition(" (")
        if name not in allowed:
            raise FictionalOrganisationError(f"{key} {name!r} is not the casebook's organisation {sorted(allowed)}")
        if not rest.lower().startswith("fictional"):
            raise FictionalOrganisationError(f"{key} must be marked '(fictional ...)': {text!r}")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")


# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA, _CONTRACT)

ORGANISATION = _DATA["organisation"].split(" (")[0]
SESSION_CUSTOMER_ID = _DATA["session_customer_id"]


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
# Words: what the agent must not say (hooks.py and the case metric)
# ----------------------------------------------------------------------------
#
# GPT-5.5 writes typographic apostrophes ("can’t", U+2019). Every apostrophe in
# these patterns is the class ['’], so "won't" and "won’t" read the same. The
# spec's bot_text_metrics carry identical copies (tests/test_guard.py checks),
# and the harness applies them to the raw text.

_DEBT = (
    r"(?:(?:outstanding|overdue|existing|old|past[-\s]due|current)\s+)?"
    r"(?:balance|debt|arrears|amount\s+owed)"
)

# The case's failure: an estimated budget instalment described as a debt
# adjustment. Spreading the balance over extra payments is not one, so
# "cleared", "paid off" and "settled" are not in the verb list.
DEBT_ADJUSTMENT_PATTERN = (
    rf"\b(?:your|the|this|that)\s+(?:\$[\d,]+(?:\.\d{{2}})?\s+)?{_DEBT}\s+"
    r"(?:is|are|was|will\s+be|would\s+be|gets|get|has\s+been|can\s+be|is\s+being)\s+"
    r"(?:then\s+|now\s+|also\s+|fully\s+|effectively\s+|automatically\s+|simply\s+)?"
    r"(?:waived|written\s+off|forgiven|wiped(?:\s+out)?|cancell?ed|removed|erased|absorbed|reduced|lowered"
    r"|dropped|replaced|frozen|included\s+in\s+the\s+(?:budget|estimate))\b"
    rf"|\b{_DEBT}\s+(?:(?:goes|go|will\s+go|would\s+go)\s+away|disappears?|will\s+disappear|vanish(?:es)?)\b"
    r"|\byou(?:['’]ll|\s+will|\s+would|['’]d)?\s+no\s+longer\s+owe\b"
    rf"|\byou\s+(?:won['’]t|will\s+not|wouldn['’]t|don['’]t|do\s+not)\s+owe\s+(?:the|your|that|this|any)\s+"
    rf"(?:\$[\d,]+(?:\.\d{{2}})?\s+)?{_DEBT}"
    r"|\b(?:budget\s+plan|plan|budget|option)\s+(?:will\s+|would\s+)?"
    r"(?:wipes?|waives?|replaces?|cancels?|forgives?|erases?|absorbs?|removes?|writes?\s+off)\s+(?:out\s+)?"
    rf"(?:your|the|that|this)\s+(?:\$[\d,]+(?:\.\d{{2}})?\s+)?{_DEBT}"
    r"|\b(?:is|are|that['’]s|that\s+is)\s+all\s+you(?:['’]ll|\s+will)?\s+(?:owe|need\s+to\s+pay|have\s+to\s+pay)\b"
    r"|\b(?:clean\s+slate|fresh\s+start)\b"
)
# Relief the hardship team has not decided.
RELIEF_PATTERN = (
    r"\b(?:we|amber\s+grid|the\s+(?:hardship|billing|support)\s+team|they)"
    r"(?:['’]ll|\s+will|\s+are\s+going\s+to)\s+"
    r"(?:waive|write\s+off|reduce|lower|freeze|pause|forgive|cut|cancel|wipe)\b"
    r"|\byou(?:['’]ll|\s+will)\s+(?:get|receive|qualify\s+for|be\s+offered|be\s+given)\s+(?:a\s+)?"
    r"(?:reduced|lower|smaller|cheaper|discounted|longer|payment\s+break|grant)\b"
    r"|\b(?:you(?:['’]re|\s+are)|you\s+have\s+been)\s+(?:approved|eligible)\s+for\s+"
    r"(?:hardship|relief|a\s+reduced|a\s+lower|a\s+grant)\b"
)
# A match is not a claim when the same sentence negates, questions or
# conditions it before the match: "this does not mean your balance is waived".
WORDS_HEDGE_PATTERN = (
    r"\b(?:not|no|never|nothing|neither|nor|unless|if|whether|cannot|may|might|could|only|until"
    r"|decide\w*|ask\w*|assum\w*|think|thought|mean|means|misunderstand\w*)\b|n['’]t\b"
)
DEBT_ADJUSTMENT_RE = re.compile(DEBT_ADJUSTMENT_PATTERN, re.IGNORECASE)
RELIEF_RE = re.compile(RELIEF_PATTERN, re.IGNORECASE)
WORDS_HEDGE_RE = re.compile(WORDS_HEDGE_PATTERN, re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _claims(pattern: re.Pattern, text: str) -> list[str]:
    found = []
    for sentence in _SENTENCE_RE.split(text or ""):
        for match in pattern.finditer(sentence):
            if not WORDS_HEDGE_RE.search(sentence[: match.start()]):
                found.append(match.group(0))
    return found


def debt_adjustment_claims(text: str) -> list[str]:
    return _claims(DEBT_ADJUSTMENT_RE, text)


def relief_promises(text: str) -> list[str]:
    return _claims(RELIEF_RE, text)


# A monthly amount in text: "$70 a month", "$70/month", "payments of $70".
_AMOUNT = r"\$\s?(\d{1,5}(?:,\d{3})*(?:\.\d{1,2})?)"
MONTHLY_RE = re.compile(
    rf"{_AMOUNT}\s*(?:a|per|each|every)\s+month\b"
    rf"|{_AMOUNT}\s*(?:/\s*mo(?:nth)?\b|monthly\b)"
    rf"|(?:payments?|instal(?:l)?ments?)\s+of\s+{_AMOUNT}",
    re.IGNORECASE,
)
# A clause that refuses, conditions or reports someone else's figure is not an
# offer: "I can’t set up $70 a month", "the $70 you asked for".
_CLAUSE_RE = re.compile(r",|;|:|\s+but\s+|\s+and\s+|\s+-\s+|\s+—\s+")
_CLAUSE_HEDGE_RE = re.compile(
    r"\b(?:not|no|never|cannot|unable|unapproved|unauthori[sz]ed|withdrawn|superseded|old|previous|earlier"
    r"|asked|requested|mentioned|wanted|suggested|proposed|colleague|letter|instead\s+of|rather\s+than"
    r"|last|bill|if|whether|unless)\b|n['’]t\b",
    re.IGNORECASE,
)


def to_money(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value).replace(",", "").replace("$", "").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def monthly_amounts(text: str) -> list[tuple[Decimal, str]]:
    """(amount, clause) for every monthly amount the text puts forward as an option."""
    found = []
    for sentence in _SENTENCE_RE.split(text or ""):
        for clause in _CLAUSE_RE.split(sentence):
            if _CLAUSE_HEDGE_RE.search(clause):
                continue
            for match in MONTHLY_RE.finditer(clause):
                raw = next(g for g in match.groups() if g)
                amount = to_money(raw)
                if amount is not None:
                    found.append((amount, clause.strip()))
    return found


def unauthorized_amounts(text: str, authorized: set[Decimal]) -> list[str]:
    """Monthly amounts put forward in *text* that no billing-service option carries."""
    return [f"${amount} ({clause})" for amount, clause in monthly_amounts(text) if amount not in authorized]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:6].upper()


def money(value: Any) -> str:
    amount = to_money(value)
    return f"${amount:,.2f}" if amount is not None else str(value)


def day(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d.strftime('%b')} {d.year}"


def normalise_id(value: Any) -> str:
    """' bp 6120 b r1 ' -> BP-6120-B. A trailing revision (' r1') is dropped."""
    text = str(value or "").strip().upper()
    text = re.sub(r"\s+R\d+$", "", text)
    return re.sub(r"[^A-Z0-9-]", "", re.sub(r"[\s_]+", "-", text))


def option_tag(option_id: str, revision: int) -> str:
    return f"{option_id} r{revision}"


def parse_tag(tag: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    match = re.fullmatch(r"\s*(BP-\d{4}-[A-Z])\s+r(\d+)\s*", str(tag or ""), re.IGNORECASE)
    if not match:
        return None, None
    return match.group(1).upper(), int(match.group(2))


# ----------------------------------------------------------------------------
# The conversation, as the tools see it (built from tracker events)
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Conversation:
    # Text of the latest bot message stamped with CONFIRM_UTTER, and whether a
    # customer message came after it.
    confirmation_question: Optional[str] = None
    confirmation_answered: bool = False
    user_messages: tuple[str, ...] = field(default_factory=tuple)


# ----------------------------------------------------------------------------
# The billing service (one per conversation)
# ----------------------------------------------------------------------------


class BillingService:
    """Amber Grid's billing service for one conversation: accounts, budget quotes, requests and referrals."""

    def __init__(self, data: Optional[dict] = None) -> None:
        self.data = data or load_data()
        self.accounts: dict[str, dict] = self.data["accounts"]
        self.quotes: dict[str, dict] = self.data["quotes"]
        self.unauthorized: dict[str, dict] = self.data.get("unauthorized_options", {})
        self.requests: dict[str, dict] = {}  # account -> request record
        self.referrals: dict[str, dict] = {}  # "kind:account" -> referral
        self.revise_due: set[str] = set()
        self.revised: set[str] = set()

    def customer_accounts(self, customer_id: str) -> list[str]:
        return sorted(a for a, acc in self.accounts.items() if acc["customer_id"] == customer_id)

    def current_revision(self, account: str) -> int:
        """The quote revision in force now. A due re-estimate lands here, once."""
        quote = self.quotes[account]
        rule = quote.get("revise_after_first_selection")
        if rule and account in self.revise_due and account not in self.revised:
            quote["current"] = rule["to"]
            self.revised.add(account)
        return int(quote["current"])

    def revision(self, account: str, revision: int) -> Optional[dict]:
        return self.quotes[account]["revisions"].get(str(revision))

    def option_account(self, option_id: str) -> Optional[str]:
        m = re.fullmatch(r"BP-(\d{4})-[A-Z]", option_id)
        return f"AG-{m.group(1)}" if m else None


_SERVICES: dict[str, BillingService] = {}


def service_for(conversation_id: str) -> BillingService:
    """One billing service per conversation, so every scripted conversation starts from the same data."""
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = BillingService()
    return _SERVICES[conversation_id]


def caller_profile(service: BillingService, customer_id: Optional[str] = None) -> dict:
    customer_id = customer_id or SESSION_CUSTOMER_ID
    person = service.data["customers"][customer_id]
    accounts = service.customer_accounts(customer_id)
    return {
        "customer_id": customer_id,
        "first_name": person["first_name"],
        "accounts": [f"{a} {service.accounts[a]['label']}" for a in accounts],
        "account_list": "; ".join(f"{a} {service.accounts[a]['label']}" for a in accounts),
    }


# ----------------------------------------------------------------------------
# Terms, as the billing service writes them
# ----------------------------------------------------------------------------


def option_terms(service: BillingService, account: str, option_id: str, revision: int) -> Optional[dict]:
    rev = service.revision(account, revision)
    if rev is None or option_id not in rev["options"]:
        return None
    opt = rev["options"][option_id]
    budget = to_money(opt["budget_usd"])
    spread = to_money(opt.get("spread_usd") or 0)
    terms = {
        "kind": opt["kind"],
        "budget_estimate_usd": f"{budget:.2f}",
        "monthly_total_usd": f"{budget + spread:.2f}",
        "first_due": opt["first_due"],
    }
    if opt["kind"] == "budget_with_balance_spread":
        terms["balance_spread_usd"] = f"{spread:.2f}"
        terms["balance_spread_payments"] = int(opt["spread_payments"])
    return terms


def schedule_line(terms: dict) -> str:
    """The payment schedule, one short line (read back in the question; under the memory cap)."""
    first = day(terms["first_due"])
    if terms["kind"] == "budget_with_balance_spread":
        return (f"{money(terms['monthly_total_usd'])} a month from {first}: {money(terms['budget_estimate_usd'])} "
                f"estimate + {money(terms['balance_spread_usd'])} x {terms['balance_spread_payments']} toward the balance")
    return f"{money(terms['budget_estimate_usd'])} a month from {first}, the usage estimate only"


def basis_line(basis: dict) -> str:
    return f"{basis['usage']}, about {money(basis['annual_cost_usd'])}, from {basis['source']}"


def balance_line(service: BillingService, account: str, terms: dict) -> str:
    acc = service.accounts[account]
    amount = money(acc["outstanding_balance_usd"])
    if terms["kind"] == "budget_with_balance_spread":
        return f"{amount} outstanding; repaid by the {terms['balance_spread_payments']} extra payments, not reduced"
    return f"{amount} outstanding, still due {day(acc['balance_due'])}; this plan does not reduce it"


def outstanding_balance(service: BillingService, account: str) -> dict:
    acc = service.accounts[account]
    return {
        "amount_usd": f"{to_money(acc['outstanding_balance_usd']):.2f}",
        "due": acc["balance_due"],
        "status": acc["balance_status"],
        "changed_by_budget_plan": False,
    }


def option_view(service: BillingService, account: str, option_id: str, revision: int) -> dict:
    terms = option_terms(service, account, option_id, revision)
    return {
        "option_id": option_id,
        "option_tag": option_tag(option_id, revision),
        **terms,
        "schedule": schedule_line(terms),
        "balance_handling": balance_line(service, account, terms),
        "debt_adjusted": False,
    }


def memory_for(service: BillingService, account: str, option_id: str, revision: int) -> dict:
    """The five short lines the engine reads back, all written by the billing service."""
    terms = option_terms(service, account, option_id, revision)
    basis = service.revision(account, revision)["basis"]
    return {
        "plan_account": f"{account} {service.accounts[account]['label']}",
        "option_tag": option_tag(option_id, revision),
        "option_schedule": schedule_line(terms),
        "option_basis": basis_line(basis),
        "option_balance": balance_line(service, account, terms),
    }


def _clear() -> dict:
    return {key: "" for key in MEMORY_KEYS}


# ----------------------------------------------------------------------------
# Account resolution
# ----------------------------------------------------------------------------


def resolve_account(service: BillingService, customer_id: str, words: str) -> tuple[Optional[str], dict]:
    """The customer's own account from their words or its number, or a blocked result.

    Another customer's account number gets the same answer as a number that
    does not exist, so the agent cannot confirm whose it is.
    """
    text = str(words or "").strip()
    mine = service.customer_accounts(customer_id)
    number = re.search(r"\b(?:AG[-\s]?)?(\d{4})\b", text, re.IGNORECASE)
    if number:
        account = f"AG-{number.group(1)}"
        if account in mine:
            return account, {}
        return None, {
            "status": "not_found",
            "reason": "no_such_account",
            "next_step": "Say there is no account with that number on their Amber Grid login and name their own accounts.",
            "your_accounts": [f"{a} {service.accounts[a]['label']}" for a in mine],
        }
    lowered = text.lower()
    words_in = set(re.findall(r"[a-z]+", lowered))
    candidates = []
    for account in mine:
        label = service.accounts[account]["label"]
        label_words = set(label.split())
        if lowered == label or label_words <= words_in:
            return account, {}
        if words_in & label_words:
            candidates.append(account)
    if len(candidates) == 1:
        return candidates[0], {}
    return None, {
        "status": "blocked",
        "reason": "which_account",
        "next_step": "Ask which account they mean; name the candidates.",
        "candidates": [f"{a} {service.accounts[a]['label']}" for a in (candidates or mine)],
    }


def _account_summary(service: BillingService, account: str) -> dict:
    return {
        "account": account,
        "account_label": service.accounts[account]["label"],
        "outstanding_balance": outstanding_balance(service, account),
        "balance_changed": False,
        "debt_adjusted": False,
    }


def _requests_on(service: BillingService, account: str) -> int:
    return 1 if account in service.requests else 0


# ----------------------------------------------------------------------------
# Tools' logic
# ----------------------------------------------------------------------------


def get_budget_quote(service: BillingService, customer_id: str, account_words: str) -> dict:
    """The billing basis, the outstanding balance and the authorized budget options, as separate things."""
    account, blocked = resolve_account(service, customer_id, account_words)
    if account is None:
        return blocked
    revision = service.current_revision(account)
    rev = service.revision(account, revision)
    result = {
        "status": "quote",
        **_account_summary(service, account),
        "quote_revision": revision,
        "billing_basis": {**rev["basis"], "annual_cost_usd": f"{to_money(rev['basis']['annual_cost_usd']):.2f}",
                          "budget_amount_is_estimate": True},
        "options": [option_view(service, account, oid, revision) for oid in sorted(rev["options"])],
    }
    withdrawn = [option_tag(oid, int(r)) for r in service.quotes[account]["revisions"] if int(r) < revision
                 for oid in sorted(service.revision(account, int(r))["options"])]
    if withdrawn:
        result["withdrawn_options"] = withdrawn
        result["why_revised"] = service.quotes[account]["revise_after_first_selection"]["why"]
    request = service.requests.get(account)
    if request:
        result["recorded_request"] = {"request_id": request["request_id"], "reference": request["reference"],
                                      "option_tag": request["option_tag"], "state": request["state"]}
        result["next_step"] = ("A budget plan request is already recorded on this account. It cannot be changed "
                               "here; use route_billing_support for a change.")
    else:
        result["next_step"] = (
            "Explain the three things separately: the usage estimate the budget amount comes from, the outstanding "
            "balance (no option reduces or waives it), and each option's schedule exactly as given, with the "
            "option id. Then ask whether they would like to request one, review it, or speak to support."
        )
    return result


def _find_option(service: BillingService, customer_id: str, option_id: str) -> tuple[Optional[str], Optional[str]]:
    """(account, None) for an option on the customer's own account, else (None, why)."""
    oid = normalise_id(option_id)
    if oid in service.unauthorized:
        account = service.unauthorized[oid]["account"]
        return (None, "unauthorized") if service.accounts[account]["customer_id"] == customer_id else (None, "not_found")
    account = service.option_account(oid)
    if account is None or account not in service.accounts or service.accounts[account]["customer_id"] != customer_id:
        return None, "not_found"
    known = any(oid in rev["options"] for rev in service.quotes[account]["revisions"].values())
    return (account, None) if known else (None, "not_found")


def select_budget_option(service: BillingService, customer_id: str, option_id: str) -> tuple[dict, dict]:
    """(result, memory values). Selects one authorized option at the current revision for the question."""
    oid = normalise_id(option_id)
    account, why = _find_option(service, customer_id, oid)
    if why == "unauthorized":
        info = service.unauthorized[oid]
        return {
            "status": "blocked",
            "reason": "unapproved_relief",
            "option_id": oid,
            "billing_status": info["billing_status"],
            "debt_adjusted": False,
            "next_step": ("The billing service never authorized this option, so it cannot be requested. No option "
                          "waives or reduces the balance. Say so, then present the authorized options from "
                          "get_budget_quote, or offer the hardship team if none is affordable."),
        }, _clear()
    if account is None:
        return {
            "status": "not_found",
            "reason": "no_such_option",
            "option_id": oid,
            "next_step": "There is no such option on their accounts. Call get_budget_quote and present only what it returns.",
        }, _clear()
    request = service.requests.get(account)
    if request:
        return {
            "status": "blocked",
            "reason": "already_requested",
            "option_id": oid,
            "request_id": request["request_id"],
            "reference": request["reference"],
            "next_step": "A budget plan request is already recorded on this account. Offer route_billing_support for a change.",
        }, _clear()
    revision = service.current_revision(account)
    if service.quotes[account].get("revise_after_first_selection"):
        # A meter reading is on its way: it lands after the first selection.
        service.revise_due.add(account)
    memory = memory_for(service, account, oid, revision)
    return {
        "status": "selected",
        **option_view(service, account, oid, revision),
        "account": account,
        "outstanding_balance": outstanding_balance(service, account),
        "next_step": ("Call request_budget_option with this option_id now; the engine reads the schedule, the "
                      "estimate and the balance back and asks the customer."),
    }, memory


def request_facts(service: BillingService, customer_id: str, memory: dict, conversation: Conversation,
                  option_id: str) -> tuple[dict, Optional[str], Optional[int]]:
    """The contract's two request facts for *option_id*, from trusted data and events only.

    Returns (facts, account, the revision the customer was asked about).
    """
    oid = normalise_id(option_id)
    account, _ = _find_option(service, customer_id, oid)
    tag_id, tag_rev = parse_tag(memory.get("option_tag"))
    question = conversation.confirmation_question or ""
    lines = [memory.get(k) for k in ("option_tag", "option_schedule", "option_basis", "option_balance")]
    asked = None
    if account is not None and tag_id == oid and service.revision(account, tag_rev or 0) is not None:
        asked = memory_for(service, account, oid, tag_rev)
    explained = (
        asked is not None
        and all(memory.get(k) == asked[k] for k in MEMORY_KEYS)
        and all(line and line in question for line in lines)
        and conversation.confirmation_answered
    )
    current = service.current_revision(account) if account is not None else None
    authorized = (
        asked is not None
        and tag_rev == current
        and option_terms(service, account, oid, current) is not None
        and memory.get("option_schedule") == schedule_line(option_terms(service, account, oid, current))
    )
    return {"billing_basis_explained": explained, "support_option_authorized": authorized}, account, tag_rev


def request_budget_option(service: BillingService, customer_id: str, memory: dict, conversation: Conversation,
                          option_id: str, conversation_id: str) -> tuple[dict, dict]:
    """(result, memory values). Record one confirmed, authorized option; read the record back."""
    oid = normalise_id(option_id)
    account, why = _find_option(service, customer_id, oid)
    if account is not None and account in service.requests:
        request = service.requests[account]
        if request["option_id"] == oid:
            return {**_receipt(service, request), "replay": True, "effects": 0,
                    "requests_on_account": _requests_on(service, account),
                    "next_step": "Already requested; nothing was requested twice. Give the same reference."}, _clear()
        return {"status": "blocked", "reason": "already_requested", "option_id": oid, "effects": 0,
                "request_id": request["request_id"], "reference": request["reference"],
                "requests_on_account": _requests_on(service, account),
                "next_step": "A budget plan request is already recorded on this account. Offer route_billing_support."}, _clear()
    facts, account, asked_rev = request_facts(service, customer_id, memory, conversation, oid)
    if why == "unauthorized":
        # An option the billing service never authorized cannot have been read
        # back (select refuses it), so both facts are false. The lab would name
        # the first rule; the result names the one that matters to the
        # customer, and carries both facts.
        return {"status": "blocked", "reason": "unapproved_relief", "option_id": oid, "effects": 0,
                "facts": {**facts, "support_option_authorized": False}, "debt_adjusted": False,
                "billing_status": service.unauthorized[oid]["billing_status"],
                "next_step": ("Nothing was requested: the billing service never authorized this option, and no "
                              "option waives or reduces the balance. Present the authorized options from "
                              "get_budget_quote, or offer the hardship team if none is affordable.")}, _clear()
    reason = evaluate(facts, "request")
    if reason:
        result = {"status": "blocked", "reason": reason, "option_id": oid, "effects": 0, "facts": facts,
                  "debt_adjusted": False}
        if account is not None:
            result.update(_account_summary(service, account))
            result["requests_on_account"] = _requests_on(service, account)
            current = service.current_revision(account)
            if asked_rev is not None and asked_rev != current:
                result["withdrawn_option"] = option_tag(oid, asked_rev)
                result["why_revised"] = service.quotes[account]["revise_after_first_selection"]["why"]
                rev = service.revision(account, current)
                result["billing_basis"] = rev["basis"]
                result["current_options"] = [option_view(service, account, o, current) for o in sorted(rev["options"])]
        result["next_step"] = {
            "estimate_as_waiver": ("The customer was not shown this option's schedule, estimate and balance and asked "
                                   "about them. Call select_budget_option for it, then request_budget_option again so "
                                   "the engine asks them."),
            "unapproved_relief": (
                "Nothing was requested. The estimate changed after the customer was asked, so the old schedule is "
                "withdrawn. Tell them, present the current options exactly as given (new estimate, balance "
                "unchanged), and ask which they want. When they choose, call select_budget_option, then "
                "request_budget_option so the engine asks again."
                if "withdrawn_option" in result else
                "Nothing was requested: the billing service has not authorized this option. Present the authorized "
                "options from get_budget_quote, or offer the hardship team if none is affordable."
            ),
        }[reason]
        return result, _clear()
    rev = service.revision(account, asked_rev)
    terms = option_terms(service, account, oid, asked_rev)
    request_id = f"AG-BPQ-{_digest(conversation_id, account, oid, 'request')}"
    read_back = service.quotes[account].get("record_read_back", "ok") == "ok"
    record = {
        "request_id": request_id,
        "reference": f"AG-BPR-{_digest(conversation_id, request_id)}",
        "account": account,
        "option_id": oid,
        "option_tag": option_tag(oid, asked_rev),
        "schedule_terms": terms,
        "schedule": schedule_line(terms),
        "billing_basis": basis_line(rev["basis"]),
        "facts": facts,
        "state": "recorded" if read_back else "unconfirmed",
    }
    service.requests[account] = record
    result = {**_receipt(service, record), "replay": False, "effects": 1,
              "requests_on_account": _requests_on(service, account)}
    return result, _clear()


def _receipt(service: BillingService, record: dict) -> dict:
    """What a request result says: schedule and balance, separately, and whether the record is confirmed."""
    facts = dict(record["facts"], choice_or_referral_recorded=record["state"] == "recorded")
    failure = evaluate(facts, "receipt")
    out = {
        "status": "pending" if failure else "succeeded",
        "reason": failure or "verified_fixture_receipt",
        "request_id": record["request_id"],
        "reference": None if failure else record["reference"],
        "option_tag": record["option_tag"],
        **_account_summary(service, record["account"]),
        "payment_schedule": {**record["schedule_terms"], "line": record["schedule"]},
        "billing_basis": record["billing_basis"],
        "budget_amount_is_estimate": True,
        "facts": facts,
        "owner": OWNER,
    }
    out["next_step"] = (
        "The billing system has not confirmed this request. Say it is not recorded yet, call check_budget_request "
        "with this request_id, and never request it again."
        if failure else
        "The customer has been sent the reference, the schedule and the balance. Add only what they still need; "
        "never say the balance is waived, reduced or covered by the budget amount."
    )
    return out


def check_budget_request(service: BillingService, customer_id: str, reference: str) -> dict:
    """Look a request up by request id or reference; reconcile an unconfirmed one. Never requests anything."""
    text = str(reference or "").strip().upper()
    for account, record in service.requests.items():
        if text not in (record["request_id"], record["reference"]):
            continue
        if service.accounts[account]["customer_id"] != customer_id:
            break
        reconciled = record["state"] != "recorded"
        # The billing system has the record: the lookup confirms it.
        record["state"] = "recorded"
        result = _receipt(service, record)
        result.update(status="recorded", reason="found_by_request_id", effects=0, reconciled=reconciled,
                      requests_on_account=_requests_on(service, account))
        result["next_step"] = ("The billing system has the request; this is the same request, not a new one. "
                               + ("The customer has been sent the reference." if reconciled else
                                  "Give the reference, the schedule and the balance separately."))
        return result
    return {"status": "not_found", "reason": "no_request_for_reference", "reference": text[:40],
            "next_step": "No budget plan request is known under that reference on this login."}


def _preserved(service: BillingService, account: str, memory: dict) -> Optional[dict]:
    """The support request the referral keeps: a recorded request, or the option the customer was considering."""
    request = service.requests.get(account)
    if request:
        return {"request_id": request["request_id"], "reference": request["reference"],
                "option_tag": request["option_tag"], "state": "recorded; unchanged by the referral"}
    tag_id, _ = parse_tag(memory.get("option_tag"))
    if tag_id and service.option_account(tag_id) == account:
        return {"option_tag": memory["option_tag"], "schedule": memory.get("option_schedule"),
                "state": "kept with the referral; not requested"}
    return None


def route_hardship_referral(service: BillingService, customer_id: str, account_words: str, customer_words: str,
                            memory: dict, conversation_id: str) -> tuple[dict, dict]:
    """(result, memory values). Opens a hardship referral that keeps the support request; decides nothing."""
    account, blocked = resolve_account(service, customer_id, account_words)
    if account is None:
        return blocked, {}
    key = f"hardship:{account}"
    prior = service.referrals.get(key)
    replay = prior is not None
    if prior is None:
        prior = {
            "referral_reference": f"AG-HSR-{_digest(conversation_id, key)}",
            "account": account,
            "team": "hardship team",
            "referral_state": "open",
            "customer_words": str(customer_words or "")[:300],
            "support_request_preserved": _preserved(service, account, memory),
        }
        service.referrals[key] = prior
    return {
        "status": "referred",
        **prior,
        **_account_summary(service, account),
        "relief_decided": False,
        "terms_offered": None,
        "option_flow_stopped": True,
        "replay": replay,
        "reply_within": REPLY_WITHIN,
        "next_step": ("The customer has been sent the referral reference. Say the hardship team decides what support "
                      "is possible; promise no relief, no plan and no amount, and say the balance is unchanged."),
    }, _clear()


def route_billing_support(service: BillingService, customer_id: str, account_words: str, note: str,
                          memory: dict, conversation_id: str) -> tuple[dict, dict]:
    """(result, memory values). Hands a question or a review to billing support; changes nothing."""
    account, blocked = resolve_account(service, customer_id, account_words)
    if account is None:
        return blocked, {}
    key = f"support:{account}"
    prior = service.referrals.get(key)
    replay = prior is not None
    if prior is None:
        prior = {
            "support_reference": f"AG-BSR-{_digest(conversation_id, key)}",
            "account": account,
            "team": "billing support team",
            "owner": OWNER,
            "note": str(note or "")[:300],
            "support_request_preserved": _preserved(service, account, memory),
        }
        service.referrals[key] = prior
    return {"status": "routed", **prior, **_account_summary(service, account), "replay": replay,
            "reply_within": REPLY_WITHIN,
            "next_step": "The customer has been sent the support reference. Nothing about the account has changed."}, _clear()


# ----------------------------------------------------------------------------
# The receipt the tool sends itself (TOOL_SENDS_RECEIPT)
# ----------------------------------------------------------------------------


def _balance_sentence(result: dict) -> str:
    return (f"Outstanding balance: {money(result['outstanding_balance']['amount_usd'])}, unchanged by this plan; "
            "nothing has been waived or reduced.")


def customer_receipt(tool: str, result: dict) -> Optional[str]:
    """The message a tool sends the customer for an outcome they must see, or None (never on a replay)."""
    status = result.get("status")
    if result.get("replay"):
        return None
    if (tool == "request_budget_option" and status == "succeeded") or (
            tool == "check_budget_request" and status == "recorded" and result.get("reconciled")):
        return (f"Budget plan request recorded: {result['reference']} for account {result['account']} "
                f"({result['account_label']}), option {result['option_tag']}. Payment schedule: "
                f"{result['payment_schedule']['line']}. {_balance_sentence(result)} The budget amount is an "
                f"estimate ({result['billing_basis']}) and is reviewed against actual meter reads.")
    if tool == "request_budget_option" and status == "pending":
        return (f"Not recorded yet: the billing system has not confirmed budget plan request {result['request_id']} "
                f"for account {result['account']}. It will not be sent twice. "
                f"Outstanding balance: {money(result['outstanding_balance']['amount_usd'])}, unchanged.")
    if tool == "route_hardship_referral" and status == "referred":
        kept = result.get("support_request_preserved") or {}
        if kept.get("reference"):
            keep = f" Your budget plan request {kept['reference']} stays as recorded."
        elif kept.get("option_tag"):
            keep = f" The option you were considering ({kept['option_tag']}) goes with the referral; it was not requested."
        else:
            keep = ""
        return (f"Referred to the Amber Grid hardship team: {result['referral_reference']}, for account "
                f"{result['account']}.{keep} Outstanding balance: "
                f"{money(result['outstanding_balance']['amount_usd'])}, unchanged. The team decides what support is "
                f"possible and replies within {result['reply_within']}; nothing has been agreed yet.")
    if tool == "route_billing_support" and status == "routed":
        return (f"Passed to Amber Grid billing support: {result['support_reference']}, for account "
                f"{result['account']}. They reply within {result['reply_within']}. Nothing on the account has "
                f"changed; the outstanding balance is {money(result['outstanding_balance']['amount_usd'])}.")
    return None


def memory_values_fit(values: dict) -> bool:
    return all(len(str(v)) <= MEMORY_VALUE_LIMIT for v in values.values())
