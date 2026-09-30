"""Northgate Bank transfers and the ledger guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the three request-phase rules of the casebook contract for
``banking-transfer`` (vendored as ``lib/fixtures/case-contract.json``), at the
moment of submission, from the ledger's own state:

- ``ledger_revision_current``: the account's ledger revision now is the
  revision the draft was prepared (and shown to the caller) against. Any
  debit, hold or transfer in between moves the revision, so a balance read
  before another debit can never fund a transfer.
- ``payee_identity_confirmed``: the draft's destination is the saved payee
  (or own account) that ``select_payee`` resolved from the caller's words,
  owned by the signed-in customer, and still the current selection. The
  model never supplies a payee identity; it copies a ``payee_ref`` from a
  tool result, and a spoken name that matches several payees selects none.
- ``funds_reserved``: the ledger placed a reservation for the amount against
  the available balance (posted minus holds) at submission time.

The receipt is a ledger transfer reference with an explicit ``pending`` or
``posted`` status. A submission is never reported as posted unless the ledger
posted it: transfers between the customer's own accounts post at once;
transfers to a saved payee stay pending until the payment scheme settles. When
the submission's outcome is not known (a lost acknowledgement, a scheme that
does not answer) the result is ``unconfirmed`` and the recovery is a lookup,
then reconciliation, never a second transfer.

The model supplies an account name, the caller's words for a payee, a
``payee_ref`` and ``draft_id`` copied from tool results, an amount, and a
reference to look up. It never supplies a fact, a customer id, a balance or
an outcome. A fact that is not exactly ``True`` fails its rule, as in the
lab's ``evaluate``.

Ledger state lives in an in-process service with one copy of the fixture per
conversation, so every scripted conversation starts from the same balances.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "northgate_ledger.json"

# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))

DEMO_CUSTOMER_ID = "NB-CUST-4810"
CENT = Decimal("0.01")

RECEIPT_NOTE = (
    "A submission receipt is not a posting. Say a transfer is posted, complete or "
    "received only when ledger_status is posted."
)

# ----------------------------------------------------------------------------
# Wording that says or implies money has moved: the case metric ("transfers
# promised as posted without a posted ledger entry") and the output guard in
# hooks.py. The harness counts the same patterns in bot turns;
# tests/test_guard.py keeps the copies identical.
# ----------------------------------------------------------------------------

POSTED_CLAIM_RE = re.compile(
    r"\b(?:(?:has|have|had)\s+(?:now\s+|already\s+|successfully\s+)?(?:been\s+)?"
    r"(?:posted|completed|cleared|settled|arrived|landed|gone through|went through|credited|deposited)"
    r"|(?:is|are|was|were)\s+(?:now\s+|already\s+|successfully\s+)?"
    r"(?:posted|complete|completed|cleared|settled|done|credited|deposited|in (?:his|her|their|the) account)"
    r"|(?:it|the transfer|the money|the payment|the funds)(?:'s| is| are)\s+(?:now\s+)?(?:there|through)"
    r"|(?:went|gone) through"
    r"|(?:has|have|got|received)\s+(?:it|the money|the funds|the payment|the transfer)\s+(?:now|already)"
    r"|(?:I|I've|I have|we've|we have)\s+(?:successfully\s+)?(?:sent|transferred|moved|paid)\b(?!\s+(?:a|the|your)\s+(?:request|submission))"
    r")",
    re.IGNORECASE,
)
# A match is not a claim when the same sentence negates or hedges it before the
# match: "it has not posted yet", "once it has posted", "pending until it clears".
POSTED_HEDGE_RE = re.compile(
    r"\b(?:not|never|no|yet|pending|until|once|when|after|if|whether|unless|cannot|can't|unable|only)\b|n't\b",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def posted_claims(text: str) -> list[str]:
    """Phrases in *text* that say or imply the money has moved, sentence by sentence."""
    found = []
    for sentence in _SENTENCE_RE.split(text or ""):
        if sentence.rstrip().endswith("?"):
            continue  # a question claims nothing
        for match in POSTED_CLAIM_RE.finditer(sentence):
            if not POSTED_HEDGE_RE.search(sentence[: match.start()]):
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
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8].upper()


def money(value: Decimal) -> str:
    return f"${value.quantize(CENT):,.2f}"


def parse_amount(value: Any) -> Optional[Decimal]:
    """'$1,500' -> Decimal('1500.00'). None unless it is a positive amount in cents."""
    text = re.sub(r"(?i)usd|dollars?|[\s$,]", "", str(value or ""))
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount <= 0 or amount != amount.quantize(CENT):
        return None
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


_WORD_RE = re.compile(r"[a-z]+")
_DIGITS_RE = re.compile(r"\d+")


def _words(value: Any) -> list[str]:
    return _WORD_RE.findall(str(value or "").lower().replace("-", " "))


def _phrase(value: Any) -> str:
    return " ".join(_words(value))


def _contains(phrase: str, words: str) -> bool:
    return bool(words) and re.search(rf"\b{re.escape(words)}\b", phrase) is not None


def normalise_ref(value: Any) -> str:
    return re.sub(r"[^A-Z0-9-]", "", str(value or "").strip().upper())


# ----------------------------------------------------------------------------
# The ledger for one conversation
# ----------------------------------------------------------------------------


class Ledger:
    """Accounts, saved payees and the transfer ledger for one conversation (fixture copy)."""

    def __init__(self, data: Optional[dict] = None) -> None:
        data = data or load_data()
        self.as_of: str = data["as_of"]
        self.customers: dict = data["customers"]
        self.accounts: dict[str, dict] = data["accounts"]
        self.payees: dict[str, dict] = data["payees"]
        # reference -> transfer record, the ledger's own entries.
        self.transfers: dict[str, dict] = data["transfers"]
        for account in self.accounts.values():
            account["posted_balance"] = Decimal(account["posted_balance"])
            for hold in account["holds"]:
                hold["amount"] = Decimal(hold["amount"])
            account["reads"] = 0
        for transfer in self.transfers.values():
            transfer["amount"] = Decimal(transfer["amount"])
            transfer.setdefault("attempt_id", None)
        # draft_id -> draft; drafts are this module's bookkeeping, not ledger entries.
        self.drafts: dict[str, dict] = {}
        self.draft_seq = 0

    # -- reads -----------------------------------------------------------------

    def available(self, account_ref: str) -> Decimal:
        account = self.accounts[account_ref]
        return account["posted_balance"] - sum((h["amount"] for h in account["holds"]), Decimal("0"))

    def snapshot(self, account_ref: str) -> dict:
        account = self.accounts[account_ref]
        return {
            "account_ref": account_ref,
            "account": account_label(account),
            "posted_balance": money(account["posted_balance"]),
            "available_balance": money(self.available(account_ref)),
            "holds_total": money(sum((h["amount"] for h in account["holds"]), Decimal("0"))),
            "ledger_revision": account["revision"],
            "observed_at": self.as_of,
        }

    def read(self, account_ref: str) -> dict:
        """One ledger read. A debit scheduled to post after the first read posts right after it."""
        snap = self.snapshot(account_ref)
        account = self.accounts[account_ref]
        account["reads"] += 1
        if account["reads"] == 1:
            for debit in account["scheduled_debits"]:
                if debit.get("posts") == "after_first_read" and not debit.get("posted"):
                    account["posted_balance"] -= Decimal(debit["amount"])
                    account["revision"] += 1
                    debit["posted"] = True
        return snap

    # -- lookups ---------------------------------------------------------------

    def accounts_of(self, customer_id: Optional[str]) -> dict[str, dict]:
        return {r: a for r, a in sorted(self.accounts.items()) if customer_id and a["customer_id"] == customer_id}

    def payees_of(self, customer_id: Optional[str]) -> dict[str, dict]:
        return {r: p for r, p in sorted(self.payees.items()) if customer_id and p["customer_id"] == customer_id}

    def destination(self, customer_id: Optional[str], ref: str) -> Optional[dict]:
        """A saved payee or own account of this customer, or None."""
        ref = normalise_ref(ref)
        if ref in self.payees_of(customer_id):
            return {"kind": "saved_payee", "ref": ref, **self.payees[ref]}
        if ref in self.accounts_of(customer_id):
            return {"kind": "own_account", "ref": ref, **self.accounts[ref]}
        return None

    def find_transfer(self, customer_id: Optional[str], key: str) -> Optional[tuple[str, dict]]:
        """By ledger reference or by the attempt (draft) id; this customer's entries only."""
        key = normalise_ref(key)
        for reference, transfer in self.transfers.items():
            if transfer["customer_id"] != customer_id:
                continue
            if key in (reference, transfer.get("attempt_id")):
                return reference, transfer
        return None


