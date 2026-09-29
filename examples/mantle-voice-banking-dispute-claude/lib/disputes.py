"""Northgate Bank dispute intake and its guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three rules of the casebook contract for ``banking-dispute``
(vendored as ``lib/fixtures/case-contract.json``):

- ``transaction_selected`` (request): the dispute names exactly one
  transaction on the verified caller's own cards, the one
  ``select_transaction`` resolved. An unverified call owns nothing, and a
  description that matches none or several transactions selects nothing.
- ``customer_statement_confirmed`` (request): the caller's statement is
  recorded for the transaction the engine's confirmation gate read back to
  them, and it is not empty. The gate (``requires_confirmation`` in
  ``skill.md``) asks the contract's question; this module checks the filing
  names that same transaction and carries a statement.
- ``case_reference_recorded`` (receipt): after filing, the case service
  reads the case back by its submission key. When it cannot, the result is
  ``pending`` with the submission key, never ``succeeded``.

A receipt is a dispute reference and the next review step. It never carries
a reimbursement outcome: ``reimbursement_decision`` and
``provisional_credit`` are always ``None``, because a dispute receipt is not
a finding of fraud. Blocking a card is a separate request with its own
reference, and it does not touch the dispute.

Facts are computed here from trusted data and session state. The model
supplies a name, a date of birth, a description of the charge, a transaction
reference copied from a tool result and the caller's statement. It never
supplies a fact, a customer id or an outcome. A fact that is not exactly
``True`` fails its rule, as in the lab's ``evaluate``.

Ledger and case state live in an in-process service with one copy of the
fixture per conversation, so every scripted call starts from the same data.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "northgate_disputes.json"

# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))

NEXT_REVIEW_STEP = (
    "The disputes team reviews the case and contacts the caller within 10 business days. "
    "No refund or credit has been decided."
)
_SPACE_RE = re.compile(r"\s+")
_NAME_DROP_RE = re.compile(r"[^a-z\s'-]")
_WORD_RE = re.compile(r"[a-z0-9]+")
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]


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
    """'7319' -> '7 3 1 9', so text-to-speech reads a card ending digit by digit."""
    return " ".join(digits)


def spoken_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {_MONTHS[d.month - 1]}"


def spoken_amount(amount: float) -> str:
    whole = int(round(amount))
    return f"{whole:,} rupees"


def normalise_name(value: Any) -> str:
    text = _NAME_DROP_RE.sub("", str(value or "").lower())
    return _SPACE_RE.sub(" ", text).strip()


def normalise_last_four(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def parse_amount(value: Any) -> Optional[float]:
    """'2,499', '2499.00', 'Rs 2499' or 2499 -> 2499.0; None when there is no number."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(value))
    return float(match.group(0).replace(",", "")) if match else None


def parse_date(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def merchant_words(value: Any) -> set[str]:
    return set(_WORD_RE.findall(str(value or "").lower()))


def _compact(value: Any) -> str:
    return "".join(_WORD_RE.findall(str(value or "").lower()))


def merchant_matches(spoken: Any, merchant: str) -> bool:
    """Every word the caller gave appears in the merchant name, or the reverse.

    Word boundaries are also ignored, because speech-to-text splits and joins
    brand names ("Brightmart" came back as "Bright Mart" live): the spoken
    name with its spaces removed may appear inside the merchant's, or the
    reverse, if it is at least six characters long.
    """
    said, name = merchant_words(spoken), merchant_words(merchant)
    if not said:
        return False
    if said <= name or name <= said:
        return True
    said_c, name_c = _compact(spoken), _compact(merchant)
    return len(said_c) >= 6 and (said_c in name_c or name_c in said_c)


class LedgerService:
    """The card ledger and dispute case service for one conversation (fixture copy)."""

    def __init__(self, data: Optional[dict] = None) -> None:
        data = data or load_data()
        self.customers: dict[str, dict] = data["customers"]
        self.cards: dict[str, dict] = data["cards"]
        self.transactions: dict[str, dict] = data["transactions"]
        # submission_key -> case record, as the case service stores it.
        self.cases: dict[str, dict] = {}
        self.card_blocks: list[dict] = []

    def owner_of(self, txn_ref: str) -> Optional[str]:
        txn = self.transactions.get(txn_ref)
        card = self.cards.get(txn["card_ref"]) if txn else None
        return card["customer_id"] if card else None

    def transactions_of(self, customer_id: Optional[str]) -> dict[str, dict]:
        return {
            ref: t for ref, t in sorted(self.transactions.items())
            if customer_id and self.owner_of(ref) == customer_id
        }

    def label(self, txn_ref: str) -> str:
        txn = self.transactions[txn_ref]
        card = self.cards[txn["card_ref"]]
        return (f"charge of {spoken_amount(txn['amount'])} from {txn['merchant']} on "
                f"{spoken_date(txn['date'])}, on your {card['kind']} card ending "
                f"{spoken_digits(card['last_four'])}")

    def read_back(self, submission_key: str) -> Optional[dict]:
        """The case as the service reports it, or None when it cannot confirm one."""
        case = self.cases.get(submission_key)
        if case is None or case["read_back"] != "ok":
            return None
        return case


_SERVICES: dict[str, LedgerService] = {}


def service_for(conversation_id: str) -> LedgerService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = LedgerService()
    return _SERVICES[conversation_id]


def submission_key(conversation_id: str, txn_ref: str) -> str:
    """One key per call and transaction, so a retried filing is a replay, not a second case."""
    return f"NB-SUB-{_digest(conversation_id, txn_ref)}"


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------


def verify_caller(service: LedgerService, full_name: str, date_of_birth: str) -> dict:
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
                "next_step": "Ask which charge the caller does not recognise, if they have not said.",
            }
    return {
        "status": "not_verified",
        "reason": "identity_mismatch",
        "next_step": (
            "Say the details did not match and ask the caller to repeat their full "
            "name and date of birth. Do not look up or dispute any transaction."
        ),
    }


