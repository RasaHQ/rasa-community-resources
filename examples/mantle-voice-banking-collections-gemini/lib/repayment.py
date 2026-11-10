"""Northgate Bank repayment plans and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three request rules of the casebook contract for
``banking-collections`` (vendored as ``lib/fixtures/case-contract.json``):

- ``offer_terms_current``: the plan is one of the offers this account has now,
  on the account's current terms version, and its offer has not expired on
  the fixture clock. A plan the customer or the model makes up, or an old
  letter's plan, has no current terms.
- ``hardship_exit_available``: the hardship team for the account's product can
  take a referral. When it cannot, automated offer collection is off: the
  request is preserved and a person calls back (the contract's recovery).
- ``choice_freely_confirmed``: the customer chose this exact plan, the engine's
  confirmation question read those terms back, the customer answered it
  without withdrawing, and nothing in the call says the choice was not free:
  no hardship declared in the customer's own words, no hardship referral open.

Facts are computed here from trusted data, the session's customer id and the
customer's own words (the tracker's user messages; on a voice call, what
speech-to-text heard). The model supplies an account ending, an offer id or
the plan's installments and amount, and a short summary for a referral. It
never supplies a fact, a customer id, an amount that gets recorded or an
outcome. A fact that is not exactly ``True`` fails its rule, as in the lab's
``evaluate``.

Only permitted plans are ever recorded: ``record_plan_choice`` writes a plan
only when every rule holds, and the plan it writes is copied from the
fixture's offer, never from the model's arguments.

The organisation guard runs at import. It is an allowlist, not a list of real
names: the fixture's organisation must be exactly the casebook contract's
fictional organisation, marked ``(fictional)``, and the contract must be the
casebook's authored synthetic fixture.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "accounts.json"

# Mantle cuts a memory value at 100 characters in the prompt without saying so
# (found in the GPT quote and diagnostics builds); every memory value is kept
# under this.
MEMORY_VALUE_LIMIT = 100

# The engine's confirmation question for record_plan_choice
# (skills/repayment_plan/responses.yml). Mantle stamps the response name on
# the BotUttered event under this metadata key.
CONFIRM_UTTER = "utter_confirm_plan"
UTTER_ACTION_KEY = "utter_action"

# Skill memory that only the plan tools write. The engine's confirmation
# question reads these back, so what the customer confirms is what the tools
# staged, never a paraphrase.
PLAN_MEMORY_KEYS = ("plan_offer_id", "plan_tag", "plan_account_label", "plan_terms_label", "plan_first_due_label")

# The receipts go to the customer from the tool itself, through
# ToolContext.send, so the reference reaches them whatever the model does next
# (the HarborCover claim-intake build's fix for a silent complete_skill).
TOOL_SENDS_RECEIPT = True


class FictionalOrganisationError(RuntimeError):
    """The fixture does not describe the casebook's fictional organisation."""


def assert_fictional(data: dict, contract: dict) -> None:
    """Refuse fixture data that is not the casebook's own fictional organisation.

    An allowlist: the only organisation accepted is the one the vendored
    casebook contract names, marked "(fictional)". No list of real names is
    kept anywhere in this project.
    """
    provenance = contract.get("provenance") or {}
    if provenance.get("kind") != "authored-synthetic-fixture":
        raise FictionalOrganisationError("the case contract must be the casebook's authored synthetic fixture")
    expected = f"{contract['organisation']} (fictional)"
    if data.get("organisation") != expected:
        raise FictionalOrganisationError(
            f"organisation must be exactly {expected!r}, got {data.get('organisation')!r}")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")
    for route in (data.get("hardship_routes") or {}).values():
        team = str(route.get("team") or "")
        other = re.search(r"\b([A-Z][a-z]+ (?:Bank|Banco|Credit Union|Financial))\b", team)
        if other and other.group(1) != contract["organisation"]:
            raise FictionalOrganisationError(f"hardship team names another organisation: {team!r}")


# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA, _CONTRACT)

ORGANISATION = _DATA["organisation"].split(" (")[0]
SESSION_CUSTOMER_ID = _DATA["session_customer_id"]


def load_contract() -> dict:
    return json.loads(json.dumps(_CONTRACT))


def load_data() -> dict:
    return json.loads(json.dumps(_DATA))


