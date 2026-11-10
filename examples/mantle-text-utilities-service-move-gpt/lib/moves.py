"""Amber Grid home moves: premises register, move orders, service state and the case guard. No Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the casebook contract for ``utilities-service-move`` (vendored
as ``lib/fixtures/case-contract.json``) when ``submit_move_order`` runs:

- ``premise_identity_resolved`` (``wrong_premise``): the service the customer
  is leaving is one of the signed-in customer's own active service points,
  and the destination resolved to exactly one serviceable premises in Amber
  Grid's register from the customer's words. A street with several flats, or
  the same street in two towns, resolves to nothing until the customer says
  which. The draft the engine read back must still be the current version.
- ``effective_dates_confirmed`` (``move_date_ambiguous``): both dates are
  exact days the customer said in this conversation ("next month" and "the
  end of October" are not), from tomorrow to 90 days out at the fixture
  clock, and the engine's question for this draft version, carrying both
  dates, was sent and answered.
- ``move_order_receipt_verified`` (``move_order_unconfirmed``, receipt
  phase): the move-order system acknowledged the order and its read-back
  matches the confirmed premises and dates, with the current service still
  on until the move-out date. When it does not, the closure instruction is
  held and the current service stays exactly as it is.

No tool closes a service. The only way a current service gets an end date is
a verified move order, and the end date is the confirmed move-out date: the
service stays on through that day. The model never supplies a date as a
value the tools trust: it passes the customer's words for each date, and the
tool reads the day from them and checks the customer said it.

Facts are computed here from trusted data and the conversation's events. A
fact that is not exactly ``True`` fails its rule, as in the lab's
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
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "amber_grid_moves.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (rasa/mantle/prompts/memory_lines.py,
# MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5; found in the GPT quote and
# diagnostics builds). Every value a tool writes to memory is one short field;
# tests/test_guard.py builds every draft the fixture allows and checks them.
MEMORY_VALUE_LIMIT = 100

# The engine's confirmation question for submit_move_order
# (skills/service_move/responses.yml). Mantle stamps the response name on the
# BotUttered event under this metadata key.
CONFIRM_UTTER = "utter_confirm_move"
UTTER_ACTION_KEY = "utter_action"

# The tools send the customer the move-order receipt, the "not confirmed"
# notice or the review reference themselves through ToolContext.send (found
# in the HarborCover claim-intake build: a silent complete_skill otherwise
# hides the receipt). The `receipt-in-result-only` variant sets this to False.
TOOL_SENDS_RECEIPT = True

# Skill memory keys the tools write (skills/service_move/memory.yml).
MEMORY_KEYS = ("move_draft_tag", "move_order_note", "move_from", "move_to", "move_out_on", "move_in_on", "move_ready")

# Organisation fields the allowlist checks, wherever they appear in the fixture.
ORGANISATION_KEYS = ("organisation", "supplier", "company", "vendor", "operator", "network")

REVIEW_TEAM = "service lifecycle team"
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
AS_OF = date.fromisoformat(_DATA["as_of"])
WINDOW_DAYS = int(_DATA["window_days"])


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
# Apostrophes. GPT-5.5 writes typographic ones ("can’t", "you’re"); every
# pattern below accepts both, and text is also normalised before matching.
# ----------------------------------------------------------------------------

APOS = "['’]"
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})


def plain(text: str) -> str:
    return (text or "").translate(_APOSTROPHES)


# ----------------------------------------------------------------------------
# Words: saying the current service is already off (hooks.py and the metric)
# ----------------------------------------------------------------------------

# A sentence that says the customer's current supply is off or closed now.
CLOSURE_PATTERN = (
    r"\b(?:your|the)\s+(?:current\s+|old\s+)?(?:power|electricity|gas|supply|service|account|energy)"
    r"(?:\s+(?:supply|service|account))?(?:\s+at\s+[^.!?]{1,60}?)?\s+"
    r"(?:has\s+been|have\s+been|is\s+now|is|was|are\s+now|got)\s+(?:now\s+|already\s+|officially\s+)?"
    r"(?:closed|disconnected|shut\s+off|switched\s+off|turned\s+off|cut\s+off|stopped|ended|terminated|cancel+ed|off)\b"
    rf"|\b(?:i|we){APOS}?(?:ve|\s+have)?\s+(?:just\s+|now\s+|already\s+)?"
    r"(?:closed|disconnected|shut\s+off|switched\s+off|turned\s+off|cut\s+off|stopped|ended|terminated|cancel+ed)"
    r"\s+(?:your|the)\s+(?:current\s+|old\s+)?(?:power|electricity|gas|supply|service|account|energy)\b"
)
# A match is not a claim when the same sentence negates or conditions it
# before the match: "nothing changes and your supply is not closed until...".
HEDGE_PATTERN = (
    r"\b(?:not|no|never|nothing|until|unless|once|after|when|if|whether|cannot|won" + APOS + r"t|isn" + APOS
    + r"t|hasn" + APOS + r"t|can" + APOS + r"t|don" + APOS + r"t|will|would|may|might|could|should)\b"
    + r"|n" + APOS + r"t\b"
)
CLOSURE_RE = re.compile(CLOSURE_PATTERN, re.IGNORECASE)
HEDGE_RE = re.compile(HEDGE_PATTERN, re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
# The hedge reaches back to the start of the sentence, or to the last clause
# break before the match: "Nothing has changed yet, and your supply is off"
# is still a claim.
_CLAUSE_BREAK_RE = re.compile(r"[,;:]\s+|\s+(?:and|but|so)\s+", re.IGNORECASE)


def closure_claims(text: str) -> list[str]:
    """Sentences (or clauses) that say the customer's current supply is already off."""
    found = []
    for sentence in _SENTENCE_RE.split(plain(text)):
        for match in CLOSURE_RE.finditer(sentence):
            before = sentence[: match.start()]
            breaks = list(_CLAUSE_BREAK_RE.finditer(before))
            clause = before[breaks[-1].end():] if breaks else before
            after = sentence[match.end(): match.end() + 40]
            # "stays on through 24 October, then it is stopped" and "is ended on
            # 24 October" are schedules, not closures now.
            if HEDGE_RE.search(clause) or re.match(r"\s+(?:on|from|after|at\s+the\s+end|once|when)\b", after,
                                                   re.IGNORECASE):
                continue
            found.append(match.group(0))
    return found