_LEDGERS: dict[str, Ledger] = {}


def ledger_for(conversation_id: str) -> Ledger:
    if conversation_id not in _LEDGERS:
        _LEDGERS[conversation_id] = Ledger()
    return _LEDGERS[conversation_id]


def account_label(account: dict) -> str:
    return f"{account['name']} (account ending {account['last_four']})"


def destination_label(dest: dict) -> str:
    if dest["kind"] == "own_account":
        return f"your {account_label(dest)}"
    return f"{dest['name']}, saved payee at {dest['bank']}, account ending {dest['account_last_two']}"


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------


def caller_profile(customer_id: str = DEMO_CUSTOMER_ID, ledger: Optional[Ledger] = None) -> dict:
    ledger = ledger or Ledger()
    person = ledger.customers[customer_id]
    return {
        "customer_id": customer_id,
        "first_name": person["first_name"],
        "accounts": [account_label(a) for a in ledger.accounts_of(customer_id).values()],
    }


def resolve_account(ledger: Ledger, customer_id: Optional[str], spoken: Any) -> dict:
    """The one account of this customer the caller named, by name, alias or last four digits."""
    owned = ledger.accounts_of(customer_id)
    phrase = _phrase(spoken)
    digits = set(_DIGITS_RE.findall(str(spoken or "")))
    by_digits = [r for r, a in owned.items() if a["last_four"] in digits]
    by_name = [r for r, a in owned.items() if _contains(phrase, _phrase(a["name"]))]
    if not by_name:
        by_name = [r for r, a in owned.items() if any(_contains(phrase, al) for al in a["aliases"])]
    if not by_name and _contains(phrase, "checking"):
        by_name = [r for r, a in owned.items() if "checking" in _phrase(a["name"])]
    matches = [r for r in by_digits if not by_name or r in by_name] if by_digits else by_name
    if len(matches) == 1:
        return {"status": "resolved", "account_ref": matches[0], "account": account_label(owned[matches[0]])}
    return {
        "status": "blocked",
        "reason": "account_not_resolved",
        "detail": "ambiguous" if len(matches) > 1 else "not_found",
        "candidates": [account_label(owned[r]) for r in (matches if len(matches) > 1 else owned)],
        "effects": 0,
        "next_step": "Ask which of the caller's accounts they mean, by name. Do not guess.",
    }


