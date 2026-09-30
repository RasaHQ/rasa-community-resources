"""Northgate Bank advisor scheduling and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three request rules of the casebook contract for
``banking-advisor-appointment`` (vendored as ``lib/fixtures/case-contract.json``):

- ``purpose_matched``: the purpose the customer stated, in their own words, is
  one the team behind the slot can handle. A mortgage question never goes to
  a general branch appointment.
- ``slot_held``: the slot is held for this call by the scheduling service,
  and the hold has not lapsed. A proposed time is not a reservation.
- ``channel_confirmed``: the slot's meeting channel (branch, phone or video)
  is the one the customer asked for, a branch visit is step-free when the
  customer needs step-free access, and the slot is the one the engine's
  confirmation gate read back.

Facts are computed here from trusted data and from the customer's own words
(the tracker's user messages; on a voice call, what speech-to-text heard). The
model supplies a purpose word, a slot id copied from a search result and
search filters. It never supplies a fact, a customer id or a booking outcome.
When the model's purpose word differs from the purpose the customer stated,
the call is refused, so a specialist question cannot be quietly turned into
a general appointment. A fact that is not exactly ``True`` fails its rule, as
in the lab's ``evaluate``.

Scheduling state (holds, bookings, callbacks) lives in an in-process service
with one copy of the fixture per conversation, so every scripted call starts
from the same diary.

The organisation guard runs at import. It is an allowlist, not a list of real
names: the fixture's organisation must be exactly the casebook contract's
fictional organisation, marked ``(fictional)``, and the contract must be the
casebook's authored synthetic fixture.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "appointments.json"

PURPOSES = ("mortgage", "investments", "business_banking", "everyday_banking")
CHANNELS = ("branch", "phone", "video")
MAX_PROPOSALS = 3
# Mantle cuts a memory value at 100 characters in the prompt without saying so
# (found in the GPT quote and diagnostics builds); every memory value is kept
# under this.
MEMORY_VALUE_LIMIT = 100


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
    for team in data.get("teams", {}).values():
        label = team["label"]
        other = re.search(r"\b([A-Z][a-z]+ (?:Bank|Building Society|Banking Group))\b", label)
        if other and other.group(1) != contract["organisation"]:
            raise FictionalOrganisationError(f"team label names another organisation: {label!r}")


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


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8].upper()


def spoken_reference(prefix: str, *parts: str) -> str:
    """A reference a voice agent can read out: letters, then six digits ('APT-482913')."""
    return f"{prefix}-{int(hashlib.sha256('|'.join(parts).encode()).hexdigest(), 16) % 1_000_000:06d}"


# ----------------------------------------------------------------------------
# The customer's own words: purpose, channel and step-free access
# ----------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9']+")


def _words(text: Any) -> list[str]:
    return [w.replace("'", "") for w in _WORD_RE.findall(str(text or "").lower().replace("-", " "))]


# Longer phrases win over the shorter ones inside them ("business account" is
# business banking, not everyday banking; "video call" is not a phone call;
# "call me back" names no meeting channel).
_PURPOSE_WORDS = {
    "mortgage": ("mortgage", "mortgages", "remortgage", "remortgaging", "re mortgage", "home loan",
                 "buying a house", "buying a home", "first home", "fixed rate", "fix my rate"),
    "investments": ("invest", "investing", "investment", "investments", "isa", "isas", "i s a",
                    "stocks and shares", "pension", "pensions", "retirement", "savings"),
    "business_banking": ("business", "business account", "business loan", "my company", "limited company",
                         "sole trader"),
    "everyday_banking": ("account", "joint account", "current account", "savings account", "open an account",
                         "bank account", "debit card", "power of attorney", "change of address"),
}
_CHANNEL_WORDS = {
    "video": ("video", "video call", "on video"),
    "phone": ("phone", "phone call", "telephone", "by phone", "over the phone", "ring me", "call", "a call"),
    "branch": ("branch", "in person", "come in", "come into", "go in", "go into", "pop in", "pop into", "visit",
               "face to face", "in branch", "kingsmere", "farrowdale", "ashcombe"),
    # Named so its spans swallow "call" without naming a channel.
    "_callback": ("call me back", "call back", "callback", "calls me back", "ring me back"),
}
_STEP_FREE_WORDS = {
    "step_free": ("step free", "stepfree", "wheelchair", "accessible", "accessibility", "mobility",
                  "cant manage steps", "cant do steps", "cant manage stairs", "no steps", "no stairs",
                  "level access"),
}
_NEGATOR_RE = re.compile(r"\b(?:not|isnt|arent|wasnt|never|without|wont|dont want|dont need|instead of|rather than)\b")


def _mentions(text: str, vocabulary: dict[str, tuple[str, ...]]) -> list[tuple[int, str, bool]]:
    """(position, kind, negated) for each vocabulary phrase in *text*, longest phrases first."""
    words = _words(text)
    spans: list[tuple[int, int, str]] = []
    phrases = sorted(((tuple(p.split()), kind) for kind, ps in vocabulary.items() for p in ps),
                     key=lambda item: -len(item[0]))
    taken = [False] * len(words)
    for target, kind in phrases:
        n = len(target)
        for i in range(len(words) - n + 1):
            if tuple(words[i:i + n]) == target and not any(taken[i:i + n]):
                spans.append((i, i + n, kind))
                for j in range(i, i + n):
                    taken[j] = True
    found = []
    for start, _end, kind in sorted(spans):
        before = " ".join(words[max(0, start - 3):start])
        found.append((start, kind, bool(_NEGATOR_RE.search(before))))
    return found


def _latest_named(user_texts: Iterable[str], vocabulary: dict) -> tuple[bool, Optional[str]]:
    """(named, kind) from the customer's latest message that names a kind.

    ``kind`` is None when that message names more than one kind without a
    negation (ambiguous), or only negated ones.
    """
    named, latest = False, None
    for text in user_texts:
        mentions = [m for m in _mentions(text, vocabulary) if not m[1].startswith("_")]
        if not mentions:
            continue
        named = True
        positive = {kind for _, kind, negated in mentions if not negated}
        latest = positive.pop() if len(positive) == 1 else None
    return named, latest


def stated_purpose(user_texts: Iterable[str]) -> Optional[str]:
    """The purpose in the customer's latest message that names one, or None."""
    return _latest_named(user_texts, _PURPOSE_WORDS)[1]