def _blocked(reason: str, **extra: Any) -> dict:
    next_step = {
        "transaction_ambiguous": (
            "The description does not pick out exactly one of the caller's transactions. "
            "If there are candidates, read them by amount, merchant and date and ask which "
            "one. If there are none, ask the caller to check the merchant, amount and date. "
            "Never say whether a transaction belongs to someone else. Do not file anything."
        ),
        "statement_not_confirmed": (
            "The caller's statement is not recorded for this transaction. Ask the caller "
            "what happened with this charge, in their words, before filing."
        ),
    }[reason]
    return {"status": "blocked", "reason": reason, "effects": 0, **extra, "next_step": next_step}


def select_transaction(
    service: LedgerService,
    customer_id: Optional[str],
    merchant: Optional[str] = None,
    amount: Any = None,
    transaction_date: Optional[str] = None,
    card_last_four: Optional[str] = None,
) -> dict:
    """Resolve a spoken description to exactly one of the verified caller's transactions."""
    wanted_amount = parse_amount(amount)
    wanted_date = parse_date(transaction_date)
    ending = normalise_last_four(card_last_four)
    described = {
        k: v for k, v in (("merchant", merchant), ("amount", wanted_amount), ("date", wanted_date),
                          ("card_last_four", ending)) if v not in (None, "")
    }
    if not customer_id:
        return _blocked("transaction_ambiguous", caller_verified=False, matches=0, described=described)
    if not (str(merchant or "").strip() or wanted_amount is not None):
        return _blocked("transaction_ambiguous", caller_verified=True, matches=0, described=described)
    matches = []
    for ref, txn in service.transactions_of(customer_id).items():
        card = service.cards[txn["card_ref"]]
        if str(merchant or "").strip() and not merchant_matches(merchant, txn["merchant"]):
            continue
        if wanted_amount is not None and abs(txn["amount"] - wanted_amount) >= 0.5:
            continue
        if wanted_date is not None and txn["date"] != wanted_date:
            continue
        if ending and card["last_four"] != ending:
            continue
        matches.append(ref)
    if len(matches) != 1:
        # None and several both select nothing. Someone else's transaction and
        # one that does not exist get the same answer.
        return _blocked(
            "transaction_ambiguous",
            caller_verified=True,
            matches=len(matches),
            described=described,
            candidates=[service.label(ref) for ref in matches],
        )
    ref = matches[0]
    return {
        "status": "selected",
        "transaction_ref": ref,
        "transaction_label": service.label(ref),
        "next_step": (
            "Call file_dispute with this transaction_ref and the caller's statement. The "
            "engine reads the transaction back and asks the caller to confirm before "
            "anything is filed."
        ),
    }