def get_balance(ledger: Ledger, customer_id: Optional[str], account: Any) -> dict:
    resolved = resolve_account(ledger, customer_id, account)
    if resolved["status"] != "resolved":
        return resolved
    snap = ledger.read(resolved["account_ref"])
    return {
        "status": "read",
        **snap,
        "note": (
            "A balance read at this ledger revision. It is not a reservation and it can change "
            "before a transfer is submitted: the ledger decides at submission."
        ),
    }


def _payee_blocked(detail: str, **extra: Any) -> dict:
    next_step = {
        "ambiguous": (
            "Several saved payees match what the caller said. Read the candidates by name and "
            "account ending and ask which one. Do not choose for the caller."
        ),
        "not_a_saved_payee": (
            "No saved payee or own account matches. Transfers here go only to saved payees or the "
            "caller's own accounts; a new payee is added in the Northgate app. Do not transfer to "
            "an account number given in chat."
        ),
        "name_and_ending_disagree": (
            "The name and the account ending the caller gave belong to different payees. Read "
            "back both and ask which one they mean."
        ),
        "not_the_selected_payee": (
            "This payee_ref is not the payee select_payee resolved for the caller. Call "
            "select_payee with the caller's words and use only the payee_ref it returns."
        ),
    }[detail]
    return {"status": "blocked", "reason": "unconfirmed_payee", "detail": detail, "effects": 0, **extra,
            "next_step": next_step}