def stated_channel(user_texts: Iterable[str]) -> Optional[str]:
    """The meeting channel in the customer's latest message that names one, or None."""
    return _latest_named(user_texts, _CHANNEL_WORDS)[1]


def step_free_needed(user_texts: Iterable[str]) -> bool:
    """True when the customer's latest message about access asks for step-free access."""
    return _latest_named(user_texts, _STEP_FREE_WORDS)[1] == "step_free"


def normalise_purpose(value: Any) -> Optional[str]:
    text = "_".join(_words(value))
    if text in PURPOSES:
        return text
    named, kind = _latest_named([str(value or "")], _PURPOSE_WORDS)
    return kind if named else None


def normalise_channel(value: Any) -> Optional[str]:
    text = " ".join(_words(value))
    if text in CHANNELS:
        return text
    if text in ("in person", "branch visit", "visit"):
        return "branch"
    named, kind = _latest_named([str(value or "")], _CHANNEL_WORDS)
    return kind if named and kind in CHANNELS else None


def _compact(value: Any) -> str:
    return "".join(_words(value))


def match_branch(value: Any, data: dict) -> Optional[str]:
    """Branch key for a spoken branch name ("Ash Combe", "Kingsmere branch"), or None.

    Speech-to-text splits and respells place names, so word boundaries are
    ignored and a close spelling (difflib ratio 0.8 or more) is accepted.
    """
    said = _compact(value).removesuffix("branch")
    if not said:
        return None
    best, score = None, 0.0
    for key, branch in data["branches"].items():
        name = _compact(branch["name"])
        ratio = 1.0 if said == name else difflib.SequenceMatcher(None, said, name).ratio()
        if ratio > score:
            best, score = key, ratio
    return best if score >= 0.8 else None


# ----------------------------------------------------------------------------
# Time
# ----------------------------------------------------------------------------

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september",
           "october", "november", "december")


def _as_of(data: dict) -> datetime:
    return datetime.fromisoformat(data["as_of"])