def request_rules(contract: Optional[dict] = None) -> list[dict]:
    contract = contract or _CONTRACT
    return [rule for rule in contract["rules"] if rule["phase"] == "request"]


def evaluate(facts: dict, contract: Optional[dict] = None) -> Optional[str]:
    """First failing rule's reason, or None. A fact must be exactly ``True``."""
    for rule in request_rules(contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


# ----------------------------------------------------------------------------
# Spanish for the ear: amounts, dates and references
# ----------------------------------------------------------------------------

_UNITS = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
          "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho",
          "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco",
          "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_TENS = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta",
         90: "noventa"}
_HUNDREDS = {100: "ciento", 200: "doscientos", 300: "trescientos", 400: "cuatrocientos", 500: "quinientos",
             600: "seiscientos", 700: "setecientos", 800: "ochocientos", 900: "novecientos"}
_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"]


def number_words(n: int) -> str:
    """0..999999 in Spanish words, as a US Spanish speaker says an amount."""
    if n < 0 or n > 999_999:
        raise ValueError(n)
    if n < 30:
        return _UNITS[n]
    if n < 100:
        tens, unit = divmod(n, 10)
        return _TENS[tens * 10] + (f" y {_UNITS[unit]}" if unit else "")
    if n < 1000:
        if n == 100:
            return "cien"
        hundreds, rest = divmod(n, 100)
        return _HUNDREDS[hundreds * 100] + (f" {number_words(rest)}" if rest else "")
    thousands, rest = divmod(n, 1000)
    head = "mil" if thousands == 1 else f"{number_words(thousands)} mil"
    return head + (f" {number_words(rest)}" if rest else "")


def _apocope(words: str) -> str:
    """'uno' before a masculine noun: 'veintiuno dólares' -> 'veintiún dólares'."""
    if words.endswith("veintiuno"):
        return words[:-len("veintiuno")] + "veintiún"
    if words.endswith("uno"):
        return words[:-3] + "un"
    return words


def spoken_amount(amount: str) -> str:
    """'204.00' -> 'doscientos cuatro dólares'; '151.67' -> '... dólares con sesenta y siete centavos'."""
    value = Decimal(amount)
    dollars = int(value)
    cents = int((value - dollars) * 100)
    text = f"{_apocope(number_words(dollars))} {'dólar' if dollars == 1 else 'dólares'}"
    if cents:
        text += f" con {_apocope(number_words(cents))} centavos"
    return text


def spoken_date(day: str) -> str:
    """'2026-10-15' -> '15 de octubre'."""
    d = date.fromisoformat(day)
    return f"{d.day} de {_MONTHS[d.month - 1]}"


def spoken_reference(reference: str) -> str:
    """'PLN-482913' -> 'P, L, N, cuatro, ocho, dos, nueve, uno, tres'."""
    parts: list[str] = []
    for ch in reference:
        if ch.isalpha():
            parts.append(ch.upper())
        elif ch.isdigit():
            parts.append(_UNITS[int(ch)])
    return ", ".join(parts)


def make_reference(prefix: str, *parts: str) -> str:
    """Letters, then six digits: easy to read out and to hear back ('PLN-482913')."""
    return f"{prefix}-{int(hashlib.sha256('|'.join(parts).encode()).hexdigest(), 16) % 1_000_000:06d}"


# ----------------------------------------------------------------------------
# The customer's own words: hardship and withdrawal
# ----------------------------------------------------------------------------


def fold(text: Any) -> str:
    """Lower case without accents: 'Perdí mi TRABAJO' -> 'perdi mi trabajo'."""
    decomposed = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# A customer who says they cannot meet basic living costs has declared
# hardship. "I can't pay it all at once" has not: that is what a plan is for,
# so the list names basic needs and lost income, never a bare "no puedo
# pagar".
HARDSHIP_PATTERNS = (
    r"\bno me alcanza\b",
    r"\bapenas me alcanza\b",
    r"\bno (?:me )?(?:queda|tengo) (?:dinero |nada )?(?:ni )?para (?:comer|la comida|la renta|el alquiler|la luz"
    r"|las medicinas|los gastos|lo basico|la casa)",
    r"\bgastos basicos\b",
    r"\blo basico\b",
    r"\b(?:perdi|me quede sin|me quitaron|me corrieron del) (?:mi |el )?(?:trabajo|empleo)\b",
    r"\bsin (?:trabajo|empleo)\b",
    r"\bdesemplead[oa]\b",
    r"\bno puedo cubrir\b",
    r"\bno puedo pagar (?:la renta|la comida|el alquiler|lo basico|mis gastos)\b",
)
_HARDSHIP_RE = re.compile("|".join(HARDSHIP_PATTERNS))