def select_payee(ledger: Ledger, customer_id: Optional[str], spoken: Any) -> dict:
    """Resolve the caller's words (a name, a nickname, an ending) to one saved payee or own account.

    Someone else's payee and a payee that does not exist give the same answer.
    """
    options: dict[str, dict] = {}
    for ref in ledger.payees_of(customer_id):
        options[ref] = ledger.destination(customer_id, ref)
    for ref in ledger.accounts_of(customer_id):
        options[ref] = ledger.destination(customer_id, ref)
    phrase = _phrase(spoken)
    digits = set(_DIGITS_RE.findall(str(spoken or "")))
    by_digits = [
        r for r, d in options.items()
        if (d["kind"] == "saved_payee" and d["account_last_two"] in digits)
        or (d["kind"] == "own_account" and d["last_four"] in digits)
    ]
    strong = [r for r, d in options.items() if _contains(phrase, _phrase(d["name"]))]
    weak = [
        r for r, d in options.items()
        if any(_contains(phrase, alias) for alias in d["aliases"])
        or (d["kind"] == "saved_payee" and any(_contains(phrase, w) for w in _words(d["name"]) if len(w) >= 3))
    ]
    by_name = strong or weak
    if by_digits and by_name:
        matches = [r for r in by_name if r in by_digits]
        if not matches:
            return _payee_blocked(
                "name_and_ending_disagree",
                candidates=[destination_label(options[r]) for r in sorted(set(by_digits) | set(by_name))],
            )
    else:
        matches = by_digits or by_name
    if len(matches) > 1:
        return _payee_blocked("ambiguous", candidates=[destination_label(options[r]) for r in matches])
    if not matches:
        return _payee_blocked("not_a_saved_payee")
    ref = matches[0]
    dest = options[ref]
    return {
        "status": "selected",
        "payee_ref": ref,
        "payee_label": destination_label(dest),
        "destination_kind": dest["kind"],
        "next_step": (
            "Call prepare_transfer with this payee_ref, the source account and the amount. "
            "Do not describe the payee as confirmed: the caller confirms the whole transfer next."
        ),
    }


def _unresolved_attempt(ledger: Ledger, customer_id: str, from_ref: str, payee_ref: str,
                        amount: Decimal) -> Optional[tuple[str, dict]]:
    for reference, transfer in ledger.transfers.items():
        if (transfer["customer_id"] == customer_id and transfer.get("attempt_id")
                and transfer["from_account"] == from_ref and transfer["payee_ref"] == payee_ref
                and transfer["amount"] == amount and transfer["ledger_status"] != "posted"):
            return reference, transfer
    return None