def spoken_time(ts: str) -> str:
    """'2026-10-08T14:30:00+01:00' -> 'Thursday 8 October at 2:30 pm'."""
    t = datetime.fromisoformat(ts)
    hour = t.strftime("%I").lstrip("0")
    minutes = t.strftime("%M")
    clock = f"{hour} {t.strftime('%p').lower()}" if minutes == "00" else f"{hour}:{minutes} {t.strftime('%p').lower()}"
    return f"{t.strftime('%A')} {t.day} {t.strftime('%B')} at {clock}"


def parse_day(value: Any, data: dict) -> Optional[date]:
    """A weekday name, an ISO date or '8 October' -> the date on or after the fixture clock."""
    text = str(value or "").strip().lower()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    today = _as_of(data).date()
    words = _words(text)
    for word in words:
        if word in _WEEKDAYS:
            ahead = (_WEEKDAYS.index(word) - today.weekday()) % 7
            return today + timedelta(days=ahead or 7) if "next" in words and ahead == 0 else today + timedelta(days=ahead)
    day = next((int(re.sub(r"\D", "", w)) for w in words if re.fullmatch(r"\d{1,2}(st|nd|rd|th)?", w)), None)
    month = next((_MONTHS.index(w) + 1 for w in words if w in _MONTHS), None)
    if day and month:
        return date(today.year, month, day)
    if day:
        return date(today.year, today.month, day)
    return None


def part_of_day_matches(ts: str, part: Any) -> bool:
    words = set(_words(part))
    if not words:
        return True
    hour = datetime.fromisoformat(ts).hour
    if "morning" in words:
        return hour < 12
    if "afternoon" in words:
        return hour >= 12
    return True


# ----------------------------------------------------------------------------
# Scheduling service: the fixture copy for one conversation
# ----------------------------------------------------------------------------


class SchedulingService:
    """The advisor diary for one conversation: slots, holds, bookings and callbacks."""

    def __init__(self, data: Optional[dict] = None) -> None:
        self.data = data or load_data()
        self.holds: dict[str, dict] = {}        # slot_id -> hold
        self.hold_attempts: dict[str, int] = {}
        self.bookings: dict[str, dict] = {}     # slot_id -> booking
        self.callbacks: list[dict] = []

    def slot(self, slot_id: Any) -> Optional[dict]:
        key = str(slot_id or "").strip().upper()
        slot = self.data["slots"].get(key)
        return {"slot_id": key, **slot} if slot else None

    def team(self, slot: dict) -> dict:
        return self.data["teams"][slot["team"]]

    def branch(self, slot: dict) -> Optional[dict]:
        key = self.team(slot).get("branch") if slot["channel"] == "branch" else None
        return self.data["branches"][key] if key else None

    def active_hold(self) -> Optional[str]:
        return next(iter(self.holds), None)

    def capable(self, slot: dict, purpose: Optional[str]) -> bool:
        return bool(purpose) and purpose in self.team(slot)["capabilities"]

    def channel_spoken(self, slot: dict) -> str:
        if slot["channel"] == "branch":
            return f"in person at the {self.branch(slot)['name']} branch"
        return {"phone": "by phone", "video": "by video call"}[slot["channel"]]

    def view(self, slot: dict) -> dict:
        branch = self.branch(slot)
        return {
            "slot_id": slot["slot_id"],
            "team": self.team(slot)["label"],
            "channel": slot["channel"],
            "channel_spoken": self.channel_spoken(slot),
            **({"branch": branch["name"], "step_free": branch["step_free"]} if branch else {}),
            **({"access_note": branch["access_note"]} if branch and branch.get("access_note") else {}),
            "starts_at": slot["starts_at"],
            "starts_at_spoken": spoken_time(slot["starts_at"]),
        }


_SERVICES: dict[str, SchedulingService] = {}


def service_for(conversation_id: str) -> SchedulingService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = SchedulingService()
    return _SERVICES[conversation_id]


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------

NEXT_STEP = {
    "purpose_not_stated": (
        "The customer has not said, in their own words, what the appointment is about. Ask them. "
        "Do not guess and do not offer a general appointment instead."
    ),
    "purpose_mismatch": (
        "The customer asked about the stated_purpose, not the purpose you passed. Use the purpose "
        "they stated. Never book a different kind of appointment in its place."
    ),
    "wrong_advisor_capability": (
        "This team cannot handle the customer's stated purpose. Do not book it. Search again for "
        "the stated purpose and offer a capable team or a callback."
    ),
    "wrong_meeting_channel": (
        "This slot's meeting channel is not what the customer asked for, or the branch is not "
        "step-free and the customer needs step-free access. Do not book it. Offer a slot on the "
        "channel they asked for, or a callback."
    ),
    "slot_not_held": (
        "The slot is not held for this call, so nothing is reserved. Do not say it is booked. "
        "Hold a slot the customer picked, or offer the other proposed times."
    ),
}