# ----------------------------------------------------------------------------
# Dates: an exact day the customer said, or nothing
# ----------------------------------------------------------------------------

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
_MONTH = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_ORD = r"(?:st|nd|rd|th)?"
_ISO_RE = re.compile(r"\b(20\d\d)-(\d{1,2})-(\d{1,2})\b")
_MONTH_DAY_RE = re.compile(rf"\b{_MONTH}\.?\s+(\d{{1,2}}){_ORD}\b(?:,?\s+(20\d\d))?", re.IGNORECASE)
_DAY_MONTH_RE = re.compile(rf"\b(\d{{1,2}}){_ORD}\s+(?:of\s+)?{_MONTH}\b\.?(?:,?\s+(20\d\d))?", re.IGNORECASE)
_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(20\d\d))?\b")
_BARE_ORDINAL_RE = re.compile(r"\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE)
_RELATIVE_RE = re.compile(r"\b(tomorrow|today)\b", re.IGNORECASE)
# Words that make a stated day approximate: "around the 24th", "end of October".
_VAGUE_RE = re.compile(
    r"\b(?:around|about|roughly|approximately|approx|sometime|some\s+time|or\s+so|ish|early|mid|late|end\s+of"
    r"|start\s+of|beginning\s+of|first\s+week|last\s+week|next\s+month|next\s+week|this\s+month|or\s+the)\b",
    re.IGNORECASE,
)


def _make(year: Optional[str], month: int, day: int, as_of: date) -> Optional[date]:
    try:
        if year:
            return date(int(year), month, day)
        candidate = date(as_of.year, month, day)
        return candidate if candidate >= as_of else date(as_of.year + 1, month, day)
    except ValueError:
        return None


def exact_dates(text: str, as_of: date = AS_OF) -> list[date]:
    """Every exact day written in *text*, in order: ISO, "24 October", "Oct 24th", "24/10", "tomorrow"."""
    found: list[tuple[int, date]] = []
    t = plain(text)
    spans: list[tuple[int, int]] = []

    def add(pos: int, end: int, value: Optional[date]) -> None:
        if value is not None and not any(s <= pos < e for s, e in spans):
            found.append((pos, value))
            spans.append((pos, end))

    for m in _ISO_RE.finditer(t):
        add(m.start(), m.end(), _make(m.group(1), int(m.group(2)), int(m.group(3)), as_of))
    for m in _MONTH_DAY_RE.finditer(t):
        add(m.start(), m.end(), _make(m.group(3), MONTHS[m.group(1).lower()], int(m.group(2)), as_of))
    for m in _DAY_MONTH_RE.finditer(t):
        add(m.start(), m.end(), _make(m.group(3), MONTHS[m.group(2).lower()], int(m.group(1)), as_of))
    for m in _SLASH_RE.finditer(t):
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 and b <= 12:
            add(m.start(), m.end(), _make(m.group(3), b, a, as_of))
        elif b > 12 and a <= 12:
            add(m.start(), m.end(), _make(m.group(3), a, b, as_of))
        # 10/11 could be either; it is not an exact day.
    for m in _RELATIVE_RE.finditer(t):
        add(m.start(), m.end(), as_of + timedelta(days=1) if m.group(1).lower() == "tomorrow" else as_of)
    return [d for _, d in sorted(found, key=lambda x: x[0])]


def read_date(words: Any, as_of: date = AS_OF) -> tuple[Optional[date], Optional[str]]:
    """(day, None) when *words* name exactly one exact day, else (None, problem)."""
    text = plain(str(words or "")).strip()
    if not text:
        return None, "no_date_given"
    if _VAGUE_RE.search(text):
        return None, "not_an_exact_day"
    days = sorted(set(exact_dates(text, as_of)))
    if not days:
        return None, "not_an_exact_day"
    if len(days) > 1:
        return None, "more_than_one_day"
    day = days[0]
    weekdays = [WEEKDAYS[w] for w in re.findall(r"\b(" + "|".join(WEEKDAYS) + r")\b", text.lower())]
    if weekdays and any(w != day.weekday() for w in weekdays):
        return None, "weekday_does_not_match"
    return day, None


def said_by_customer(day: date, user_messages: tuple[str, ...] | list[str], as_of: date = AS_OF) -> bool:
    """Whether the customer stated *day* in this conversation.

    An exact date in any customer message counts. A bare ordinal ("make it the
    27th") counts when the customer also named that month in the conversation.
    """
    stated: set[date] = set()
    bare_days: set[int] = set()
    months: set[int] = set()
    for message in user_messages:
        text = plain(message)
        stated.update(exact_dates(text, as_of))
        bare_days.update(int(m.group(1)) for m in _BARE_ORDINAL_RE.finditer(text))
        months.update(MONTHS[m.lower()] for m in re.findall(_MONTH, text, re.IGNORECASE))
    return day in stated or (day.day in bare_days and day.month in months)


def long_date(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B %Y}"


def date_window(as_of: date = AS_OF) -> tuple[date, date]:
    """Earliest and latest effective day a move can be scheduled for in chat."""
    return as_of + timedelta(days=1), as_of + timedelta(days=WINDOW_DAYS)


def check_day(words: Any, user_messages, as_of: date = AS_OF) -> tuple[Optional[date], Optional[str]]:
    """The day from the customer's words, or the problem that makes it ambiguous."""
    day, problem = read_date(words, as_of)
    if problem:
        return None, problem
    earliest, latest = date_window(as_of)
    if day < earliest:
        return None, "before_earliest_day"
    if day > latest:
        return None, "beyond_scheduling_window"
    if not said_by_customer(day, user_messages, as_of):
        return None, "not_said_by_customer"
    return day, None


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8].upper()