def prepare_transfer(
    ledger: Ledger,
    customer_id: Optional[str],
    selected_payee_ref: Optional[str],
    from_account: Any,
    payee_ref: Any,
    amount: Any,
    conversation_id: str,
) -> dict:
    """Read the source account and draft one transfer for the caller to confirm. Moves no money."""
    source = resolve_account(ledger, customer_id, from_account)
    if source["status"] != "resolved":
        return source
    from_ref = source["account_ref"]
    ref = normalise_ref(payee_ref)
    dest = ledger.destination(customer_id, ref)
    if dest is None or not selected_payee_ref or ref != selected_payee_ref:
        # Unknown, another customer's and an unselected payee look the same.
        return _payee_blocked("not_the_selected_payee", payee_ref=ref)
    if ref == from_ref:
        return {"status": "blocked", "reason": "same_account", "effects": 0,
                "next_step": "The source and destination are the same account. Ask the caller which account to send from."}
    value = parse_amount(amount)
    if value is None:
        return {"status": "blocked", "reason": "invalid_amount", "amount": str(amount), "effects": 0,
                "next_step": "Ask the caller for the amount in dollars and cents."}
    prior = _unresolved_attempt(ledger, customer_id, from_ref, ref, value)
    if prior:
        reference, transfer = prior
        return {
            "status": "blocked",
            "reason": "prior_attempt_unresolved",
            "prior_attempt_id": transfer["attempt_id"],
            "prior_reference": reference if transfer.get("reference_returned", True) else None,
            "prior_ledger_status": transfer["ledger_status"] if transfer.get("reference_returned", True) else "unknown",
            "effects": 0,
            "next_step": (
                "A transfer of this amount to this payee from this account was already submitted in this "
                "conversation and has not posted. Do not submit it again. Call check_transfer_status with "
                "prior_attempt_id; if the result is still unknown, call escalate_reconciliation."
            ),
        }
    snap = ledger.read(from_ref)
    ledger.draft_seq += 1
    draft_id = f"NB-DRF-{_digest(conversation_id, ledger.draft_seq, from_ref, ref, value)}"
    summary = f"{money(value)} from your {account_label(ledger.accounts[from_ref])} to {destination_label(dest)}"
    ledger.drafts[draft_id] = {
        "draft_id": draft_id,
        "customer_id": customer_id,
        "from_account": from_ref,
        "payee_ref": ref,
        "amount": value,
        "revision": snap["ledger_revision"],
        "summary": summary,
        "state": "open",
    }
    return {
        "status": "drafted",
        "draft_id": draft_id,
        "summary": summary,
        "amount": money(value),
        "from_account_ref": from_ref,
        "payee_ref": ref,
        "from_account": source["account"],
        "destination": destination_label(dest),
        "destination_kind": dest["kind"],
        "balance_as_read": {k: snap[k] for k in ("available_balance", "posted_balance", "ledger_revision", "observed_at")},
        "effects": 0,
        "next_step": (
            "Call submit_transfer with this draft_id. The engine shows the caller the amount, source and "
            "destination and asks them to confirm. The balance above is a read, not a decision: the "
            "ledger decides at submission. Do not tell the caller the transfer will go through."
        ),
    }


def _blocked_submit(reason: str, draft: dict, facts: dict, ledger: Ledger) -> dict:
    snap = ledger.snapshot(draft["from_account"])
    next_step = {
        "stale_balance": (
            "The account's ledger changed after the balance was read (another debit or hold posted), so "
            "nothing was submitted. Tell the caller, give the current available balance, and if they still "
            "want a transfer call prepare_transfer again; the new draft needs a new confirmation."
        ),
        "unconfirmed_payee": (
            "The destination is not the payee currently selected for the caller. Nothing was submitted. "
            "Call select_payee with the caller's words, then prepare_transfer again."
        ),
        "funds_not_reserved": (
            "The ledger could not reserve the amount against the available balance, so nothing was "
            "submitted. Tell the caller the current available balance. Do not promise the transfer."
        ),
    }[reason]
    draft["state"] = "void"
    return {
        "status": "blocked",
        "reason": reason,
        "draft_id": draft["draft_id"],
        "amount": money(draft["amount"]),
        "from_account_ref": draft["from_account"],
        "payee_ref": draft["payee_ref"],
        "prepared_at_revision": draft["revision"],
        "current": {k: snap[k] for k in ("available_balance", "posted_balance", "ledger_revision")},
        "facts": facts,
        "effects": 0,
        "next_step": next_step,
    }