def _blocked(reason: str, detail: Optional[str] = None, **extra: Any) -> dict:
    return {
        "status": "blocked",
        "reason": reason,
        **({"detail": detail} if detail else {}),
        "effects": 0,
        **extra,
        "next_step": NEXT_STEP[detail if detail in NEXT_STEP else reason],
    }


def _purpose_check(user_texts: list[str], purpose: Any) -> tuple[Optional[str], Optional[dict]]:
    """(stated purpose, None) or (None, blocked result)."""
    stated = stated_purpose(user_texts)
    requested = normalise_purpose(purpose)
    if stated is None:
        return None, _blocked("wrong_advisor_capability", "purpose_not_stated", requested_purpose=requested,
                              facts={"purpose_matched": False})
    if requested is not None and requested != stated:
        return None, _blocked("wrong_advisor_capability", "purpose_mismatch", requested_purpose=requested,
                              stated_purpose=stated, facts={"purpose_matched": False})
    return stated, None


def _channel_ok(service: SchedulingService, slot: dict, user_texts: list[str]) -> bool:
    wanted = stated_channel(user_texts)
    if wanted is not None and slot["channel"] != wanted:
        return False
    if slot["channel"] == "branch" and step_free_needed(user_texts):
        return bool(service.branch(slot)["step_free"])
    return True


def find_advisor_slots(service: SchedulingService, customer_id: Optional[str], user_texts: list[str],
                       purpose: Any, channel: Any = None, branch: Any = None, day: Any = None,
                       part_of_day: Any = None) -> dict:
    """Proposed times from teams that can handle the stated purpose. Proposals reserve nothing."""
    if not customer_id:
        return {"status": "refused", "reason": "no_session_customer", "effects": 0,
                "next_step": "The session has no signed-in customer. Do not search or book."}
    stated, refusal = _purpose_check(user_texts, purpose)
    if refusal:
        return refusal
    data = service.data
    wanted_channel = normalise_channel(channel) or stated_channel(user_texts)
    wanted_branch = match_branch(branch, data) if branch else None
    wanted_day = parse_day(day, data)
    step_free = step_free_needed(user_texts)
    capable = [s for s in (service.slot(k) for k in sorted(data["slots"])) if service.capable(s, stated)
               and s["slot_id"] not in service.bookings]
    capable.sort(key=lambda s: s["starts_at"])

    def fits(s: dict, *, use_branch: bool = True, use_day: bool = True, use_channel: bool = True) -> bool:
        b = service.branch(s)
        if use_channel and wanted_channel and s["channel"] != wanted_channel:
            return False
        if use_branch and wanted_branch and (s["channel"] != "branch" or service.team(s)["branch"] != wanted_branch):
            return False
        if use_day and wanted_day and datetime.fromisoformat(s["starts_at"]).date() != wanted_day:
            return False
        if use_day and not part_of_day_matches(s["starts_at"], part_of_day):
            return False
        if b is not None and step_free and not b["step_free"]:
            return False
        return True

    matches = [s for s in capable if fits(s)]
    filters = {k: v for k, v in (("channel", wanted_channel), ("branch", data["branches"][wanted_branch]["name"]
               if wanted_branch else None), ("day", wanted_day.isoformat() if wanted_day else None),
               ("part_of_day", part_of_day or None), ("step_free_required", step_free or None)) if v}
    base = {"purpose": stated, "purpose_label": data["purposes"][stated], "filters": filters}
    if matches:
        return {
            "status": "proposed",
            **base,
            "proposals": [service.view(s) for s in matches[:MAX_PROPOSALS]],
            "reserved": False,
            "effects": 0,
            "next_step": (
                "These are proposed times, not reservations. Offer them and ask which one the customer "
                "wants. Hold only the slot they pick, with hold_slot."
            ),
        }
    if branch and wanted_branch is None:
        detail = "unknown_branch"
    elif wanted_branch and not any(service.team(s)["branch"] == wanted_branch for s in capable):
        detail = "no_capable_team_at_branch"
    else:
        detail = "no_slot_matches"
    alternatives = [s for s in capable if fits(s, use_branch=False, use_day=False, use_channel=False)]
    return {
        "status": "no_capable_slot",
        "detail": detail,
        **base,
        "proposals": [],
        "alternatives": [service.view(s) for s in alternatives[:MAX_PROPOSALS]],
        "callback_available": True,
        "reserved": False,
        "effects": 0,
        "next_step": (
            "No team that can handle this purpose has a slot matching the request. Say so plainly. "
            "Offer the alternatives (other channels, branches or days from a capable team) or a callback "
            "with request_callback. Never offer or book a general appointment instead."
        ),
    }