# A withdrawal in the answer to the confirmation question. The engine's gate
# normally reads it as a denial; this is the code's own check, in case the
# model resolves the question as confirmed anyway.
WITHDRAWAL_PATTERNS = (
    r"\bmejor no\b",
    r"\bya no\b",
    r"\bno quiero\b",
    r"\bno confirmo\b",
    r"\bno lo registre\b",
    r"\bcancel",
    r"\bolvide\b",
    r"\bolvidelo\b",
    r"\bespere\b",
    r"^\s*no\b",
)
_WITHDRAWAL_RE = re.compile("|".join(WITHDRAWAL_PATTERNS))


def hardship_declared(user_texts: Iterable[str]) -> Optional[str]:
    """The first customer message that declares hardship, or None."""
    for text in user_texts:
        if _HARDSHIP_RE.search(fold(text)):
            return text
    return None


def is_withdrawal(text: Optional[str]) -> bool:
    return bool(text) and _WITHDRAWAL_RE.search(fold(text)) is not None


@dataclass(frozen=True)
class Conversation:
    """The tools' view of the call, read from the tracker."""

    user_texts: tuple = ()
    # Text of the latest confirmation question (CONFIRM_UTTER) and the
    # customer's first message after it, if any.
    confirmation_question: Optional[str] = None
    confirmation_answer: Optional[str] = None


# ----------------------------------------------------------------------------
# Per-call state: the staged choice, recorded plans, referrals and callbacks
# ----------------------------------------------------------------------------


@dataclass
class CallState:
    conversation_id: str
    staged: Optional[dict] = None
    plans: list = field(default_factory=list)
    referrals: list = field(default_factory=list)
    callbacks: list = field(default_factory=list)
    stage_count: int = 0

    def open_referral(self) -> Optional[dict]:
        return self.referrals[-1] if self.referrals else None

    def active_plan(self, account: Optional[str] = None) -> Optional[dict]:
        for plan in reversed(self.plans):
            if plan["plan_status"] == "recorded" and (account is None or plan["account_ending"] == account):
                return plan
        return None


_STATES: dict[str, CallState] = {}


def state_for(conversation_id: str) -> CallState:
    """One state per conversation, so every scripted call starts from the same fixture."""
    if conversation_id not in _STATES:
        _STATES[conversation_id] = CallState(conversation_id)
    return _STATES[conversation_id]


def reset_states() -> None:
    _STATES.clear()


# ----------------------------------------------------------------------------
# Accounts and offers
# ----------------------------------------------------------------------------


def normalise_account(value: Any) -> str:
    """'4471', 'la tarjeta 4471', 'cuatro cuatro siete uno' -> '4471'; else the digits found."""
    text = fold(value)
    words = {w: str(i) for i, w in enumerate(["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
                                               "ocho", "nueve"])}
    digits = "".join(words.get(t, t if t.isdigit() else "") for t in re.findall(r"[a-z]+|\d+", text))
    return digits[-4:] if len(digits) >= 4 else digits


def _account(data: dict, customer_id: Optional[str], ending: Any) -> tuple[Optional[str], Optional[dict]]:
    key = normalise_account(ending)
    account = data["accounts"].get(key)
    if account is None or customer_id is None or account["customer_id"] != customer_id:
        return key, None
    return key, account


def _not_found(key: str) -> dict:
    # Someone else's account and an unknown number get the same answer, so the
    # call never confirms that an account exists for another customer.
    return {
        "status": "not_found",
        "account_ending": key,
        "next_step": ("Say you cannot find an account ending in those digits on this customer's profile and "
                      "ask them to check the last four digits. Never say whether it belongs to someone else."),
    }


def _as_of(data: dict) -> date:
    return datetime.fromisoformat(data["as_of"]).date()


def terms_current(account: dict, offer: Optional[dict], data: dict) -> bool:
    return (
        offer is not None
        and offer.get("terms_version") == account.get("offers_terms_version")
        and _as_of(data) <= date.fromisoformat(offer["valid_until"])
    )