def normalise_id(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = re.sub(r"\s+V\d+$", "", text)
    return re.sub(r"[^A-Z0-9-]", "", re.sub(r"[\s_]+", "-", text))


def address(premises: dict) -> str:
    flat = f"Flat {premises['flat']}, " if premises.get("flat") else ""
    return f"{flat}{premises['number']} {premises['street']}, {premises['town']}"


_ABBREVIATIONS = ((r"\bst\b\.?", "street"), (r"\brd\b\.?", "road"), (r"\bln\b\.?", "lane"), (r"\bcl\b\.?", "close"))


def _address_text(words: Any) -> str:
    text = plain(str(words or "")).lower().replace(",", " ")
    for pattern, replacement in _ABBREVIATIONS:
        text = re.sub(pattern, replacement, text)
    return re.sub(r"\s+", " ", text).strip()


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
# Amber Grid's systems for one conversation
# ----------------------------------------------------------------------------


@dataclass
class Draft:
    draft_id: str
    customer_id: str
    from_sp: str
    to_premises: Optional[str]  # None while the destination is unresolved
    to_words: str
    move_out: Optional[date]
    move_in: Optional[date]
    version: int = 1
    order_ref: Optional[str] = None  # set once an order exists for this draft

    @property
    def tag(self) -> str:
        return f"{self.draft_id} v{self.version}"


class MoveService:
    """Amber Grid's premises register, move-order system and service state for one conversation."""

    def __init__(self, data: Optional[dict] = None, as_of: date = AS_OF) -> None:
        self.data = data or load_data()
        self.as_of = as_of
        self.premises: dict[str, dict] = self.data["premises"]
        self.service_points: dict[str, dict] = self.data["service_points"]
        self.drafts: dict[str, Draft] = {}
        # Move orders by reference: what the order system holds.
        self.orders: dict[str, dict] = {}
        # Per service point: the end date the service state carries, if any,
        # and whether a closure instruction is held for review.
        self.state: dict[str, dict] = {
            sp: {"status": point["status"], "stays_on_through": None, "closure_instruction": "none",
                 "order_ref": None, "review_ref": None}
            for sp, point in self.service_points.items()
        }
        self.reviews: dict[str, dict] = {}
        self._lost_ack_used: set[str] = set()

    # -- reads --------------------------------------------------------------

    def own_service_points(self, customer_id: str) -> list[str]:
        return sorted(sp for sp, p in self.service_points.items() if p["customer_id"] == customer_id)

    def service_label(self, sp: str) -> str:
        return f"{sp} {address(self.premises[self.service_points[sp]['premises']])}"

    def current_service(self, sp: str) -> dict:
        """The current service as the service-state system holds it now."""
        point = self.service_points[sp]
        state = self.state[sp]
        through = state["stays_on_through"]
        return {
            "service_point": sp,
            "address": address(self.premises[point["premises"]]),
            "supply": point["supply"],
            "status": state["status"],
            "on_now": state["status"] == "active",
            "stays_on_through": through.isoformat() if through else None,
            "closure_instruction": state["closure_instruction"],
        }


_SERVICES: dict[str, MoveService] = {}


def service_for(conversation_id: str) -> MoveService:
    """One set of systems per conversation, so every scripted conversation starts from the same data."""
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = MoveService()
    return _SERVICES[conversation_id]


def caller_profile(service: MoveService, customer_id: Optional[str] = None) -> dict:
    customer_id = customer_id or SESSION_CUSTOMER_ID
    person = service.data["customers"][customer_id]
    points = service.own_service_points(customer_id)
    return {
        "customer_id": customer_id,
        "first_name": person["first_name"],
        "service_list": "; ".join(service.service_label(sp) for sp in points),
        "today": service.as_of.isoformat(),
    }


# ----------------------------------------------------------------------------
# Premises resolution
# ----------------------------------------------------------------------------


def resolve_current(service: MoveService, customer_id: str, words: Any) -> tuple[Optional[str], dict]:
    """The customer's own active service point from their words, or a blocked result.

    Another customer's service point gets the same answer as one that does not
    exist, so the agent cannot confirm whose it is.
    """
    text = _address_text(words)
    mine = [sp for sp in service.own_service_points(customer_id) if service.state[sp]["status"] == "active"]
    listing = [service.service_label(sp) for sp in mine]
    not_found = {
        "status": "blocked",
        "reason": "wrong_premise",
        "detail": "not_your_service",
        "next_step": "Say there is no Amber Grid service at that address on their account and name their own.",
        "your_services": listing,
    }
    ident = re.search(r"\b(?:ag-?sp-?)?(\d{4})\b", text)
    if ident and f"AG-SP-{ident.group(1)}" in service.service_points:
        sp = f"AG-SP-{ident.group(1)}"
        return (sp, {}) if sp in mine else (None, not_found)
    candidates = []
    for sp in mine:
        p = service.premises[service.service_points[sp]["premises"]]
        street = p["street"].lower()
        number_given = re.search(rf"\b(\d{{1,4}})\s+{re.escape(street)}\b", text)
        if street in text:
            if number_given and number_given.group(1) != p["number"]:
                continue
            candidates.append(sp)
        elif p.get("flat") and re.search(r"\b(?:flat|apartment)\b", text):
            candidates.append(sp)
    if len(candidates) == 1:
        return candidates[0], {}
    if not candidates and any(p["street"].lower() in text for p in service.premises.values()):
        return None, not_found
    return None, {
        "status": "blocked",
        "reason": "wrong_premise",
        "detail": "which_current_service",
        "next_step": "Ask which of their services they are moving out of; name them.",
        "your_services": [service.service_label(sp) for sp in (candidates or mine)],
    }


def resolve_destination(service: MoveService, words: Any) -> tuple[Optional[str], dict]:
    """Exactly one premises in the register from the customer's words, or why not.

    Returns (premises id, {}) when resolved, else (None, result) with status
    ``which_premises`` (more than one fits: ask), or ``unresolved`` (not in
    the register, or no supply point there yet).
    """
    text = _address_text(words)
    flat = None
    slash = re.search(r"\b(\d{1,3})\s*/\s*(\d{1,4})\b", text)
    if slash:
        flat, text = slash.group(1), text.replace(slash.group(0), f" {slash.group(2)} ")
    match = re.search(r"\b(?:flat|apartment|apt|unit)\s*#?\s*(\d{1,3})\b", text)
    if match:
        flat, text = match.group(1), text.replace(match.group(0), " ")
    number = re.search(r"\b(\d{1,4})[a-z]?\b(?=\s+[a-z])", text)
    streets = {p["street"] for p in service.premises.values() if p["street"].lower() in text}
    towns = {p["town"] for p in service.premises.values() if p["town"].lower() in text}
    candidates = [pid for pid, p in service.premises.items() if p["street"] in streets]
    if number:
        candidates = [pid for pid in candidates if service.premises[pid]["number"] == number.group(1)]
    if flat:
        candidates = [pid for pid in candidates if service.premises[pid].get("flat") == flat]
    if towns:
        candidates = [pid for pid in candidates if service.premises[pid]["town"] in towns]
    if len(candidates) > 1:
        return None, {
            "status": "which_premises",
            "reason": "wrong_premise",
            "detail": "more_than_one_premises_fits",
            "candidates": [address(service.premises[pid]) for pid in sorted(candidates)],
            "next_step": ("More than one premises fits. Ask the customer which one, in their words; never choose "
                          "for them. Then call the tool again with their answer."),
        }
    if not candidates:
        return None, {
            "status": "unresolved",
            "reason": "wrong_premise",
            "detail": "not_in_premises_register",
            "why": "Amber Grid's premises register has no premises at that address; it may be outside the supply area.",
        }
    pid = candidates[0]
    premises = service.premises[pid]
    if premises.get("serviceable") is not True:
        return None, {
            "status": "unresolved",
            "reason": "wrong_premise",
            "detail": "no_supply_point",
            "address": address(premises),
            "why": premises.get("why") or "no supply point at this premises",
        }
    return pid, {}


# ----------------------------------------------------------------------------
# Draft memory (what the engine reads back)
# ----------------------------------------------------------------------------


def memory_values(service: MoveService, draft: Draft) -> dict:
    """The skill memory values for *draft*: one short field each."""
    point = service.service_points[draft.from_sp]
    to = address(service.premises[draft.to_premises]) if draft.to_premises else f"not resolved: {draft.to_words}"
    return {
        "move_draft_tag": draft.tag,
        "move_order_note": f"a change to move order {draft.order_ref}" if draft.order_ref else "a new move order",
        "move_from": f"{address(service.premises[point['premises']])} ({point['supply']})",
        "move_to": to[:80],
        "move_out_on": long_date(draft.move_out) if draft.move_out else "not set",
        "move_in_on": long_date(draft.move_in) if draft.move_in else "not set",
        "move_ready": "yes" if draft.to_premises and draft.move_out and draft.move_in else "",
    }


def memory_values_fit(values: dict) -> bool:
    return all(len(str(v)) <= MEMORY_VALUE_LIMIT for v in values.values())


def _clear() -> dict:
    return {key: "" for key in MEMORY_KEYS}


# ----------------------------------------------------------------------------
# Tools' logic
# ----------------------------------------------------------------------------


def _draft_view(service: MoveService, draft: Draft) -> dict:
    return {
        "draft_id": draft.draft_id,
        "draft_tag": draft.tag,
        "version": draft.version,
        "moving_out_of": service.service_label(draft.from_sp),
        "moving_to": address(service.premises[draft.to_premises]) if draft.to_premises else None,
        "move_out_date": draft.move_out.isoformat() if draft.move_out else None,
        "move_in_date": draft.move_in.isoformat() if draft.move_in else None,
        "amends_order": draft.order_ref,
        "current_service": service.current_service(draft.from_sp),
    }


def _date_problem(which: str, problem: str) -> dict:
    earliest, latest = date_window()
    steps = {
        "no_date_given": f"Ask the customer for the exact {which} day.",
        "not_an_exact_day": (f"The customer has not given an exact {which} day. Ask for the day and month; never "
                             "pick one for them, even for 'next month' or 'the end of the month'."),
        "more_than_one_day": f"The words name more than one day. Ask which day is the {which} date.",
        "weekday_does_not_match": f"The weekday and the date disagree. Ask the customer which {which} day they mean.",
        "before_earliest_day": (f"A {which} can be scheduled from {earliest.isoformat()} at the earliest. Nothing "
                                "changes today: say the current service stays on and ask for a day from then on."),
        "beyond_scheduling_window": (f"A {which} can be scheduled up to {latest.isoformat()}. Ask for a day in that "
                                     "window, or offer to route it for review."),
        "not_said_by_customer": (f"The customer has not said that {which} day in this conversation. Ask them for the "
                                 "exact day; only a day they said can be scheduled."),
    }
    return {"status": "blocked", "reason": "move_date_ambiguous", "detail": f"{which}: {problem}",
            "earliest_day": earliest.isoformat(), "latest_day": latest.isoformat(), "next_step": steps[problem]}


def _new_draft_id(service: MoveService, conversation_id: str) -> str:
    return f"AG-MVD-{_digest(conversation_id, len(service.drafts) + 1)[:5]}"


def start_move_draft(service: MoveService, customer_id: str, conversation: Conversation, conversation_id: str,
                     moving_out_of: str, moving_to: str, move_out_date: str, move_in_date: str) -> tuple[dict, dict]:
    """(result, memory values). Opens a draft move. A draft schedules nothing and changes no service."""
    sp, blocked = resolve_current(service, customer_id, moving_out_of)
    if sp is None:
        return blocked, {}
    existing = service.state[sp]["order_ref"]
    if existing:
        return {"status": "blocked", "reason": "move_already_scheduled", "order_ref": existing,
                "draft_id": service.orders[existing]["draft_id"], "current_service": service.current_service(sp),
                "next_step": ("A move order already exists for this service. For a change of date or address, call "
                              "update_move_draft on its draft; never start a second move.")}, {}
    days = {}
    for which, words in (("move-out", move_out_date), ("move-in", move_in_date)):
        day, problem = check_day(words, conversation.user_messages, service.as_of)
        if problem:
            return _date_problem(which, problem), {}
        days[which] = day
    to, why = resolve_destination(service, moving_to)
    if why.get("status") == "which_premises":
        return why, {}
    if to == service.service_points[sp]["premises"]:
        return {"status": "blocked", "reason": "wrong_premise", "detail": "same_premises",
                "next_step": "The destination is the service they are leaving. Ask where they are moving to."}, {}
    draft = Draft(
        draft_id=_new_draft_id(service, conversation_id), customer_id=customer_id, from_sp=sp, to_premises=to,
        to_words=str(moving_to or "").strip()[:60], move_out=days["move-out"], move_in=days["move-in"],
    )
    service.drafts[draft.draft_id] = draft
    view = _draft_view(service, draft)
    if to is None:
        return {**why, **view, "status": "needs_review",
                "next_step": ("The destination cannot be resolved, so this move cannot be scheduled here. Read the "
                              "address back; if the customer confirms it, call route_move_review with this draft_id. "
                              "Their current service stays on as it is. If they correct the address, call "
                              "update_move_draft.")}, memory_values(service, draft)
    return {"status": "drafted", **view,
            "next_step": ("Call submit_move_order with this draft_id now; the engine reads both sides and dates back "
                          "and asks. A draft schedules nothing.")}, memory_values(service, draft)


def _own_draft(service: MoveService, customer_id: str, draft_id: Any) -> Optional[Draft]:
    draft = service.drafts.get(normalise_id(draft_id))
    return draft if draft is not None and draft.customer_id == customer_id else None


def update_move_draft(service: MoveService, customer_id: str, conversation: Conversation, draft_id: str,
                      moving_to: Optional[str] = None, move_out_date: Optional[str] = None,
                      move_in_date: Optional[str] = None) -> tuple[dict, dict]:
    """(result, memory values). A change gives the draft a new version that the customer must confirm again."""
    draft = _own_draft(service, customer_id, draft_id)
    if draft is None:
        return {"status": "not_found", "reason": "no_such_draft", "draft_id": normalise_id(draft_id),
                "next_step": "There is no such draft. Start the move with start_move_draft."}, {}
    changes: dict[str, Any] = {}
    for which, words, key in (("move-out", move_out_date, "move_out"), ("move-in", move_in_date, "move_in")):
        if words is None or not str(words).strip():
            continue
        day, problem = check_day(words, conversation.user_messages, service.as_of)
        if problem:
            return _date_problem(which, problem), {}
        changes[key] = day
    if moving_to is not None and str(moving_to).strip():
        to, why = resolve_destination(service, moving_to)
        if why.get("status") == "which_premises":
            return why, {}
        if to == service.service_points[draft.from_sp]["premises"]:
            return {"status": "blocked", "reason": "wrong_premise", "detail": "same_premises",
                    "next_step": "The destination is the service they are leaving. Ask where they are moving to."}, {}
        changes["to_premises"] = to
        changes["to_words"] = str(moving_to).strip()[:60]
    if not changes:
        return {"status": "unchanged", **_draft_view(service, draft),
                "next_step": "Nothing to change. Ask what the customer wants to change."}, memory_values(service, draft)
    for key, value in changes.items():
        setattr(draft, key, value)
    draft.version += 1
    view = _draft_view(service, draft)
    if draft.to_premises is None:
        return {"status": "needs_review", "reason": "wrong_premise", "detail": "destination_unresolved", **view,
                "next_step": ("The destination cannot be resolved. If the customer confirms the address, call "
                              "route_move_review with this draft_id; their current service stays on as it is.")
                }, memory_values(service, draft)
    step = ("Call submit_move_order with this draft_id now; the engine reads the new version back, both sides and "
            "both dates, and asks again.")
    if draft.order_ref:
        step += f" It changes move order {draft.order_ref}; nothing changes until the customer confirms."
    return {"status": "drafted", **view, "next_step": step}, memory_values(service, draft)


def move_facts(service: MoveService, customer_id: str, memory: dict, conversation: Conversation,
               draft: Optional[Draft]) -> dict:
    """The contract's two request facts for *draft*, from trusted data and events only."""
    if draft is None:
        return {"premise_identity_resolved": False, "effective_dates_confirmed": False}
    point = service.service_points.get(draft.from_sp) or {}
    premises = service.premises.get(draft.to_premises or "") or {}
    current_tag = memory.get("move_draft_tag") == draft.tag
    resolved = (
        point.get("customer_id") == customer_id
        and service.state[draft.from_sp]["status"] == "active"
        and premises.get("serviceable") is True
        and draft.to_premises != point.get("premises")
        and current_tag
        and memory.get("move_to") == address(premises)
    )
    earliest, latest = date_window(service.as_of)
    dates_valid = all(
        d is not None and earliest <= d <= latest and said_by_customer(d, conversation.user_messages, service.as_of)
        for d in (draft.move_out, draft.move_in)
    )
    question = conversation.confirmation_question or ""
    confirmed = (
        dates_valid
        and current_tag
        and conversation.confirmation_answered
        and draft.tag in question
        and long_date(draft.move_out) in question
        and long_date(draft.move_in) in question
    )
    return {"premise_identity_resolved": resolved, "effective_dates_confirmed": confirmed}


def _order_readback(service: MoveService, order: dict) -> dict:
    """What the move-order system reads back for an order."""
    readback = {k: order[k] for k in ("service_point", "to_premises", "move_out", "move_in")}
    if service.premises[order["to_premises"]]["order_system"] == "reads_back_closure_a_day_early":
        # The fixture's fault: this order system stores a move-out as the start
        # of that day, so the service would end a day before the confirmed date.
        readback["move_out"] = order["move_out"] - timedelta(days=1)
    return readback


def _verify(service: MoveService, order: dict, draft: Draft) -> tuple[bool, dict]:
    """move_order_receipt_verified: the read-back matches the confirmed draft and the service is still on."""
    readback = _order_readback(service, order)
    state = service.state[draft.from_sp]
    ok = (
        order["acknowledged"] is True
        and readback["service_point"] == draft.from_sp
        and readback["to_premises"] == draft.to_premises
        and readback["move_out"] == draft.move_out
        and readback["move_in"] == draft.move_in
        and state["status"] == "active"
    )
    return ok, readback


def _schedule(service: MoveService, draft: Draft, order_ref: str) -> None:
    state = service.state[draft.from_sp]
    state.update({"stays_on_through": draft.move_out, "closure_instruction": f"scheduled after {draft.move_out}",
                  "order_ref": order_ref})


def _hold(service: MoveService, draft: Draft, why: str) -> None:
    state = service.state[draft.from_sp]
    state.update({"stays_on_through": None, "closure_instruction": f"held: {why}"})


def _order_result(service: MoveService, draft: Draft, order: dict, replay: bool, effects: int) -> dict:
    return {
        "status": "succeeded",
        "order_ref": order["order_ref"],
        "order_revision": order["revision"],
        "draft_id": draft.draft_id,
        "draft_tag": draft.tag,
        "moving_out_of": service.service_label(draft.from_sp),
        "moving_to": address(service.premises[draft.to_premises]),
        "move_out_date": draft.move_out.isoformat(),
        "move_in_date": draft.move_in.isoformat(),
        "new_service_starts": draft.move_in.isoformat(),
        "current_service": service.current_service(draft.from_sp),
        "receipt_verified": True,
        "replay": replay,
        "effects": effects,
        "next_step": ("The customer has been sent the move-order reference and dates. Their current service stays on "
                      "through the move-out date; never say it is off or closed now."),
    }


def submit_move_order(service: MoveService, customer_id: str, memory: dict, conversation: Conversation,
                      draft_id: str, conversation_id: str) -> dict:
    """Send one confirmed draft to the move-order system, then verify its read-back."""
    draft = _own_draft(service, customer_id, draft_id)
    if draft is None:
        return {"status": "blocked", "reason": "wrong_premise", "detail": "no_such_draft", "effects": 0,
                "draft_id": normalise_id(draft_id), "next_step": "There is no such draft. Start with start_move_draft."}
    order = service.orders.get(draft.order_ref or "")
    if order is not None and order["draft_version"] == draft.version:
        if order["state"] == "verified":
            return _order_result(service, draft, order, replay=True, effects=0)
        return {"status": "pending", "reason": "move_order_unconfirmed", "detail": "already_sent", "effects": 0,
                "draft_id": draft.draft_id, "current_service": service.current_service(draft.from_sp),
                "next_step": ("This version was already sent and is not confirmed. Never send it again: call "
                              "check_move_order with the draft_id, then route_move_review if it stays unconfirmed.")}
    facts = move_facts(service, customer_id, memory, conversation, draft)
    reason = evaluate(facts, "request")
    if reason:
        steps = {
            "wrong_premise": ("The move's premises are not resolved, or the draft read back was not the current "
                              "version. Resolve the destination with the customer (update_move_draft) or route the "
                              "draft with route_move_review. The current service stays on."),
            "move_date_ambiguous": ("The customer did not confirm this version's dates. Call submit_move_order again "
                                    "so the engine reads both dates back and asks."),
        }
        return {"status": "blocked", "reason": reason, "facts": facts, "effects": 0, "draft_id": draft.draft_id,
                "current_service": service.current_service(draft.from_sp), "next_step": steps[reason]}
    behaviour = service.premises[draft.to_premises]["order_system"]
    amending = order is not None
    if behaviour == "never_confirms":
        _hold(service, draft, "move-order system has not confirmed")
        return {"status": "pending", "reason": "move_order_unconfirmed", "detail": "no_confirmation",
                "draft_id": draft.draft_id, "effects": 0, "current_service": service.current_service(draft.from_sp),
                "next_step": ("The move-order system has not confirmed the order. The closure instruction is held and "
                              "the current service stays on. Call check_move_order with the draft_id once; if it is "
                              "still unknown, call route_move_review. Never submit it again.")}
    if amending:
        order.update({"revision": order["revision"] + 1, "draft_version": draft.version, "move_out": draft.move_out,
                      "move_in": draft.move_in, "to_premises": draft.to_premises, "acknowledged": True})
    else:
        ref = f"AG-MOV-{_digest(conversation_id, draft.draft_id)[:6]}"
        order = {"order_ref": ref, "revision": 1, "draft_id": draft.draft_id, "draft_version": draft.version,
                 "service_point": draft.from_sp, "to_premises": draft.to_premises, "move_out": draft.move_out,
                 "move_in": draft.move_in, "acknowledged": True, "state": "committed"}
        service.orders[ref] = order
        draft.order_ref = ref
    if behaviour == "loses_acknowledgment" and draft.draft_id not in service._lost_ack_used:
        # The order system committed the order, but its acknowledgment never arrived.
        service._lost_ack_used.add(draft.draft_id)
        order["acknowledged"] = False
        order["state"] = "committed"
        _schedule(service, draft, order["order_ref"])
        return {"status": "pending", "reason": "move_order_unconfirmed", "detail": "acknowledgment_lost",
                "draft_id": draft.draft_id, "effects": 1, "current_service": service.current_service(draft.from_sp),
                "next_step": ("The move-order system did not acknowledge the order, so it is not confirmed. Call "
                              "check_move_order with the draft_id before anything else. Never submit it again.")}
    ok, readback = _verify(service, order, draft)
    receipt_facts = {"move_order_receipt_verified": ok}
    if evaluate(receipt_facts, "receipt"):
        order["state"] = "held"
        _hold(service, draft, "read-back did not match the confirmed dates")
        return {"status": "pending", "reason": "move_order_unconfirmed", "detail": "readback_mismatch",
                "draft_id": draft.draft_id, "effects": 1,
                "confirmed_move_out": draft.move_out.isoformat(),
                "readback_move_out": readback["move_out"].isoformat(),
                "current_service": service.current_service(draft.from_sp),
                "next_step": ("The move-order system read the move-out back as a different day. The closure "
                              "instruction is held, so the current service stays on as it is. Call route_move_review "
                              "with the draft_id. Never submit it again.")}
    order["state"] = "verified"
    _schedule(service, draft, order["order_ref"])
    return _order_result(service, draft, order, replay=False, effects=1)


def check_move_order(service: MoveService, customer_id: str, reference: str) -> dict:
    """Look up a move by draft id or order reference. Reconciles an unacknowledged order; submits nothing."""
    ref = normalise_id(reference)
    draft = _own_draft(service, customer_id, ref)
    if draft is None:
        order = service.orders.get(ref)
        if order is not None:
            draft = _own_draft(service, customer_id, order["draft_id"])
    if draft is None:
        return {"status": "not_found", "reason": "no_such_move", "reference": ref,
                "next_step": "There is no move with that reference on their account."}
    order = service.orders.get(draft.order_ref or "")
    behaviour = service.premises[draft.to_premises]["order_system"] if draft.to_premises else None
    if order is None:
        if behaviour == "never_confirms" and service.state[draft.from_sp]["closure_instruction"].startswith("held"):
            return {"status": "unknown", "reason": "move_order_unconfirmed", "detail": "no_confirmation",
                    "draft_id": draft.draft_id, "current_service": service.current_service(draft.from_sp),
                    "next_step": ("The order system still cannot say whether the order exists. Call route_move_review "
                                  "with the draft_id; the current service stays on. Never submit it again.")}
        return {"status": "not_submitted", "draft_id": draft.draft_id, **_draft_view(service, draft),
                "next_step": "This draft has not been sent. Nothing is scheduled; the current service is unchanged."}
    if order["state"] == "held":
        return {"status": "pending", "reason": "move_order_unconfirmed", "detail": "readback_mismatch",
                "draft_id": draft.draft_id, "current_service": service.current_service(draft.from_sp),
                "next_step": "The closure instruction is held for review. Call route_move_review if not done."}
    order["acknowledged"] = True
    ok, _ = _verify(service, order, draft)
    if not ok:
        order["state"] = "held"
        _hold(service, draft, "read-back did not match the confirmed dates")
        return {"status": "pending", "reason": "move_order_unconfirmed", "detail": "readback_mismatch",
                "draft_id": draft.draft_id, "current_service": service.current_service(draft.from_sp),
                "next_step": "Call route_move_review with the draft_id."}
    first = order["state"] != "verified"
    order["state"] = "verified"
    _schedule(service, draft, order["order_ref"])
    result = _order_result(service, draft, order, replay=not first, effects=0)
    result["acknowledged_on_check"] = first
    result["next_step"] = ("The order is confirmed; it is the same order, not a new one. The customer has been sent "
                           "the reference. The current service stays on through the move-out date.")
    return result


def route_move_review(service: MoveService, customer_id: str, draft_id: str, reason: str,
                      conversation_id: str) -> dict:
    """Route a move draft to the service lifecycle team. Holds any closure; the current service stays on."""
    draft = _own_draft(service, customer_id, draft_id)
    if draft is None:
        return {"status": "not_found", "reason": "no_such_draft", "draft_id": normalise_id(draft_id),
                "next_step": "Route needs the draft_id from start_move_draft."}
    order = service.orders.get(draft.order_ref or "")
    if order is not None and order["state"] == "verified" and order["draft_version"] == draft.version:
        return {"status": "blocked", "reason": "already_scheduled", "order_ref": order["order_ref"],
                "current_service": service.current_service(draft.from_sp),
                "next_step": "This move is confirmed and scheduled; there is nothing to review. Give the order reference."}
    key = draft.draft_id
    prior = service.reviews.get(key)
    replay = prior is not None
    if prior is None:
        prior = {"review_ref": f"AG-SLR-{_digest(conversation_id, key)[:6]}", "draft_id": draft.draft_id,
                 "team": REVIEW_TEAM, "reason": str(reason or "")[:200]}
        service.reviews[key] = prior
    if order is not None:
        order["state"] = "held"
    _hold(service, draft, f"review {prior['review_ref']}")
    service.state[draft.from_sp]["review_ref"] = prior["review_ref"]
    return {
        "status": "routed",
        **prior,
        "moving_out_of": service.service_label(draft.from_sp),
        "moving_to": address(service.premises[draft.to_premises]) if draft.to_premises else draft.to_words,
        "current_service": service.current_service(draft.from_sp),
        "closure_sent": False,
        "reply_within": REPLY_WITHIN,
        "replay": replay,
        "next_step": ("The customer has been sent the review reference. Say the current service stays on as it is and "
                      "no closure has been sent; the team contacts them. Promise no date."),
    }


def service_status(service: MoveService, customer_id: str, words: str) -> dict:
    """The current service at one of the customer's premises now, with any scheduled move."""
    sp, blocked = resolve_current(service, customer_id, words)
    if sp is None:
        return blocked
    state = service.state[sp]
    result = {"status": "read", "as_of": service.as_of.isoformat(), "current_service": service.current_service(sp)}
    if state["order_ref"]:
        order = service.orders[state["order_ref"]]
        result["move_order"] = {"order_ref": order["order_ref"], "state": order["state"],
                                "move_out_date": order["move_out"].isoformat(),
                                "moving_to": address(service.premises[order["to_premises"]]),
                                "move_in_date": order["move_in"].isoformat()}
    if state["review_ref"]:
        result["review_ref"] = state["review_ref"]
    result["next_step"] = "Report the service exactly as read: it is on now unless status says otherwise."
    return result


# ----------------------------------------------------------------------------
# The receipt the tool sends itself (TOOL_SENDS_RECEIPT)
# ----------------------------------------------------------------------------


def _day(iso: Optional[str]) -> str:
    return long_date(date.fromisoformat(iso)) if iso else "not set"


def customer_receipt(tool: str, result: dict) -> Optional[str]:
    """The message a tool sends the customer for an outcome they must see, or None."""
    status = result.get("status")
    current = result.get("current_service") or {}
    here = f"your {current.get('supply', 'supply')} at {current.get('address', 'your current address')}"
    if tool in ("submit_move_order", "check_move_order") and status == "succeeded":
        if tool == "check_move_order" and not result.get("acknowledged_on_check"):
            return None
        verb = "updated" if result.get("order_revision", 1) > 1 else "scheduled"
        again = " It was already scheduled; nothing was scheduled twice." if result.get("replay") else ""
        return (f"Move order {result['order_ref']} is {verb}. {here[0].upper()}{here[1:]} stays on through "
                f"{_day(result['move_out_date'])} and nothing changes there before then. Supply at "
                f"{result['moving_to']} starts on {_day(result['move_in_date'])}.{again}")
    if tool == "submit_move_order" and status == "pending":
        if result.get("detail") == "readback_mismatch":
            return (f"Your move (draft {result['draft_id']}) is not confirmed: the move-order system read the move-out "
                    f"back as {_day(result['readback_move_out'])}, not {_day(result['confirmed_move_out'])}. The "
                    f"closure is on hold, so {here} stays on as it is.")
        return (f"Your move (draft {result['draft_id']}) is not confirmed yet: the move-order system has not "
                f"acknowledged it. {here[0].upper()}{here[1:]} stays on as it is.")
    if tool == "route_move_review" and status == "routed":
        return (f"Passed to the Amber Grid {REVIEW_TEAM} for review: {result['review_ref']}. {here[0].upper()}"
                f"{here[1:]} stays on as it is and no closure has been sent. They reply within "
                f"{result['reply_within']}.")
    return None
