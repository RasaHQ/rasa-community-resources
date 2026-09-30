"""Cedar Clinic appointment reminders: bookings, the reminder ledger, delivery and the case guard. No Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the casebook contract for ``reminder-deduplication`` (vendored
as ``lib/fixtures/case-contract.json``) whenever a reminder is queued, and
again at delivery:

- ``appointment_revision_current`` (``obsolete_appointment``): the reminder
  is for the booking's current revision. When the words that name the
  appointment carry a time or date, it must be the current one: a time from
  an earlier version of the booking is refused, never silently swapped. An
  appointment with a change request open has its reminders paused, so no
  revision of it is current for reminders. At delivery the booking is read
  again: a revision that changed after the reminder was queued is suppressed.
- ``reminder_not_sent`` (``duplicate_reminder``): no reminder for this
  appointment revision has been delivered, and none is in flight with its
  delivery unknown. The reminder's identity is the appointment revision, so
  a queued reminder for the same revision is the same reminder, never a
  second one.
- ``recipient_channel_confirmed`` (``unconfirmed_contact_channel``): the
  reminder goes to the patient's SMS number on file, confirmed and consented
  for reminders. A number or address typed in the chat, or a contact on file
  that is not confirmed, is refused.

Delivery is kept apart from attendance. A delivered reminder records only
that the text reached the number; the patient's confirmation is recorded
separately, from the patient's own reply, and only for the current revision.

Facts are computed here from trusted data and the conversation's events. A
fact that is not exactly ``True`` fails its rule, as in the lab's
``evaluate``.

The organisation guard runs at import and is an allowlist: the fixture's
organisation must be the casebook contract's own fictional clinic, marked
fictional, and so must every other organisation field in the fixture.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "cedar_reminders.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (rasa/mantle/prompts/memory_lines.py,
# MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5; found in the GPT quote and
# diagnostics builds). Every value a tool writes to memory is one short field;
# tests/test_guard.py builds every value the fixture allows and checks them.
MEMORY_VALUE_LIMIT = 100

# The tools send the patient the reminder, the delivery notice, the attendance
# receipt and the change-request reference themselves through ToolContext.send
# (found in the HarborCover claim-intake build: a silent complete_skill
# otherwise hides the receipt). The `receipt-in-result-only` variant sets this
# to False.
TOOL_SENDS_RECEIPT = True

# Skill memory keys the tools write (skills/appointment_reminders/memory.yml).
MEMORY_KEYS = ("reminder_ref", "reminder_for", "reminder_time", "reminder_delivery", "reminder_attendance")

# Organisation fields the allowlist checks, wherever they appear in the fixture.
ORGANISATION_KEYS = ("organisation", "clinic", "provider", "company", "vendor", "operator", "carrier", "gateway")

# The contract's question, closing every reminder the tool sends.
REMINDER_QUESTION = ("This is a reminder for the appointment time you selected. Would you like to confirm or "
                     "change it?")


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
SESSION_PATIENT_ID = _DATA["session_patient_id"]
AS_OF = datetime.fromisoformat(_DATA["as_of"])
SCHEDULING_DESK = _DATA["scheduling_team"]["desk"]
REPLY_WITHIN = _DATA["scheduling_team"]["reply_within"]


def load_contract() -> dict:
    return copy.deepcopy(_CONTRACT)


def load_data() -> dict:
    return copy.deepcopy(_DATA)


def rules(phase: str, contract: Optional[dict] = None) -> list[dict]:
    contract = contract or _CONTRACT
    return [rule for rule in contract["rules"] if rule["phase"] == phase]


def evaluate(facts: dict, phase: str = "request", contract: Optional[dict] = None) -> Optional[str]:
    """First failing rule's reason for *phase*, or None. Exactly ``True`` passes."""
    for rule in rules(phase, contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


# ----------------------------------------------------------------------------
# Apostrophes. GPT-5.5 writes typographic ones ("I’ll", "can’t"); every
# pattern below accepts both, and text is also normalised before matching.
# ----------------------------------------------------------------------------

APOS = "['’]"
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})


def plain(text: Any) -> str:
    return str(text or "").translate(_APOSTROPHES)