def hardship_route(account: dict, data: dict) -> dict:
    return data["hardship_routes"][account["product"]]


def hardship_exit_available(account: dict, data: dict) -> bool:
    return hardship_route(account, data).get("available") is True


def _offer_view(offer: dict) -> dict:
    return {
        "offer_id": offer["offer_id"],
        "installments": offer["installments"],
        "amount_usd": offer["amount_usd"],
        "amount_spoken": spoken_amount(offer["amount_usd"]),
        "first_due": offer["first_due"],
        "first_due_spoken": spoken_date(offer["first_due"]),
        "terms_spoken": f"{number_words(offer['installments'])} pagos mensuales de {spoken_amount(offer['amount_usd'])}",
    }


def _to_decimal(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value).replace("$", "").replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def find_offer(account: dict, offer_id: Any = None, installments: Any = None, amount_usd: Any = None) -> Optional[dict]:
    """The account's offer the customer asked for, by id or by installments and amount.

    Expired offers are found too, so an old letter's plan is refused as stale
    rather than as unknown. A plan with no matching offer returns None.
    """
    wanted = str(offer_id or "").strip().upper()
    for offer in account["offers"]:
        if wanted and offer["offer_id"] == wanted:
            return offer
    try:
        count = int(installments) if installments not in (None, "") else None
    except (TypeError, ValueError):
        count = None
    amount = _to_decimal(amount_usd) if amount_usd not in (None, "") else None
    if count is None and amount is None:
        return None
    matches = [
        o for o in account["offers"]
        if (count is None or o["installments"] == count) and (amount is None or Decimal(o["amount_usd"]) == amount)
    ]
    return matches[0] if len(matches) == 1 else None


CASE_QUESTION = ("Puede revisar la opción disponible o hablar con el equipo de apoyo financiero. "
                 "¿Qué le ayudaría más?")


def _hardship_stop(state: CallState, conversation: Conversation) -> Optional[dict]:
    said = hardship_declared(conversation.user_texts)
    referral = state.open_referral()
    if not said and not referral:
        return None
    return {
        "status": "hardship_declared",
        "offers": [],
        "customer_said": said,
        "hardship_referral": referral["reference"] if referral else None,
        "next_step": (
            "The customer has said they cannot meet basic expenses, or a hardship referral is open. Do not "
            "present, suggest or ask about any payment plan or payment amount for the rest of this call. "
            + ("Tell them the hardship referral reference and that the team will call." if referral else
               "Offer the hardship team with request_hardship_referral and ask whether they want it.")
        ),
    }


def get_plan_offers(customer_id: Optional[str], account_ending: Any, conversation: Conversation,
                    state: CallState, data: Optional[dict] = None) -> dict:
    """The current plans for one account, with the hardship exit beside them."""
    data = data or _DATA
    key, account = _account(data, customer_id, account_ending)
    if account is None:
        return _not_found(key)
    stop = _hardship_stop(state, conversation)
    if stop:
        return {**stop, "account_ending": key}
    base = {"account_ending": key, "account_label": account["label"], "past_due_usd": account["past_due_usd"],
            "past_due_spoken": spoken_amount(account["past_due_usd"])}
    if not hardship_exit_available(account, data):
        return {
            "status": "blocked",
            "reason": "hardship_path_missing",
            "detail": "offer_collection_off",
            **base,
            "offers": [],
            "next_step": (
                "Automated payment plans are switched off for this account because its hardship team cannot "
                "take referrals right now. Do not present any plan or amount. Offer a call back from a person "
                "(request_human_callback), or request_hardship_referral if they cannot meet basic expenses; "
                "either way the request is kept."
            ),
        }
    offers = [_offer_view(o) for o in account["offers"] if terms_current(account, o, data)]
    return {
        "status": "offers",
        **base,
        "offers": offers,
        "hardship_option": {"team": hardship_route(account, data)["team"], "tool": "request_hardship_referral"},
        "question": CASE_QUESTION,
        "payment_note": "Choosing a plan is a promise to pay, not a payment. No payment has been received.",
        "next_step": (
            "Unless the customer already said which they want, ask the question first, in these words. Present "
            "only these offers, with their exact amounts and dates, and never another amount, number of "
            "payments or date. If the customer says they cannot meet basic expenses, stop offering plans and "
            "offer the hardship team."
        ),
    }