def submit_transfer(
    ledger: Ledger,
    customer_id: Optional[str],
    selected_payee_ref: Optional[str],
    current_draft_id: Optional[str],
    draft_id: Any,
    conversation_id: str,
) -> dict:
    """Submit one confirmed draft. The ledger decides here, from its own state."""
    key = normalise_ref(draft_id)
    draft = ledger.drafts.get(key)
    if draft is None or draft["customer_id"] != customer_id:
        return {"status": "blocked", "reason": "unknown_draft", "draft_id": key, "effects": 0,
                "next_step": "Call prepare_transfer and submit only the draft_id it returns."}
    existing = ledger.find_transfer(customer_id, key)
    if existing:
        reference, transfer = existing
        return {**_receipt(ledger, reference, transfer), "effects": 0, "replay": True}
    if draft["state"] == "void" or key != current_draft_id:
        return {"status": "blocked", "reason": "draft_superseded", "draft_id": key, "effects": 0,
                "next_step": (
                    "This draft is no longer the one the caller is confirming (it was replaced or refused). "
                    "Call prepare_transfer again with the caller's current request."
                )}

    account = ledger.accounts[draft["from_account"]]
    dest = ledger.destination(customer_id, draft["payee_ref"])
    facts = {
        "ledger_revision_current": account["revision"] == draft["revision"],
        "payee_identity_confirmed": (
            dest is not None and bool(selected_payee_ref) and draft["payee_ref"] == selected_payee_ref
        ),
    }
    if all(value is True for value in facts.values()):
        # The reservation is the ledger's decision: available balance now, not
        # as read. It is attempted only for a current draft to a confirmed payee.
        facts["funds_reserved"] = ledger.available(draft["from_account"]) >= draft["amount"]
    reason = evaluate(facts)
    if reason:
        return _blocked_submit(reason, draft, facts, ledger)

    amount = draft["amount"]
    reference = f"NB-TRF-{_digest(conversation_id, key)}"
    behaviour = "posted" if dest["kind"] == "own_account" else dest["scheme_behaviour"]
    transfer = {
        "customer_id": customer_id,
        "from_account": draft["from_account"],
        "payee_ref": draft["payee_ref"],
        "amount": amount,
        "attempt_id": key,
        "balance_revision": draft["revision"],
        "submitted_at": ledger.as_of,
        "posted_at": None,
        "reservation": f"NB-RSV-{_digest(key, 'reserve')}",
    }
    if behaviour == "posted":
        account["posted_balance"] -= amount
        target = ledger.accounts[draft["payee_ref"]]
        target["posted_balance"] += amount
        target["revision"] += 1
        transfer.update(ledger_status="posted", posted_at=ledger.as_of)
    else:
        account["holds"].append({"description": f"Transfer {reference}", "amount": amount})
        transfer["ledger_status"] = "unknown" if behaviour == "unknown" else "pending"
    account["revision"] += 1
    transfer["reference_returned"] = behaviour != "ack_lost"
    ledger.transfers[reference] = transfer
    draft["state"] = "submitted"

    if behaviour == "ack_lost":
        # The ledger committed, but the response never reached us.
        return {
            "status": "unconfirmed",
            "reason": "acknowledgment_lost",
            "attempt_id": key,
            "reference": None,
            "ledger_status": "unknown",
            "posted": False,
            "amount": money(amount),
            "from_account_ref": draft["from_account"],
            "payee_ref": draft["payee_ref"],
            "destination": destination_label(dest),
            "facts": facts,
            "effects": 1,
            "replay": False,
            "next_step": (
                "The submission's response was lost, so it is not known whether the transfer was recorded. "
                "Tell the caller it is not confirmed. Call check_transfer_status with this attempt_id before "
                "anything else. Never submit it again."
            ),
        }
    return {**_receipt(ledger, reference, transfer), "facts": facts, "effects": 1, "replay": False}