def hold_slot(service: SchedulingService, customer_id: Optional[str], user_texts: list[str], slot_id: Any,
              purpose: Any = None) -> dict:
    """Hold one proposed slot for this call, after checking purpose and channel."""
    slot = service.slot(slot_id)
    if not customer_id or slot is None:
        return {"status": "not_held", "reason": "slot_not_held", "detail": "unknown_slot", "effects": 0,
                "slot_id": str(slot_id or ""), "next_step": NEXT_STEP["slot_not_held"]}
    stated, refusal = _purpose_check(user_texts, purpose)
    if refusal:
        return {**refusal, "slot_id": slot["slot_id"]}
    facts = {"purpose_matched": service.capable(slot, stated), "slot_held": True,
             "channel_confirmed": _channel_ok(service, slot, user_texts)}
    reason = evaluate(facts)
    if reason:
        return _blocked(reason, slot_id=slot["slot_id"], stated_purpose=stated, facts=facts,
                        slot=service.view(slot))
    active = service.active_hold()
    if active and active != slot["slot_id"]:
        return {"status": "not_held", "reason": "another_hold_active", "effects": 0, "slot_id": slot["slot_id"],
                "active_hold": active,
                "next_step": "Only one slot can be held per call. Call release_hold for the active hold first."}
    if slot["slot_id"] in service.bookings:
        return {"status": "not_held", "reason": "slot_not_held", "detail": "already_booked", "effects": 0,
                "slot_id": slot["slot_id"], "next_step": "This slot is already booked on this call."}
    if slot.get("hold") == "taken":
        return {"status": "not_held", "reason": "slot_not_held", "detail": "taken_since_proposed", "effects": 0,
                "slot_id": slot["slot_id"], "slot": service.view(slot),
                "next_step": ("Someone else took this time after it was proposed, so nothing is held. Say so "
                              "and offer the other proposed times, or search again.")}
    service.hold_attempts[slot["slot_id"]] = service.hold_attempts.get(slot["slot_id"], 0) + 1
    hold = {"hold_id": f"NGB-HLD-{_digest(customer_id, slot['slot_id'], str(service.hold_attempts[slot['slot_id']]))}",
            "slot_id": slot["slot_id"], "purpose": stated, "attempt": service.hold_attempts[slot["slot_id"]]}
    service.holds = {slot["slot_id"]: hold}
    return {
        "status": "held",
        "hold_id": hold["hold_id"],
        "purpose": stated,
        "purpose_label": service.data["purposes"][stated],
        "slot": service.view(slot),
        "reserved": False,
        "effects": 0,
        "next_step": (
            "The slot is held, not booked. Call book_appointment with this slot_id now; the engine reads "
            "the team, channel and time back and asks the customer to confirm."
        ),
    }


def release_hold(service: SchedulingService, slot_id: Any) -> dict:
    key = str(slot_id or "").strip().upper()
    if key not in service.holds:
        return {"status": "no_hold", "slot_id": key, "active_hold": service.active_hold(), "effects": 0,
                "next_step": "Nothing is held under this slot_id."}
    service.holds.pop(key)
    return {"status": "released", "slot_id": key, "effects": 0,
            "next_step": "The hold is released. Search again for what the customer now needs."}