def plan_memory_values(account: dict, offer: dict, tag: str) -> dict:
    values = {
        "plan_offer_id": offer["offer_id"],
        "plan_tag": tag,
        "plan_account_label": account["label"],
        "plan_terms_label": _offer_view(offer)["terms_spoken"],
        "plan_first_due_label": spoken_date(offer["first_due"]),
    }
    for key, value in values.items():
        if len(value) >= MEMORY_VALUE_LIMIT:
            raise ValueError(f"memory value {key} would be cut at {MEMORY_VALUE_LIMIT} characters: {value!r}")
    return values


def select_plan_offer(customer_id: Optional[str], account_ending: Any, conversation: Conversation, state: CallState,
                      offer_id: Any = None, installments: Any = None, amount_usd: Any = None,
                      data: Optional[dict] = None) -> tuple[dict, Optional[dict]]:
    """Stage the plan the customer picked, for the engine to read back. Records nothing."""
    data = data or _DATA
    key, account = _account(data, customer_id, account_ending)
    if account is None:
        return _not_found(key), None
    stop = _hardship_stop(state, conversation)
    if stop:
        state.staged = None
        return {**stop, "account_ending": key, "reason": "choice_not_confirmed", "detail": "hardship_declared"}, None
    offer = find_offer(account, offer_id, installments, amount_usd)
    facts = {
        "offer_terms_current": terms_current(account, offer, data),
        "hardship_exit_available": hardship_exit_available(account, data),
    }
    if facts["offer_terms_current"] is not True:
        state.staged = None
        current = [_offer_view(o) for o in account["offers"] if terms_current(account, o, data)]
        return {
            "status": "blocked",
            "reason": "stale_plan_terms",
            "detail": "expired" if offer is not None else "not_offered",
            "account_ending": key,
            "facts": facts,
            **({"asked_for": {"installments": offer["installments"], "amount_usd": offer["amount_usd"],
                              "valid_until": offer["valid_until"]}} if offer else {}),
            "current_offers": current if facts["hardship_exit_available"] else [],
            "next_step": (
                ("That offer has expired; its terms are no longer valid. " if offer else
                 "That plan is not an offer on this account; no other amount or schedule can be recorded. ")
                + "Say so plainly, then give the current offers, if any, or the hardship team."
            ),
        }, None
    if facts["hardship_exit_available"] is not True:
        state.staged = None
        return {"status": "blocked", "reason": "hardship_path_missing", "detail": "offer_collection_off",
                "account_ending": key, "facts": facts,
                "next_step": "Automated plans are off for this account. Offer request_human_callback."}, None
    state.stage_count += 1
    tag = f"{offer['offer_id']}/{state.stage_count}"
    state.staged = {"account_ending": key, "offer_id": offer["offer_id"], "tag": tag}
    return {
        "status": "staged",
        "account_ending": key,
        **_offer_view(offer),
        "recorded": False,
        "next_step": ("Call record_plan_choice with this offer_id now. Do not ask for confirmation yourself: the "
                      "engine reads the exact terms back and asks the customer."),
    }, plan_memory_values(account, offer, tag)


def confirmation_facts(conversation: Conversation, state: CallState, account: dict, offer: Optional[dict],
                       memory_tag: Optional[str]) -> tuple[bool, Optional[str]]:
    """choice_freely_confirmed, and why not.

    The latest confirmation question must carry this offer's exact terms and
    account, as the customer heard them; the first customer message after it
    must not withdraw the choice.
    """
    if hardship_declared(conversation.user_texts) or state.open_referral():
        return False, "hardship_declared"
    staged = state.staged
    if offer is None or not staged or staged["offer_id"] != offer["offer_id"] or memory_tag != staged["tag"]:
        return False, "not_staged"
    question = fold(conversation.confirmation_question or "")
    if fold(_offer_view(offer)["terms_spoken"]) not in question or fold(account["label"]) not in question:
        return False, "not_read_back"
    if conversation.confirmation_answer is None:
        return False, "not_answered"
    if is_withdrawal(conversation.confirmation_answer):
        return False, "withdrawn"
    return True, None