def file_dispute(
    service: LedgerService,
    customer_id: Optional[str],
    selected_txn_ref: Optional[str],
    txn_ref: str,
    customer_statement: str,
    conversation_id: str,
) -> dict:
    """File one dispute for the confirmed transaction and prove it by reading the case back."""
    ref = str(txn_ref or "").strip().upper()
    statement = " ".join(str(customer_statement or "").split())[:300]
    owned = bool(customer_id) and service.owner_of(ref) == customer_id
    facts = {
        "transaction_selected": owned and bool(selected_txn_ref) and ref == selected_txn_ref,
        "customer_statement_confirmed": owned and ref == selected_txn_ref and bool(statement),
    }
    reason = evaluate(facts, "request")
    if reason:
        return _blocked(reason, transaction_ref=ref, facts=facts)

    key = submission_key(conversation_id, ref)
    replay = key in service.cases
    if not replay:
        txn = service.transactions[ref]
        service.cases[key] = {
            "submission_key": key,
            "dispute_reference": f"NB-DSP-{_digest(key, 'case')}",
            "transaction_ref": ref,
            "customer_statement": statement,
            # ack_lost: the case service records it but the filing response
            # never arrives; unavailable: nothing can be confirmed either way.
            "read_back": "ok" if txn["case_service"] == "ok" else "failed",
            "lookup": {"ok": "ok", "ack_lost": "ok", "unavailable": "unknown"}[txn["case_service"]],
        }
    case = service.read_back(key)
    facts["case_reference_recorded"] = case is not None
    receipt_failure = evaluate(facts, "receipt")
    result = {
        "status": "pending" if receipt_failure else "succeeded",
        "reason": receipt_failure or "verified_fixture_receipt",
        "transaction_ref": ref,
        "transaction_label": service.label(ref),
        "submission_key": key,
        "dispute_reference": case["dispute_reference"] if case else None,
        "customer_statement": statement,
        "next_review_step": NEXT_REVIEW_STEP if case else None,
        "reimbursement_decision": None,
        "provisional_credit": None,
        "card_blocked": False,
        "effects": 0 if replay else 1,
        "replay": replay,
        "facts": facts,
    }
    if receipt_failure:
        result["next_step"] = (
            "The case service did not confirm the case. Say the dispute is not confirmed "
            "yet, call check_dispute_status with this submission_key, and if it is still "
            "unknown call route_disputes_desk. Do not file again and do not promise any "
            "refund or credit."
        )
    else:
        result["next_step"] = (
            "Give the dispute reference and the next review step. Say no refund or credit "
            "has been decided; the disputes team decides after review."
        )
    return result


def check_dispute_status(service: LedgerService, customer_id: Optional[str], key: str) -> dict:
    """Look a filing up by its original submission key. Never files anything."""
    key = str(key or "").strip().upper()
    case = service.cases.get(key)
    if case is None or not customer_id or service.owner_of(case["transaction_ref"]) != customer_id:
        return {"status": "unknown", "reason": "no_record_for_submission_key", "submission_key": key,
                "next_step": "No filing is known under this key. Call route_disputes_desk."}
    if case["lookup"] != "ok":
        return {
            "status": "unknown",
            "reason": "case_service_unavailable",
            "submission_key": key,
            "next_step": (
                "The case service cannot give a definite state. Call route_disputes_desk and "
                "say the dispute is pending. Do not file again."
            ),
        }
    return {
        "status": "recorded",
        "reason": "found_by_submission_key",
        "submission_key": key,
        "transaction_ref": case["transaction_ref"],
        "dispute_reference": case["dispute_reference"],
        "next_review_step": NEXT_REVIEW_STEP,
        "reimbursement_decision": None,
        "next_step": "Give the dispute reference and the next review step. No refund has been decided.",
    }


def route_disputes_desk(service: LedgerService, customer_id: Optional[str], key: str, reason: str) -> dict:
    key = str(key or "").strip().upper()
    case = service.cases.get(key)
    if case is None or not customer_id or service.owner_of(case["transaction_ref"]) != customer_id:
        return {"status": "refused", "reason": "no_record_for_submission_key", "submission_key": key,
                "next_step": "Route only a filing this call made, by its submission key."}
    return {
        "status": "routed",
        "dispute_status": "pending",
        "submission_key": key,
        "desk_reference": f"NB-DSK-{_digest(customer_id, key, 'desk')}",
        "route": "disputes case owner",
        "reason": " ".join(str(reason or "").split())[:200],
        "reimbursement_decision": None,
        "next_step": (
            "Say the dispute is pending, give the desk reference, and say the disputes case "
            "owner will confirm it within one business day."
        ),
    }


def request_card_block(service: LedgerService, customer_id: Optional[str], card_last_four: str,
                       conversation_id: str) -> dict:
    """Card containment: a separate request with its own reference. It never changes a dispute."""
    ending = normalise_last_four(card_last_four)
    owned = [
        (ref, c) for ref, c in sorted(service.cards.items())
        if customer_id and c["customer_id"] == customer_id and c["last_four"] == ending
    ]
    if len(owned) != 1:
        return {"status": "blocked", "reason": "card_not_owned", "card_last_four": ending, "effects": 0,
                "next_step": "Say you cannot find that card for this caller. Never say whose it is."}
    ref, card = owned[0]
    replay = card["state"] == "blocked"
    card["state"] = "blocked"
    block = {"card_ref": ref, "reference": f"NB-BLK-{_digest(conversation_id, ref)}"}
    if not replay:
        service.card_blocks.append(block)
    return {
        "status": "succeeded",
        **block,
        "card_label": f"{card['kind']} card ending {spoken_digits(card['last_four'])}",
        "effects": 0 if replay else 1,
        "replay": replay,
        "dispute_changed": False,
        "next_step": (
            "Give the card block reference. Say it is separate from the dispute reference "
            "and does not decide the dispute."
        ),
    }