def book_appointment(service: SchedulingService, customer_id: Optional[str], user_texts: list[str],
                     read_back_slot_id: Optional[str], slot_id: Any, conversation_id: str = "offline") -> dict:
    """Book the held slot the engine read back, and return the receipt."""
    slot = service.slot(slot_id)
    if not customer_id or slot is None:
        return _blocked("slot_not_held", "unknown_slot", slot_id=str(slot_id or ""), facts={"slot_held": False})
    stated = stated_purpose(user_texts)
    hold = service.holds.get(slot["slot_id"])
    lapsed = hold is not None and slot.get("hold") == "lapses_once" and hold["attempt"] == 1
    if lapsed:
        service.holds.pop(slot["slot_id"])
    facts = {
        "purpose_matched": service.capable(slot, stated),
        "slot_held": hold is not None and not lapsed and read_back_slot_id == slot["slot_id"],
        "channel_confirmed": read_back_slot_id == slot["slot_id"] and _channel_ok(service, slot, user_texts),
    }
    reason = evaluate(facts)
    if reason:
        detail = "hold_lapsed" if lapsed and reason == "slot_not_held" else None
        return _blocked(reason, detail, slot_id=slot["slot_id"], stated_purpose=stated, facts=facts,
                        slot=service.view(slot),
                        **({"next_step_detail": "The hold lapsed before the booking went through. Nothing is "
                            "booked. Tell the customer, hold the slot again if they still want it, and ask "
                            "again."} if detail else {}))
    if slot["slot_id"] in service.bookings:
        booking = service.bookings[slot["slot_id"]]
        return {**booking, "effects": 0, "replay": True}
    service.holds.pop(slot["slot_id"], None)
    view = service.view(slot)
    booking = {
        "status": "succeeded",
        "reason": "verified_fixture_receipt",
        "booking_reference": spoken_reference("APT", conversation_id, customer_id, slot["slot_id"]),
        "purpose": stated,
        "purpose_label": service.data["purposes"][stated],
        **view,
        "advice_given": None,
        "effects": 1,
        "replay": False,
        "facts": facts,
        "next_step": (
            "Say the booking reference, the purpose, the channel and the time in your reply before you do "
            "anything else. Booking an appointment is not advice: the advisor advises at the meeting."
        ),
    }
    service.bookings[slot["slot_id"]] = booking
    return booking


def request_callback(service: SchedulingService, customer_id: Optional[str], user_texts: list[str],
                     purpose: Any, preferred_time: Any = None, conversation_id: str = "offline") -> dict:
    """Ask a team that can handle the stated purpose to call the customer. Consumes no slot."""
    if not customer_id:
        return {"status": "refused", "reason": "no_session_customer", "effects": 0,
                "next_step": "The session has no signed-in customer."}
    stated, refusal = _purpose_check(user_texts, purpose)
    if refusal:
        return refusal
    # A central team when there is one (every purpose but everyday banking has one), else a branch team.
    teams = sorted((t for t in service.data["teams"].values() if stated in t["capabilities"]),
                   key=lambda t: t["branch"] is not None)
    team = teams[0]
    request = {
        "status": "requested",
        "callback_reference": spoken_reference("CB", conversation_id, customer_id, stated),
        "purpose": stated,
        "purpose_label": service.data["purposes"][stated],
        "team": team["label"],
        "preferred_time": " ".join(str(preferred_time or "").split())[:80] or None,
        "slot_reserved": False,
        "effects": 1,
        "next_step": ("Give the callback reference and say the team will phone within two working days to "
                      "arrange the appointment. Nothing is booked yet."),
    }
    service.callbacks.append(request)
    return request


def memory_values(service: SchedulingService, slot_id: Optional[str], purpose: Optional[str]) -> dict:
    """The short fields the engine's confirmation question reads back, each under the memory limit."""
    if not slot_id:
        return {"held_slot_id": "", "held_team_label": "", "held_purpose_label": "", "held_slot_label": ""}
    slot = service.slot(slot_id)
    team = service.team(slot)["label"]
    values = {
        "held_slot_id": slot["slot_id"],
        "held_team_label": team[0].upper() + team[1:],
        "held_purpose_label": service.data["purposes"].get(purpose or "", ""),
        "held_slot_label": f"{service.channel_spoken(slot)} on {spoken_time(slot['starts_at'])}",
    }
    return {k: v[:MEMORY_VALUE_LIMIT] for k, v in values.items()}


def session_profile(customer_id: str = SESSION_CUSTOMER_ID, data: Optional[dict] = None) -> dict:
    data = data or load_data()
    person = data["customers"][customer_id]
    return {"customer_id": customer_id, "first_name": person["first_name"]}