def record_plan_choice(customer_id: Optional[str], conversation: Conversation, state: CallState, offer_id: Any,
                       memory: dict, conversation_id: str, data: Optional[dict] = None) -> dict:
    """Record one confirmed, permitted plan: the case's guarded action."""
    data = data or _DATA
    staged = state.staged or {}
    wanted = str(offer_id or "").strip().upper()
    key, account = _account(data, customer_id, staged.get("account_ending") or "")
    if account is None:
        return {"status": "blocked", "reason": "choice_not_confirmed", "detail": "not_staged", "effects": 0,
                "next_step": "No plan was chosen on this call. Use get_plan_offers and select_plan_offer first."}
    offer = find_offer(account, wanted)
    confirmed, why_not = confirmation_facts(conversation, state, account, offer, memory.get("plan_tag"))
    facts = {
        "offer_terms_current": terms_current(account, offer, data),
        "hardship_exit_available": hardship_exit_available(account, data),
        "choice_freely_confirmed": confirmed,
    }
    reason = evaluate(facts)
    if reason:
        if why_not in ("withdrawn", "hardship_declared"):
            state.staged = None
        return {
            "status": "blocked",
            "reason": reason,
            **({"detail": why_not} if reason == "choice_not_confirmed" else {}),
            "account_ending": key,
            "facts": facts,
            "effects": 0,
            "recorded": False,
            "next_step": {
                "stale_plan_terms": "Those terms are not current. Nothing was recorded. Offer the current plans.",
                "hardship_path_missing": "Automated plans are off. Nothing was recorded. Offer request_human_callback.",
                "choice_not_confirmed": (
                    "Nothing was recorded. " + {
                        "hardship_declared": "The customer declared hardship: offer the hardship team, no plans.",
                        "withdrawn": "The customer withdrew the choice: confirm that nothing was recorded and no debit was scheduled.",
                    }.get(why_not or "", "Stage the plan with select_plan_offer so the engine can read it back.")
                ),
            }[reason],
        }
    reference = make_reference("PLN", conversation_id, key, offer["offer_id"], str(len(state.plans)))
    plan = {
        "status": "succeeded",
        "plan_status": "recorded",
        "reference": reference,
        "reference_spoken": spoken_reference(reference),
        "account_ending": key,
        "account_label": account["label"],
        **_offer_view(offer),
        "payment_status": "no_payment_received",
        "debit_scheduled": False,
        "facts": facts,
        "effects": 1,
        "next_step": ("The customer has already been sent the plan reference and terms. Say that choosing the plan "
                      "is not a payment and no payment has been received."),
    }
    state.plans.append(plan)
    state.staged = None
    return plan


def withdraw_plan_choice(state: CallState, account_ending: Any = None) -> dict:
    """The customer takes the choice back: clear a staged plan, or cancel one recorded on this call."""
    key = normalise_account(account_ending) if account_ending else None
    plan = state.active_plan(key)
    if plan is not None:
        plan["plan_status"] = "withdrawn"
        state.staged = None
        return {
            "status": "withdrawn",
            "reference": plan["reference"],
            "reference_spoken": plan["reference_spoken"],
            "account_ending": plan["account_ending"],
            "plan_status": "withdrawn",
            "debit_scheduled": False,
            "payment_status": "no_payment_received",
            "effects": 1,
            "next_step": "Say the plan was withdrawn, nothing is active and no debit is scheduled.",
        }
    had_staged = state.staged is not None
    state.staged = None
    return {
        "status": "nothing_recorded",
        "staged_choice_cleared": had_staged,
        "debit_scheduled": False,
        "effects": 0,
        "next_step": "Say that no plan was recorded and no debit was scheduled.",
    }