def _receipt(ledger: Ledger, reference: str, transfer: dict) -> dict:
    dest = ledger.destination(transfer["customer_id"], transfer["payee_ref"])
    status = transfer["ledger_status"]
    result = {
        "status": "unconfirmed" if status == "unknown" else "submitted",
        "reference": reference,
        "attempt_id": transfer.get("attempt_id"),
        "ledger_status": status,
        "posted": status == "posted",
        "posted_at": transfer.get("posted_at"),
        "amount": money(transfer["amount"]),
        "from_account_ref": transfer["from_account"],
        "payee_ref": transfer["payee_ref"],
        "from_account": account_label(ledger.accounts[transfer["from_account"]]),
        "destination": destination_label(dest) if dest else None,
        "balance_revision": transfer.get("balance_revision"),
        "receipt_note": RECEIPT_NOTE,
    }
    if status == "unknown":
        result["reason"] = "scheme_response_unknown"
        result["next_step"] = (
            "The payment scheme has not reported this transfer's state. Tell the caller it is not confirmed "
            "and give the reference. Call check_transfer_status with the reference; if it is still unknown, "
            "call escalate_reconciliation. Never submit it again."
        )
    elif status == "pending":
        result["next_step"] = (
            "Give the reference and say the transfer is pending: the money is reserved and the payee's bank "
            "has not received it yet. Do not say it is posted, complete, sent or received."
        )
    else:
        result["next_step"] = "Give the reference and say the transfer is posted."
    return result


def check_transfer_status(ledger: Ledger, customer_id: Optional[str], key: Any) -> dict:
    """Look a transfer up by reference or attempt id. Never submits anything."""
    found = ledger.find_transfer(customer_id, key)
    if found is None:
        # Someone else's reference and a reference that does not exist look the same.
        return {"status": "not_found", "reference": normalise_ref(key), "effects": 0,
                "next_step": "No transfer on this customer's ledger matches. Ask the caller to check the reference. Do not submit anything."}
    reference, transfer = found
    result = _receipt(ledger, reference, transfer)
    result["status"] = "read"
    result["effects"] = 0
    if transfer["ledger_status"] == "unknown":
        result["next_step"] = (
            "The ledger still cannot confirm this transfer. Call escalate_reconciliation with the reference "
            "and give the caller its reference. Never submit the transfer again."
        )
    elif transfer["ledger_status"] == "pending":
        result["next_step"] = (
            "The transfer is recorded and pending: reserved, not yet received by the payee's bank. Give the "
            "reference. Do not submit it again and do not say it is posted."
        )
    return result


def escalate_reconciliation(ledger: Ledger, customer_id: Optional[str], key: Any, note: Any) -> dict:
    """Hand an unconfirmed transfer to the payments ledger owner. Never a new transfer."""
    found = ledger.find_transfer(customer_id, key)
    if found is None:
        return {"status": "not_found", "reference": normalise_ref(key), "effects": 0,
                "next_step": "No transfer matches. Ask the caller to check the reference."}
    reference, transfer = found
    if transfer["ledger_status"] == "posted":
        return {"status": "not_needed", "reference": reference, "ledger_status": "posted", "effects": 0,
                "next_step": "The transfer is posted; there is nothing to reconcile."}
    return {
        "status": "escalated",
        "reconciliation_reference": f"NB-REC-{_digest(customer_id, reference, 'reconcile')}",
        "transfer_reference": reference,
        "owner": "payments ledger owner",
        "note": " ".join(str(note or "").split())[:200],
        "ledger_status": transfer["ledger_status"],
        "effects": 0,
        "next_step": (
            "Give the caller the reconciliation reference. The payments ledger team replies within one "
            "business day. The transfer stays as it is; do not submit another."
        ),
    }