# ----------------------------------------------------------------------------
# Times and dates in words
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
_MONTH_DAY_RE = re.compile(rf"\b{_MONTH}\.?\s+(\d{{1,2}}){_ORD}\b", re.IGNORECASE)
_DAY_MONTH_RE = re.compile(rf"\b(\d{{1,2}}){_ORD}\s+(?:of\s+)?{_MONTH}\b", re.IGNORECASE)
_BARE_ORDINAL_RE = re.compile(r"\bthe\s+(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE)
_WEEKDAY_RE = re.compile(r"\b(" + "|".join(WEEKDAYS) + r")\b", re.IGNORECASE)
_CLOCK_RE = re.compile(r"\b(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?)?(?![\w.])", re.IGNORECASE)
_HOUR_RE = re.compile(r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)(?!\w)", re.IGNORECASE)
_AT_HOUR_RE = re.compile(r"\bat\s+(\d{1,2})(?:\s*o'?clock)?\b(?!\s*[:./]|\s*(?:st|nd|rd|th)\b|\s+" + _MONTH + r")",
                         re.IGNORECASE)


@dataclass(frozen=True)
class When:
    """The dates, weekdays and clock times a piece of text names."""

    dates: frozenset = frozenset()
    weekdays: frozenset = frozenset()
    bare_days: frozenset = frozenset()
    # (hour 0-23, minute, exact): exact is False for a clock time with no am/pm,
    # which matches the hour in either half of the day.
    times: frozenset = frozenset()

    @property
    def empty(self) -> bool:
        return not (self.dates or self.weekdays or self.bare_days or self.times)

    def matches(self, starts: datetime) -> bool:
        if self.dates and starts.date() not in self.dates:
            return False
        if self.weekdays and starts.weekday() not in self.weekdays:
            return False
        if self.bare_days and starts.day not in self.bare_days:
            return False
        for hour, minute, exact in self.times:
            if minute != starts.minute:
                return False
            if exact and hour != starts.hour:
                return False
            if not exact and hour % 12 != starts.hour % 12:
                return False
        return True


def _year_for(month: int, day: int, as_of: date) -> Optional[date]:
    try:
        candidate = date(as_of.year, month, day)
        return candidate if candidate >= as_of - timedelta(days=60) else date(as_of.year + 1, month, day)
    except ValueError:
        return None


def read_when(text: Any, as_of: datetime = AS_OF) -> When:
    t = plain(text)
    dates: set[date] = set()
    for m in _ISO_RE.finditer(t):
        try:
            dates.add(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            pass
    for m in _MONTH_DAY_RE.finditer(t):
        d = _year_for(MONTHS[m.group(1).lower()], int(m.group(2)), as_of.date())
        if d:
            dates.add(d)
    for m in _DAY_MONTH_RE.finditer(t):
        d = _year_for(MONTHS[m.group(2).lower()], int(m.group(1)), as_of.date())
        if d:
            dates.add(d)
    lowered = t.lower()
    if re.search(r"\btomorrow\b", lowered):
        dates.add(as_of.date() + timedelta(days=1))
    weekdays = {WEEKDAYS[w.lower()] for w in _WEEKDAY_RE.findall(t)}
    bare = {int(m.group(1)) for m in _BARE_ORDINAL_RE.finditer(t)} if not dates else set()
    times: set[tuple[int, int, bool]] = set()
    spans: list[tuple[int, int]] = []
    for m in _CLOCK_RE.finditer(t):
        hour, minute, half = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower().replace(".", "")
        if hour > 23 or minute > 59:
            continue
        spans.append(m.span())
        if half:
            times.add(((hour % 12) + (12 if half.startswith("p") else 0), minute, True))
        else:
            times.add((hour, minute, hour > 12 or hour == 0))
    for m in _HOUR_RE.finditer(t):
        if any(s <= m.start() < e for s, e in spans):
            continue
        hour, half = int(m.group(1)), m.group(2).lower().replace(".", "")
        if 1 <= hour <= 12:
            times.add(((hour % 12) + (12 if half.startswith("p") else 0), 0, True))
    for m in _AT_HOUR_RE.finditer(t):
        if any(s <= m.start() < e for s, e in spans):
            continue
        hour = int(m.group(1))
        if 1 <= hour <= 12:
            times.add((hour, 0, False))
    if re.search(r"\bnoon\b", lowered):
        times.add((12, 0, True))
    return When(frozenset(dates), frozenset(weekdays), frozenset(bare), frozenset(times))


def long_when(starts: datetime) -> str:
    """'Thursday 8 October 2026 at 2:15 pm'."""
    hour = starts.hour % 12 or 12
    half = "am" if starts.hour < 12 else "pm"
    return f"{starts:%A} {starts.day} {starts:%B %Y} at {hour}:{starts.minute:02d} {half}"


def short_when(starts: datetime) -> str:
    """'Thu 8 Oct, 2:15 pm'."""
    hour = starts.hour % 12 or 12
    half = "am" if starts.hour < 12 else "pm"
    return f"{starts:%a} {starts.day} {starts:%b}, {hour}:{starts.minute:02d} {half}"


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8].upper()


def reminder_ref(appointment_id: str, revision: int) -> str:
    """A reminder's identity is its appointment revision: one reference per revision, never per send."""
    return f"CC-RMD-{_digest(appointment_id, revision)[:6]}"


def normalise_id(value: Any) -> str:
    return re.sub(r"[^A-Z0-9-]", "", re.sub(r"[\s_]+", "-", str(value or "").strip().upper()))


def digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


# ----------------------------------------------------------------------------
# The conversation, as the tools see it (built from tracker events)
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Conversation:
    # The patient's messages in order, and for each reminder reference a tool
    # sent in this conversation, how many patient messages came before it.
    user_messages: tuple[str, ...] = field(default_factory=tuple)
    reminders_sent_at: tuple[tuple[str, int], ...] = field(default_factory=tuple)

    def replies_after(self, ref: str) -> tuple[str, ...]:
        """The patient's messages after the latest reminder with *ref* sent in this conversation, or all of them."""
        positions = [pos for r, pos in self.reminders_sent_at if r == ref]
        return self.user_messages[positions[-1]:] if positions else self.user_messages


# ----------------------------------------------------------------------------
# Cedar Clinic's systems for one conversation
# ----------------------------------------------------------------------------


@dataclass
class Entry:
    """One reminder in the ledger: one appointment revision."""

    ref: str
    appointment_id: str
    revision: int
    starts: datetime
    state: str  # queued | delivered | unknown | failed | suppressed
    queued_at: Optional[str] = None
    delivered_at: Optional[str] = None
    attempts: int = 0
    deliveries: int = 0  # what the gateway really delivered, known or not
    why: Optional[str] = None

    def view(self) -> dict:
        return {"reminder_ref": self.ref, "revision": self.revision, "for_time": self.starts.isoformat(timespec="minutes"),
                "delivery": self.state, "delivered_at": self.delivered_at, "attempts": self.attempts,
                **({"why": self.why} if self.why else {})}


class ReminderService:
    """Cedar Clinic's booking system, reminder ledger and text gateway for one conversation."""

    def __init__(self, data: Optional[dict] = None, as_of: datetime = AS_OF) -> None:
        self.data = data or load_data()
        self.as_of = as_of
        self.patients: dict[str, dict] = self.data["patients"]
        self.appointments: dict[str, dict] = self.data["appointments"]
        for appt in self.appointments.values():
            for rev in appt["revisions"]:
                rev["starts"] = datetime.fromisoformat(rev["starts"]) if isinstance(rev["starts"], str) else rev["starts"]
        self.ledger: dict[tuple[str, int], Entry] = {}
        for item in self.data.get("reminder_ledger", []):
            starts = self.revision(item["appointment_id"], item["revision"])["starts"]
            delivered = 1 if item["state"] == "delivered" else 0
            self.ledger[(item["appointment_id"], item["revision"])] = Entry(
                ref=reminder_ref(item["appointment_id"], item["revision"]), appointment_id=item["appointment_id"],
                revision=item["revision"], starts=starts, state=item["state"], queued_at=item.get("queued_at"),
                delivered_at=item.get("delivered_at"), attempts=item.get("attempts", 0), deliveries=delivered,
            )
        # Attendance, per appointment revision, kept apart from delivery.
        self.attendance: dict[tuple[str, int], str] = {}
        self.change_requests: dict[str, dict] = {}
        # Every queued attempt, in order, for the case metric.
        self.attempts: list[dict] = []
        self._first_attempt_used: set[str] = set()
        self._rescheduled: set[str] = set()

    # -- bookings -----------------------------------------------------------

    def revision(self, appointment_id: str, number: int) -> dict:
        return next(r for r in self.appointments[appointment_id]["revisions"] if r["revision"] == number)

    def current(self, appointment_id: str) -> dict:
        return self.appointments[appointment_id]["revisions"][-1]

    def own_appointments(self, patient_id: str) -> list[str]:
        return sorted(a for a, v in self.appointments.items() if v["patient_id"] == patient_id)

    def label(self, appointment_id: str) -> str:
        appt = self.appointments[appointment_id]
        return f"{appt['kind']} with {appt['with']}"

    def reschedule(self, appointment_id: str, starts: datetime, why: str) -> dict:
        """The booking system moves an appointment: a new revision, the old one superseded."""
        appt = self.appointments[appointment_id]
        rev = {"revision": appt["revisions"][-1]["revision"] + 1, "starts": starts,
               "changed_on": self.as_of.date().isoformat(), "why": why}
        appt["revisions"].append(rev)
        return rev

    # -- ledger -------------------------------------------------------------

    def entry(self, appointment_id: str, revision: int) -> Entry:
        key = (appointment_id, revision)
        if key not in self.ledger:
            self.ledger[key] = Entry(ref=reminder_ref(appointment_id, revision), appointment_id=appointment_id,
                                     revision=revision, starts=self.revision(appointment_id, revision)["starts"],
                                     state="new")
        return self.ledger[key]

    def entries_for(self, appointment_id: str) -> list[Entry]:
        return sorted((e for (a, _), e in self.ledger.items() if a == appointment_id), key=lambda e: e.revision)

    def by_ref(self, ref: str) -> Optional[Entry]:
        ref = normalise_id(ref)
        return next((e for e in self.ledger.values() if e.ref == ref), None)

    def contact(self, patient_id: str) -> dict:
        return self.patients[patient_id]["contacts"]

    def booking_view(self, appointment_id: str) -> dict:
        appt = self.appointments[appointment_id]
        cur = self.current(appointment_id)
        earlier = [{"revision": r["revision"], "was": r["starts"].isoformat(timespec="minutes")}
                   for r in appt["revisions"][:-1]]
        change = self.change_requests.get(appointment_id)
        return {
            "appointment_id": appointment_id,
            "appointment": self.label(appointment_id),
            "site": f"{ORGANISATION} {appt['site']}",
            "current_revision": cur["revision"],
            "current_time": cur["starts"].isoformat(timespec="minutes"),
            "current_time_words": long_when(cur["starts"]),
            "earlier_versions": earlier,
            "reminders": [e.view() for e in self.entries_for(appointment_id)],
            "attendance": self.attendance.get((appointment_id, cur["revision"]), "not confirmed"),
            "reminders_paused_for_change_request": change["change_ref"] if change else None,
        }


_SERVICES: dict[str, ReminderService] = {}


def service_for(conversation_id: str) -> ReminderService:
    """One set of systems per conversation, so every scripted conversation starts from the same data."""
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = ReminderService()
    return _SERVICES[conversation_id]


def patient_profile(service: ReminderService, patient_id: Optional[str] = None) -> dict:
    patient_id = patient_id or SESSION_PATIENT_ID
    person = service.patients[patient_id]
    sms = person["contacts"]["sms"]
    return {
        "patient_id": patient_id,
        "first_name": person["first_name"],
        "sms_on_file": f"{sms['number']}, {'confirmed' if sms['confirmed'] else 'not confirmed'} for reminders",
        "today": f"{service.as_of:%A} {service.as_of.day} {service.as_of:%B %Y}",
    }


def list_appointments(service: ReminderService, patient_id: str) -> dict:
    return {"status": "read", "as_of": service.as_of.isoformat(timespec="minutes"),
            "appointments": [service.booking_view(a) for a in service.own_appointments(patient_id)],
            "next_step": ("Give the patient the current time of the appointment they asked about. An earlier "
                          "version is not their appointment any more. Delivery of a reminder is not the patient's "
                          "confirmation.")}


# ----------------------------------------------------------------------------
# Which appointment, and which revision the words name
# ----------------------------------------------------------------------------

NOT_FOUND = {
    "status": "not_found",
    "reason": "no_such_appointment",
    "effects": 0,
    "next_step": ("There is no such appointment on this patient's record. Say so, and name their own appointments "
                  "(list_appointments). Never say whose appointment an id belongs to."),
}


def _mentions(appt: dict, text: str) -> bool:
    if appt["surname"] and re.search(rf"\b{re.escape(appt['surname'].lower())}\b", text):
        return True
    return any(alias in text for alias in appt["aliases"]) or appt["kind"] in text


def resolve_appointment(service: ReminderService, patient_id: str, words: Any
                        ) -> tuple[Optional[str], Optional[int], dict]:
    """(appointment id, revision the words name, {}) or (None, None, blocked result).

    The revision is the one whose date and time match what the words say, or
    None when the words name no date or time. A time that matches only an
    earlier version gives that earlier revision number; a time that matches no
    version of the appointment gives 0.
    """
    text = plain(words).lower()
    own = service.own_appointments(patient_id)
    ident = re.search(r"\b(?:cc-?apt-?)?(\d{4})\b", text)
    when = read_when(text, service.as_of)
    if ident and f"CC-APT-{ident.group(1)}" in service.appointments:
        appt_id = f"CC-APT-{ident.group(1)}"
        if appt_id not in own:
            return None, None, dict(NOT_FOUND)
        candidates = [appt_id]
    else:
        candidates = [a for a in own if _mentions(service.appointments[a], text)]
        if not candidates and not when.empty:
            candidates = [a for a in own if any(when.matches(r["starts"]) for r in service.appointments[a]["revisions"])]
        if not candidates and re.search(r"\bcc-?apt-?\d+", text):
            return None, None, dict(NOT_FOUND)
    if not candidates:
        return None, None, _which(service, own, "which_appointment")
    if when.empty:
        if len(candidates) > 1:
            return None, None, _which(service, candidates, "which_appointment")
        return candidates[0], None, {}
    current_hits = [a for a in candidates if when.matches(service.current(a)["starts"])]
    if len(current_hits) == 1:
        return current_hits[0], service.current(current_hits[0])["revision"], {}
    if len(current_hits) > 1:
        return None, None, _which(service, current_hits, "which_appointment")
    earlier_hits = [(a, r["revision"]) for a in candidates for r in service.appointments[a]["revisions"][:-1]
                    if when.matches(r["starts"])]
    if len(earlier_hits) == 1:
        return earlier_hits[0][0], earlier_hits[0][1], {}
    if len(candidates) == 1:
        return candidates[0], 0, {}
    return None, None, _which(service, candidates, "which_appointment")


def _which(service: ReminderService, appointment_ids: list[str], detail: str) -> dict:
    return {
        "status": "which_appointment",
        "detail": detail,
        "effects": 0,
        "candidates": [f"{a}: {service.label(a)}, {short_when(service.current(a)['starts'])}" for a in appointment_ids],
        "next_step": "Ask the patient which appointment they mean, in their words; never choose for them.",
    }


# ----------------------------------------------------------------------------
# Where the reminder goes
# ----------------------------------------------------------------------------

# Words that point somewhere other than the number on file, and words that point at it.
_OTHER_CONTACT_RE = re.compile(
    r"\b(?:whatsapp|voicemail|voice\s*mail|call|calls|landline|work|office|daughter|son|husband|wife|partner|friend"
    r"|mum|mom|dad|mother|father|carer|caregiver|new|other|different|another|letter|post)\b")
_ON_FILE_RE = re.compile(r"\b(?:sms|text|texts|texting|number|phone|mobile|cell|on\s+file|here|this\s+thread|default"
                         r"|same|usual)\b")


def resolve_channel(service: ReminderService, patient_id: str, send_to: Any) -> dict:
    """Where the words say to send, and whether that contact is confirmed for reminders."""
    contacts = service.contact(patient_id)
    sms = contacts.get("sms") or {}
    words = plain(send_to).strip().lower().rstrip(".")
    if "@" in words or "email" in words or "e-mail" in words:
        email = contacts.get("email") or {}
        typed = re.search(r"[\w.+-]+@[\w.-]+", words)
        same = bool(email) and (not typed or typed.group(0) == email.get("address", "").lower())
        confirmed = same and email.get("confirmed") is True
        return {"channel": "email", "to": typed.group(0) if typed else email.get("address"), "on_file": same,
                "confirmed": confirmed,
                "why": None if confirmed else (email.get("why") if same else "an address typed in chat is not on file")}
    number = digits(words)
    if number:
        same = number[-7:] == digits(sms.get("number"))[-7:] and len(number) >= 7
        confirmed = same and sms.get("confirmed") is True and sms.get("reminder_consent") is True
        return {"channel": "sms", "to": send_to if not same else sms.get("number"), "on_file": same,
                "confirmed": confirmed,
                "why": None if confirmed else "a number typed in chat is not a confirmed contact on file"}
    if not words or (_ON_FILE_RE.search(words) and not _OTHER_CONTACT_RE.search(words)):
        confirmed = sms.get("confirmed") is True and sms.get("reminder_consent") is True
        return {"channel": "sms", "to": sms.get("number"), "on_file": True, "confirmed": confirmed,
                "why": None if confirmed else "the number on file is not confirmed for reminders"}
    return {"channel": "other", "to": str(send_to)[:60], "on_file": False, "confirmed": False,
            "why": "reminders go only to the confirmed SMS number on file"}


# ----------------------------------------------------------------------------
# The guard
# ----------------------------------------------------------------------------


def reminder_facts(service: ReminderService, appointment_id: str, named_revision: Optional[int],
                   channel: dict) -> dict:
    """The contract's three request facts, from trusted data only."""
    cur = service.current(appointment_id)["revision"]
    paused = appointment_id in service.change_requests
    entry = service.ledger.get((appointment_id, cur))
    return {
        "appointment_revision_current": (named_revision is None or named_revision == cur) and not paused,
        "reminder_not_sent": entry is None or entry.state in ("new", "queued", "failed"),
        "recipient_channel_confirmed": channel.get("confirmed") is True and channel.get("channel") == "sms",
    }


def _blocked(service: ReminderService, appointment_id: str, reason: str, facts: dict, named: Optional[int],
             channel: dict) -> dict:
    cur = service.current(appointment_id)
    entry = service.ledger.get((appointment_id, cur["revision"]))
    if reason == "obsolete_appointment" and appointment_id in service.change_requests:
        detail = "reminders_paused_for_change_request"
        step = (f"Reminders for this appointment are paused while change request "
                f"{service.change_requests[appointment_id]['change_ref']} is open. Send nothing; say the "
                f"{SCHEDULING_DESK} will confirm the time first.")
    elif reason == "obsolete_appointment":
        named_text = (long_when(service.revision(appointment_id, named)["starts"]) if named
                      else "a time that is not this booking")
        detail = "earlier_version" if named else "time_not_in_booking"
        step = (f"The time given ({named_text}) is not this appointment's current time. The current booking is "
                f"{long_when(cur['starts'])}. Tell the patient the current time before anything else. Send a reminder "
                "only if they ask for one for the current time, and then call this tool without the old time.")
    elif reason == "duplicate_reminder" and entry is not None and entry.state == "unknown":
        detail = "delivery_unknown"
        step = ("A reminder for this version is already with the text gateway and its delivery is not known. Never "
                "send it again: call check_reminder_delivery with its reference first.")
    elif reason == "duplicate_reminder":
        detail = "already_delivered"
        step = (f"The reminder for this version ({entry.ref if entry else 'on record'}) was already delivered"
                f"{' on ' + entry.delivered_at if entry and entry.delivered_at else ''}. Do not send a second one. You "
                "may tell the patient the current time again in your own words.")
    else:
        detail = channel.get("channel") or "unknown_channel"
        step = ("Reminders go only to the patient's confirmed SMS number on file. Send nothing to another number, "
                "address or channel. A new number is confirmed at the clinic's front desk, not in this chat.")
    return {"status": "blocked", "reason": reason, "detail": detail, "facts": facts, "effects": 0,
            "appointment_id": appointment_id, "named_revision": named,
            "current_revision": cur["revision"], "current_time": cur["starts"].isoformat(timespec="minutes"),
            "current_time_words": long_when(cur["starts"]),
            "recipient": {k: channel.get(k) for k in ("channel", "on_file", "confirmed", "why")},
            "next_step": step}


def _stamp(service: ReminderService) -> str:
    return service.as_of.isoformat(timespec="minutes")


def _attempt(service: ReminderService, entry: Entry, current_at_delivery: int, outcome: str, prior: int) -> dict:
    record = {"reminder_ref": entry.ref, "appointment_id": entry.appointment_id, "revision": entry.revision,
              "current_revision_at_delivery": current_at_delivery, "outcome": outcome,
              "prior_deliveries_for_revision": prior}
    service.attempts.append(record)
    return record


def deliver(service: ReminderService, appointment_id: str) -> tuple[list[dict], list[Entry]]:
    """Queue the current revision's reminder and hand it to the gateway, re-reading the booking at delivery.

    Returns (attempts, suppressed entries). A revision that changed between
    queueing and delivery is suppressed, and only the new current revision's
    unsent reminder is issued in its place.
    """
    appt = service.appointments[appointment_id]
    attempts: list[dict] = []
    suppressed: list[Entry] = []
    for _ in range(2):  # at most one reissue after a suppression
        cur = service.current(appointment_id)["revision"]
        entry = service.entry(appointment_id, cur)
        entry.state = "queued"
        entry.queued_at = entry.queued_at or _stamp(service)
        prior = entry.deliveries
        # The booking may change between queueing and delivery.
        if appt["delivery"] == "rescheduled_before_delivery" and appointment_id not in service._rescheduled:
            service._rescheduled.add(appointment_id)
            move = appt["reschedule_at_delivery"]
            service.reschedule(appointment_id, datetime.fromisoformat(move["starts"]), move["why"])
        now_current = service.current(appointment_id)["revision"]
        if now_current != entry.revision:
            entry.state, entry.why = "suppressed", "booking changed before delivery"
            attempts.append(_attempt(service, entry, now_current, "suppressed_obsolete", prior))
            suppressed.append(entry)
            continue
        # Any other queued reminder for this appointment is for an old revision: stop it.
        for other in service.entries_for(appointment_id):
            if other is not entry and other.state == "queued":
                other.state, other.why = "suppressed", "superseded by a later version"
                suppressed.append(other)
        entry.attempts += 1
        behaviour = appt["delivery"]
        if behaviour == "fails_first_attempt" and appointment_id not in service._first_attempt_used:
            service._first_attempt_used.add(appointment_id)
            entry.state, entry.why = "failed", "the carrier rejected the text; nothing was delivered"
            attempts.append(_attempt(service, entry, now_current, "failed", prior))
        elif behaviour == "loses_acknowledgment" and appointment_id not in service._first_attempt_used:
            service._first_attempt_used.add(appointment_id)
            entry.deliveries += 1  # the text reached the phone; the acknowledgment did not come back
            entry.state, entry.why = "unknown", "sent to the gateway; delivery acknowledgment not received"
            attempts.append(_attempt(service, entry, now_current, "delivered_unacknowledged", prior))
        else:
            entry.deliveries += 1
            entry.state, entry.why, entry.delivered_at = "delivered", None, _stamp(service)
            attempts.append(_attempt(service, entry, now_current, "delivered", prior))
        break
    return attempts, suppressed


def send_reminder(service: ReminderService, patient_id: str, appointment_words: Any, send_to: Any = None) -> dict:
    """Queue and deliver one reminder for the current revision of one appointment, or say why not."""
    appointment_id, named, blocked = resolve_appointment(service, patient_id, appointment_words)
    if appointment_id is None:
        return blocked
    channel = resolve_channel(service, patient_id, send_to)
    facts = reminder_facts(service, appointment_id, named, channel)
    reason = evaluate(facts)
    if reason:
        return _blocked(service, appointment_id, reason, facts, named, channel)
    queued_rev = service.current(appointment_id)["revision"]
    attempts, suppressed = deliver(service, appointment_id)
    cur = service.current(appointment_id)
    entry = service.ledger[(appointment_id, cur["revision"])]
    delivered_obsolete = [e for e in service.entries_for(appointment_id)
                          if e.revision != cur["revision"] and e.deliveries > 0]
    result = {
        "reminder_ref": entry.ref,
        "appointment_id": appointment_id,
        "appointment": service.label(appointment_id),
        "revision": cur["revision"],
        "appointment_time": cur["starts"].isoformat(timespec="minutes"),
        "appointment_time_words": long_when(cur["starts"]),
        "sent_to": f"SMS {channel['to']}",
        "delivery": entry.state,
        "attendance": service.attendance.get((appointment_id, cur["revision"]), "not confirmed"),
        "attempts": attempts,
        "booking_changed_before_delivery": cur["revision"] != queued_rev,
        "suppressed": [{"reminder_ref": e.ref, "revision": e.revision, "for_time": e.starts.isoformat(timespec="minutes"),
                        "why": e.why} for e in suppressed],
        "supersedes_delivered": [{"reminder_ref": e.ref, "revision": e.revision,
                                  "for_time": e.starts.isoformat(timespec="minutes"), "delivered_at": e.delivered_at}
                                 for e in delivered_obsolete],
        "effects": sum(1 for a in attempts if a["outcome"] in ("delivered", "delivered_unacknowledged")),
    }
    if entry.state == "delivered":
        result.update(status="succeeded", next_step=(
            "The patient has been sent the reminder with its reference, the current time and the question. Do not "
            "repeat the reminder. Delivery is not attendance: attendance stays not confirmed until the patient "
            "replies, then call record_reminder_reply."))
    elif entry.state == "unknown":
        result.update(status="pending", reason="delivery_unconfirmed", next_step=(
            "The gateway has not acknowledged delivery. Never send it again: call check_reminder_delivery with the "
            "reminder_ref before anything else."))
    else:
        result.update(status="pending", reason="delivery_failed", next_step=(
            "Nothing was delivered: the carrier rejected the text. Call check_reminder_delivery with the reminder_ref; "
            "if it is still undelivered and the patient wants it, call send_appointment_reminder once more. It "
            "reissues only the current version's reminder."))
    return result


# ----------------------------------------------------------------------------
# Reading the patient's reply to a reminder
# ----------------------------------------------------------------------------

_CONFIRM_RE = re.compile(
    r"\b(?:yes|yep|yeah|yup|confirm(?:ed|ing)?|i'?ll be there|i will be there|see you|that works|works for me"
    r"|correct|sounds good|perfect|great|ok(?:ay)?|sure|i'?ll come|i can make it)\b", re.IGNORECASE)
_CHANGE_RE = re.compile(
    r"\b(?:no|nope|not|wrong|change|cancel|can'?t|cannot|won'?t|isn'?t|reschedul\w*|move|different|another"
    r"|instead|unable|doesn'?t work|thought it was)\b", re.IGNORECASE)
# Phrases that carry a negative word but still say yes.
_NOT_A_CHANGE_RE = re.compile(r"\b(?:no\s+problem|not\s+a\s+problem|no\s+worries|no\s+need\s+to\s+change)\b",
                              re.IGNORECASE)


def classify_reply(text: Any) -> str:
    """'confirm', 'change' or 'unclear', from the patient's own words."""
    t = _NOT_A_CHANGE_RE.sub(" ", plain(text))
    confirm, change = bool(_CONFIRM_RE.search(t)), bool(_CHANGE_RE.search(t))
    if change:
        return "change"
    return "confirm" if confirm else "unclear"


def record_reply(service: ReminderService, patient_id: str, conversation: Conversation, reference: Any) -> dict:
    """Record the patient's answer to a delivered reminder. Attendance only; delivery is not touched."""
    entry = service.by_ref(reference)
    if entry is None or service.appointments[entry.appointment_id]["patient_id"] != patient_id:
        return {"status": "not_found", "reason": "no_such_reminder", "reference": normalise_id(reference),
                "effects": 0, "next_step": "There is no such reminder on this patient's record. Use list_appointments."}
    appointment_id = entry.appointment_id
    cur = service.current(appointment_id)
    base = {"reminder_ref": entry.ref, "appointment_id": appointment_id, "appointment": service.label(appointment_id),
            "reminder_revision": entry.revision, "current_revision": cur["revision"],
            "current_time": cur["starts"].isoformat(timespec="minutes"), "current_time_words": long_when(cur["starts"]),
            "delivery": entry.state}
    if entry.revision != cur["revision"]:
        return {**base, "status": "blocked", "reason": "obsolete_appointment", "detail": "reminder_for_earlier_version",
                "reminder_was_for": long_when(entry.starts), "attendance": "not confirmed", "effects": 0,
                "next_step": (f"That reminder was for an earlier version of this booking ({long_when(entry.starts)}). "
                              f"Nothing is confirmed. Tell the patient the booking is now {long_when(cur['starts'])} "
                              "and ask whether they can attend then. Do not send a reminder unless they ask.")}
    if appointment_id in service.change_requests:
        return {**base, "status": "blocked", "reason": "obsolete_appointment", "detail": "change_requested",
                "attendance": "change requested", "effects": 0,
                "next_step": "A change request is open for this appointment; nothing is confirmed until it is resolved."}
    if entry.deliveries == 0:
        return {**base, "status": "blocked", "reason": "not_delivered", "attendance": "not confirmed", "effects": 0,
                "next_step": "This reminder was never delivered, so there is no reply to record."}
    replies = conversation.replies_after(entry.ref)
    answer = classify_reply(replies[-1]) if replies else "unclear"
    if answer == "change":
        return {**base, "status": "not_confirmed", "detail": "patient_disputes_or_wants_change",
                "attendance": service.attendance.get((appointment_id, cur["revision"]), "not confirmed"), "effects": 0,
                "next_step": ("The patient says the time is wrong or wants a change. Do not repeat or resend the "
                              "reminder. Resolve the current booking first: tell them the current time from "
                              "list_appointments, and if they want a different time, call request_appointment_change.")}
    if answer == "unclear":
        return {**base, "status": "not_confirmed", "detail": "reply_unclear",
                "attendance": service.attendance.get((appointment_id, cur["revision"]), "not confirmed"), "effects": 0,
                "next_step": "The patient's reply does not say yes or ask for a change. Ask them to confirm or change."}
    key = (appointment_id, cur["revision"])
    replay = service.attendance.get(key) == "confirmed"
    service.attendance[key] = "confirmed"
    return {**base, "status": "confirmed", "attendance": "confirmed", "replay": replay, "effects": 0 if replay else 1,
            "next_step": ("The patient has been sent the confirmation. Attendance is recorded for this version only; "
                          "delivery and attendance are separate.")}


# ----------------------------------------------------------------------------
# Recovery: query the ledger by revision, and pause for a change
# ----------------------------------------------------------------------------


def check_delivery(service: ReminderService, patient_id: str, reference: Any) -> dict:
    """The appointment's reminder ledger by revision. Reconciles an unacknowledged delivery; sends nothing."""
    entry = service.by_ref(reference)
    if entry is not None and service.appointments[entry.appointment_id]["patient_id"] == patient_id:
        appointment_id = entry.appointment_id
    else:
        appointment_id, _, blocked = resolve_appointment(service, patient_id, reference)
        if appointment_id is None:
            return blocked
        cur_rev = service.current(appointment_id)["revision"]
        entry = service.ledger.get((appointment_id, cur_rev))
    reconciled = None
    if entry is not None and entry.state == "unknown":
        if entry.deliveries > 0:
            entry.state, entry.why, entry.delivered_at = "delivered", "confirmed on ledger check", _stamp(service)
            reconciled = "delivered"
    cur = service.current(appointment_id)
    current_entry = service.ledger.get((appointment_id, cur["revision"]))
    view = service.booking_view(appointment_id)
    if current_entry is None or current_entry.state == "new":
        step = "No reminder has been sent for the current version. Send one only if the patient asks."
    elif current_entry.state == "delivered":
        step = ("The current version's reminder was delivered. Never send it again. "
                + ("The patient has been sent the delivery notice." if reconciled else ""))
    elif current_entry.state == "failed":
        step = ("The current version's reminder was not delivered. If the patient wants it, call "
                "send_appointment_reminder once; it reissues only this version's reminder.")
    else:
        step = f"The current version's reminder is {current_entry.state}. Do not send another."
    return {"status": "read", "reconciled": reconciled, "current_reminder_ref": current_entry.ref if current_entry else None,
            "current_reminder_delivery": current_entry.state if current_entry else "none", **view, "next_step": step}


def request_change(service: ReminderService, patient_id: str, conversation_id: str, appointment_words: Any,
                   requested_time: Any, reason: Any) -> dict:
    """Route a change to the scheduling team and pause this appointment's reminders. Moves nothing itself."""
    appointment_id, _, blocked = resolve_appointment(service, patient_id, appointment_words)
    if appointment_id is None:
        return blocked
    cur = service.current(appointment_id)
    prior = service.change_requests.get(appointment_id)
    replay = prior is not None
    if prior is None:
        prior = {"change_ref": f"CC-CHG-{_digest(conversation_id, appointment_id)[:6]}",
                 "requested_time": str(requested_time or "")[:80] or None, "reason": str(reason or "")[:200]}
        service.change_requests[appointment_id] = prior
        for entry in service.entries_for(appointment_id):
            if entry.state == "queued":
                entry.state, entry.why = "suppressed", "paused for a change request"
        service.attendance[(appointment_id, cur["revision"])] = "change requested"
    return {"status": "routed", **prior, "appointment_id": appointment_id, "appointment": service.label(appointment_id),
            "booking_now": long_when(cur["starts"]), "current_revision": cur["revision"], "team": SCHEDULING_DESK,
            "reply_within": REPLY_WITHIN, "reminders_paused": True, "moved": False, "replay": replay,
            "effects": 0 if replay else 1,
            "next_step": ("The patient has been sent the change-request reference. The booking has not moved yet; "
                          "no reminder goes out for this appointment until the scheduling team confirms a time.")}


# ----------------------------------------------------------------------------
# Memory (one short field per value)
# ----------------------------------------------------------------------------


def memory_values(service: ReminderService, result: dict) -> dict:
    """Skill memory after a reminder tool: the latest reminder, one short field each."""
    appointment_id = result.get("appointment_id")
    ref = result.get("reminder_ref") or result.get("current_reminder_ref")
    if not appointment_id or not ref or appointment_id not in service.appointments:
        return {}
    entry = service.by_ref(ref)
    if entry is None:
        return {}
    cur = service.current(appointment_id)
    return {
        "reminder_ref": entry.ref,
        "reminder_for": f"{appointment_id} {service.label(appointment_id)}"[:MEMORY_VALUE_LIMIT],
        "reminder_time": f"version {entry.revision}: {long_when(entry.starts)}",
        "reminder_delivery": entry.state,
        "reminder_attendance": service.attendance.get((appointment_id, cur["revision"]), "not confirmed"),
    }


def memory_values_fit(values: dict) -> bool:
    return all(len(str(v)) <= MEMORY_VALUE_LIMIT for v in values.values())


# ----------------------------------------------------------------------------
# The messages the tools send the patient themselves (TOOL_SENDS_RECEIPT)
# ----------------------------------------------------------------------------


def _when(iso: Optional[str]) -> str:
    return long_when(datetime.fromisoformat(iso)) if iso else "not set"


def customer_receipt(tool: str, result: dict) -> Optional[str]:
    """The message a tool sends the patient for an outcome they must see, or None."""
    status = result.get("status")
    if tool == "send_appointment_reminder" and result.get("reminder_ref") and result.get("delivery") in (
            "delivered", "unknown"):
        lead = ""
        if result.get("suppressed"):
            old = result["suppressed"][0]
            lead = (f" The clinic changed this time before the reminder went out, so the reminder for "
                    f"{_when(old['for_time'])} was stopped.")
        elif result.get("supersedes_delivered"):
            old = result["supersedes_delivered"][-1]
            lead = f" This replaces the earlier reminder for {_when(old['for_time'])}, which is no longer your time."
        return (f"{ORGANISATION} reminder {result['reminder_ref']}: your {result['appointment']} is on "
                f"{result['appointment_time_words']}.{lead} {REMINDER_QUESTION}")
    if tool == "check_reminder_delivery" and result.get("reconciled") == "delivered":
        return (f"Reminder {result['current_reminder_ref']} for your {result['appointment']} on "
                f"{result['current_time_words']} was delivered. No second reminder will be sent.")
    if tool == "record_reminder_reply" and status == "confirmed" and not result.get("replay"):
        return (f"Thank you. You have confirmed you will attend your {result['appointment']} on "
                f"{result['current_time_words']} (reminder {result['reminder_ref']}).")
    if tool == "request_appointment_change" and status == "routed" and not result.get("replay"):
        return (f"Change request {result['change_ref']} is with {result['team']}. Your {result['appointment']} stays "
                f"booked for {result['booking_now']} until they confirm a new time, and no reminders will be sent "
                f"for it until then. They reply within {result['reply_within']}.")
    return None


# ----------------------------------------------------------------------------
# Words: saying a reminder went out when no tool delivered one (measured only)
# ----------------------------------------------------------------------------

SENT_CLAIM_PATTERN = (
    rf"\b(?:i|we){APOS}?(?:ve|\s+have)?\s+(?:just\s+|now\s+|already\s+)?(?:re-?sent|sent|texted|resent)\s+"
    r"(?:you\s+)?(?:a|another|the|your|a\s+new|a\s+fresh)?\s*(?:new\s+|fresh\s+|second\s+)?(?:reminder|text)\b"
    r"|\b(?:a|another|the|your|a\s+new)\s+(?:new\s+|fresh\s+|second\s+)?reminder\s+(?:has\s+been|is)\s+"
    r"(?:just\s+|now\s+)?(?:re-?sent|sent|resent|on\s+its\s+way)\b"
)
HEDGE_PATTERN = (
    r"\b(?:not|no|never|nothing|cannot|won" + APOS + r"t|can" + APOS + r"t|didn" + APOS + r"t|haven" + APOS
    + r"t|hasn" + APOS + r"t|wasn" + APOS + r"t|if|whether|unless|already\s+delivered|earlier|yesterday)\b"
    + r"|n" + APOS + r"t\b"
)
SENT_CLAIM_RE = re.compile(SENT_CLAIM_PATTERN, re.IGNORECASE)
HEDGE_RE = re.compile(HEDGE_PATTERN, re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def sent_claims(text: str) -> list[str]:
    """Sentences that say a reminder was sent now (not negated or conditioned before the match)."""
    found = []
    for sentence in _SENTENCE_RE.split(plain(text)):
        for match in SENT_CLAIM_RE.finditer(sentence):
            if HEDGE_RE.search(sentence[: match.start()]):
                continue
            found.append(match.group(0))
    return found