def request_hardship_referral(customer_id: Optional[str], account_ending: Any, summary: Optional[str],
                              state: CallState, conversation_id: str, data: Optional[dict] = None) -> dict:
    """The hardship exit: a referral to the product's hardship team, or a preserved request and a callback."""
    data = data or _DATA
    key, account = _account(data, customer_id, account_ending)
    if account is None:
        return _not_found(key)
    route = hardship_route(account, data)
    state.staged = None
    reference = make_reference("HRD", conversation_id, key, "hardship")
    referral = {
        "reference": reference,
        "reference_spoken": spoken_reference(reference),
        "account_ending": key,
        "team": route["team"],
        "summary": (summary or "")[:200],
    }
    if route.get("available") is True:
        referral["referral_status"] = "referred"
        state.referrals.append(referral)
        return {
            "status": "referred",
            **referral,
            "offers_paused": True,
            "next_contact": "El equipo le llama en un día hábil.",
            "effects": 1,
            "next_step": ("The customer has been sent the referral reference. Do not mention payment plans again "
                          "on this call."),
        }
    callback = make_reference("CB", conversation_id, key, "hardship-callback")
    referral["referral_status"] = "preserved"
    state.referrals.append(referral)
    state.callbacks.append({"reference": callback, "account_ending": key, "topic": "hardship"})
    return {
        "status": "callback_requested",
        **referral,
        "referral_preserved": True,
        "callback_reference": callback,
        "callback_reference_spoken": spoken_reference(callback),
        "offers_paused": True,
        "next_contact": "Una persona le llama en un día hábil.",
        "effects": 1,
        "next_step": ("The hardship team cannot take referrals right now, so the request was kept and a person "
                      "will call back. The customer has been sent both references. Do not mention payment plans."),
    }


def request_human_callback(customer_id: Optional[str], account_ending: Any, topic: Optional[str],
                           state: CallState, conversation_id: str, data: Optional[dict] = None) -> dict:
    """A person calls back about the account; no plan is recorded."""
    data = data or _DATA
    key, account = _account(data, customer_id, account_ending)
    if account is None:
        return _not_found(key)
    reference = make_reference("CB", conversation_id, key, "callback", str(len(state.callbacks)))
    state.callbacks.append({"reference": reference, "account_ending": key, "topic": (topic or "")[:120]})
    return {
        "status": "callback_requested",
        "callback_reference": reference,
        "callback_reference_spoken": spoken_reference(reference),
        "account_ending": key,
        "next_contact": "Una persona le llama en un día hábil.",
        "plan_recorded": False,
        "effects": 1,
        "next_step": "The customer has been sent the callback reference. Nothing else is recorded.",
    }


# ----------------------------------------------------------------------------
# What the tools send to the customer themselves (ToolContext.send)
# ----------------------------------------------------------------------------


def customer_receipt(tool_name: str, result: dict) -> Optional[str]:
    """The Spanish receipt a tool sends straight to the customer, or None."""
    status = result.get("status")
    if tool_name == "record_plan_choice" and status == "succeeded":
        return (f"Plan registrado. Su referencia es {result['reference_spoken']}. "
                f"{result['account_label'].capitalize()}: {result['terms_spoken']}, el primero el "
                f"{result['first_due_spoken']}. Elegir un plan no es un pago: no hemos recibido ningún pago "
                "y no se programó ningún cargo automático.")
    if tool_name == "withdraw_plan_choice" and status == "withdrawn":
        return (f"Retiré el plan con referencia {result['reference_spoken']}. No queda ningún plan activo "
                "y no se programó ningún cargo.")
    if tool_name == "request_hardship_referral" and status == "referred":
        return (f"Le pasé con el {result['team']}. Su referencia es {result['reference_spoken']}. "
                f"{result['next_contact']} No le vamos a pedir un plan de pagos en esta llamada.")
    if tool_name == "request_hardship_referral" and status == "callback_requested":
        return (f"El {result['team']} no puede recibir solicitudes en este momento, así que guardé su solicitud "
                f"con la referencia {result['reference_spoken']}. {result['next_contact']} La referencia de la "
                f"llamada es {result['callback_reference_spoken']}.")
    if tool_name == "request_human_callback" and status == "callback_requested":
        return (f"Listo, {result['next_contact'][0].lower()}{result['next_contact'][1:]} Su referencia es "
                f"{result['callback_reference_spoken']}.")
    return None


def session_profile(customer_id: str = SESSION_CUSTOMER_ID, data: Optional[dict] = None) -> dict:
    data = data or _DATA
    person = data["customers"][customer_id]
    accounts = [
        f"{'tarjeta' if a['product'] == 'card' else 'préstamo'} {ending}"
        for ending, a in sorted(data["accounts"].items()) if a["customer_id"] == customer_id
    ]
    account_list = ", ".join(accounts)
    if len(account_list) >= MEMORY_VALUE_LIMIT:
        raise ValueError("account list would be cut in the prompt")
    return {"customer_id": customer_id, "first_name": person["first_name"], "account_list": account_list}
