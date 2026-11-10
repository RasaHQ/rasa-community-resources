"""Horizon Travel journey changes and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the casebook contract for ``travel-booking`` (vendored as
``lib/fixtures/case-contract.json``): two request rules and one receipt rule.

- ``segment_identity_confirmed`` (request): the segment being changed is the
  one the tools resolved from the signed-in traveller's own booking and read
  back to the caller, it is still open (not flown), and it has not changed
  since the draft was prepared. The model passes a booking and an option id
  from ``find_change_options``; the draft it confirms is skill memory only
  ``prepare_journey_change`` writes.
- ``dependent_services_checked`` (request): every service linked to the
  segment (the connecting flight, transfers, the checked bag's routing,
  parking) is found from the booking at commit time, its status can be read,
  and the set is exactly the one read back to the caller. If a partner's
  status cannot be read, nothing changes.
- ``change_receipt_reconciled`` (receipt): after the change, the identifiers
  of every affected service are compared with the new segment. Only when
  each one points at the new times is the change complete. Otherwise the
  result is ``pending`` / ``partial_journey_change``: the booking is frozen
  for further changes and handed to the travel desk with a reference, rather
  than repeating the request.

Facts are computed here from trusted data. The model supplies a booking
reference (or trip city), segment words and an option id. It never supplies
a fact, a traveller id or an outcome. A fact that is not exactly ``True``
fails its rule, as in the lab's ``evaluate``.

Booking state lives in an in-process service with one copy of the fixture per
conversation, so every scripted call starts from the same bookings.

The organisation guard runs at import. It is an allowlist, not a list of real
names: the fixture's organisation must be exactly the casebook contract's
fictional organisation, marked ``(fictional)``, and the contract must be the
casebook's authored synthetic fixture.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "journeys.json"

# Mantle cuts a memory value at 100 characters in the prompt without saying so
# (found in the GPT quote and diagnostics builds); every memory value is kept
# under this, and tests/test_journeys.py checks every option of every booking.
MEMORY_VALUE_LIMIT = 100
MEMORY_KEYS = ("draft_booking", "draft_option", "draft_segment", "draft_services", "change_label",
               "services_label")

# The change tool sends the caller its own receipt through ToolContext.send
# (found in the claim-intake and collections builds: left to the model,
# references often never reach the customer).
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
    if "(fictional" not in str(data.get("partners") or ""):
        raise FictionalOrganisationError("the service partners must be marked (fictional ...)")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")
    for traveller in data.get("travellers", {}).values():
        if not str(traveller.get("email", "")).endswith("@example.com"):
            raise FictionalOrganisationError("traveller emails must use the reserved example.com domain")
        if " 555 01" not in str(traveller.get("mobile", "")):
            raise FictionalOrganisationError("traveller mobiles must be in the 555-01xx fictional range")
    partners = str(data.get("partners") or "")
    for booking in data.get("bookings", {}).values():
        for service in booking.get("services", {}).values():
            provider = service.get("provider")
            if provider and provider not in partners:
                raise FictionalOrganisationError(f"service provider {provider!r} is not a listed fictional partner")


# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA, _CONTRACT)

ORGANISATION = _DATA["organisation"].split(" (")[0]
SESSION_TRAVELLER_ID = _DATA["session_traveller_id"]
TRAVEL_DESK = _DATA["travel_desk"]
AS_OF = datetime.fromisoformat(_DATA["as_of"])
CITIES = _DATA["cities"]


def load_contract() -> dict:
    return json.loads(json.dumps(_CONTRACT))


def load_data() -> dict:
    return json.loads(json.dumps(_DATA))


def rules(phase: str, contract: Optional[dict] = None) -> list[dict]:
    contract = contract or _CONTRACT
    return [rule for rule in contract["rules"] if rule["phase"] == phase]


def evaluate(facts: dict, phase: str = "request", contract: Optional[dict] = None) -> Optional[str]:
    """First failing rule's reason for the phase, or None. A fact must be exactly ``True``."""
    for rule in rules(phase, contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


def lab_outcome(facts: dict, contract: Optional[dict] = None) -> tuple[str, str, int]:
    """The lab's execute(): request rules block with no effect; the receipt rule leaves it pending."""
    reason = evaluate(facts, "request", contract)
    if reason:
        return "blocked", reason, 0
    reason = evaluate(facts, "receipt", contract)
    if reason:
        return "pending", reason, 1
    return "succeeded", "verified_fixture_receipt", 1


# ----------------------------------------------------------------------------
# Speech-friendly labels
# ----------------------------------------------------------------------------

_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def spoken_code(code: str) -> str:
    """'HZ 219' -> 'H Z 2 1 9'; 'HZ4R8N' -> 'H Z 4 R 8 N'."""
    return " ".join(ch for ch in code if ch.isalnum())


def spoken_reference(reference: str) -> str:
    """'HC-482913' -> 'H C, 4 8 2, 9 1 3'."""
    prefix, _, digits = reference.partition("-")
    return f"{' '.join(prefix)}, {' '.join(digits[:3])}, {' '.join(digits[3:])}"


def spoken_date(value: str) -> str:
    moment = _dt(value)
    return f"{_MONTHS[moment.month - 1]} {moment.day}"


def spoken_time(value: str) -> str:
    moment = _dt(value)
    hour = moment.hour % 12 or 12
    suffix = "AM" if moment.hour < 12 else "PM"
    return f"{hour}:{moment.minute:02d} {suffix}" if moment.minute else f"{hour} {suffix}"


def city(code: str) -> str:
    return CITIES.get(code, code)


def route(segment: dict) -> str:
    return f"{city(segment['from'])} to {city(segment['to'])}"


def segment_summary(segment_id: str, segment: dict) -> dict:
    return {
        "segment": segment_id,
        "flight": segment["flight"],
        "flight_spoken": spoken_code(segment["flight"]),
        "route": route(segment),
        "direction": segment["direction"],
        "departs": segment["departs"],
        "arrives": segment["arrives"],
        "departs_spoken": f"{spoken_date(segment['departs'])} at {spoken_time(segment['departs'])}",
        "arrives_spoken": f"{spoken_date(segment['arrives'])} at {spoken_time(segment['arrives'])}",
        "status": segment["status"],
    }


# ----------------------------------------------------------------------------
# Normalising what the model passes (spoken or typed)
# ----------------------------------------------------------------------------

# Straight and curly apostrophes read the same everywhere below.
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})

_DIGIT_WORDS = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "for": "4",
                "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
_LETTER_WORDS = {"aitch": "h", "zee": "z", "zed": "z", "are": "r", "en": "n", "and": "n", "em": "m",
                 "pee": "p", "el": "l", "vee": "v", "dee": "d", "ex": "x", "tee": "t", "kay": "k",
                 "cue": "q", "why": "y", "see": "c", "sea": "c"}
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
             "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
             "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
             "nineteenth": 19, "twentieth": 20, "twenty-first": 21, "twenty-second": 22, "twenty-third": 23,
             "twenty-fourth": 24, "twenty-fifth": 25, "twenty-sixth": 26, "twenty-seventh": 27,
             "twenty-eighth": 28, "twenty-ninth": 29, "thirtieth": 30, "thirty-first": 31}
_RETURN_WORDS = re.compile(r"\b(?:return|returning|home|back|inbound|flight home|way back)\b")
_OUTBOUND_WORDS = re.compile(r"\b(?:outbound|going out|way out|out there|first leg|departing flight)\b")


def clean(value: Any) -> str:
    return str(value or "").translate(_APOSTROPHES).strip()


def compact_code(value: Any) -> str:
    """Letters and digits as spoken or typed, joined: 'H Z four R eight N' -> 'hz4r8n'.

    Words that are not a single letter, a digit word, a letter name or a short
    code break the run with '|', so codes do not join across ordinary words.
    """
    out = []
    for token in re.findall(r"[a-z0-9]+", clean(value).lower().replace("-", " ")):
        if token in _DIGIT_WORDS:
            out.append(_DIGIT_WORDS[token])
        elif token in _LETTER_WORDS:
            out.append(_LETTER_WORDS[token])
        elif len(token) == 1 or (len(token) <= 6 and re.search(r"\d", token)) or token == "hz":
            out.append(token)
        else:
            out.append("|")
    return "".join(out)


def digit_runs(value: Any) -> set[str]:
    return {run for run in re.findall(r"\d+", compact_code(value))}


def parse_date(value: Any) -> Optional[str]:
    """'2026-10-24', 'October 24', '24 October', 'the 24th', 'twenty-fourth', 'tomorrow' -> '2026-10-24'."""
    text = clean(value).lower()
    m = re.search(r"\b(20\d\d)-(\d\d)-(\d\d)\b", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if re.search(r"\btomorrow\b", text):
        return (AS_OF + timedelta(days=1)).date().isoformat()
    if re.search(r"\btoday\b|\btonight\b", text):
        return AS_OF.date().isoformat()
    month = None
    for i, name in enumerate(_MONTHS):
        if re.search(rf"\b{name.lower()}\b|\b{name.lower()[:3]}\b", text):
            month = i + 1
    day = None
    for word, number in sorted(_ORDINALS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{word}\b", text.replace(" ", "-")) or re.search(rf"\b{word}\b", text):
            day = number
            break
    if day is None:
        # A bare number is a day only next to a month, after "the", or with an ordinal suffix.
        pattern = (r"\b(\d{1,2})(?:st|nd|rd|th)?\b" if month else
                   r"\b(?:the\s+)(\d{1,2})(?:st|nd|rd|th)?\b|\b(\d{1,2})(?:st|nd|rd|th)\b")
        m = re.search(pattern, text)
        number = next((g for g in (m.groups() if m else ()) if g), None)
        if number and 1 <= int(number) <= 31:
            day = int(number)
    if day is None:
        return None
    if month is None:
        # A bare day means the next such day on or after the booking clock.
        month, year = AS_OF.month, AS_OF.year
        if day < AS_OF.day:
            month, year = (1, year + 1) if month == 12 else (month + 1, year)
        return f"{year}-{month:02d}-{day:02d}"
    year = AS_OF.year if month >= AS_OF.month else AS_OF.year + 1
    return f"{year}-{month:02d}-{day:02d}"


def mentioned_cities(value: Any) -> list[str]:
    """Airport codes of the cities named, in the order they are named."""
    text = clean(value)
    lower = text.lower()
    found = []
    for code, name in CITIES.items():
        for m in re.finditer(rf"\b{name.lower()}\b", lower):
            found.append((m.start(), code))
        for m in re.finditer(rf"\b{code}\b", text):  # codes only in capitals: "mad", "den" are words
            found.append((m.start(), code))
    ordered = []
    for _, code in sorted(found):
        if code not in ordered:
            ordered.append(code)
    return ordered


# ----------------------------------------------------------------------------
# The booking service (one per conversation)
# ----------------------------------------------------------------------------


def _reference(prefix: str, *parts: str) -> str:
    return f"{prefix}-{int(hashlib.sha256('|'.join(parts).encode()).hexdigest(), 16) % 1_000_000:06d}"


class JourneyService:
    """Bookings, changes and travel-desk hand-offs for one conversation."""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self.data = load_data()
        self.frozen: dict[str, str] = {}  # booking -> travel-desk reference
        self.changes: list[dict] = []

    # -- lookup ----------------------------------------------------------------

    def traveller(self, traveller_id: Optional[str]) -> Optional[dict]:
        return self.data["travellers"].get(traveller_id or "")

    def _by_reference(self, traveller_id: Optional[str], value: Any) -> tuple[Optional[str], Optional[dict], str]:
        code = compact_code(value)
        for ref, booking in self.data["bookings"].items():
            if ref.lower() in code:
                if booking["traveller_id"] != traveller_id:
                    return None, None, "not_found"
                return ref, booking, "reference"
        return None, None, "no_reference"

    def find_booking(self, traveller_id: Optional[str], value: Any,
                     caller_texts: Iterable[str] = ()) -> tuple[Optional[str], Optional[dict], str]:
        """(reference, booking, how). A booking of another traveller is never returned or named.

        The model's argument is tried first. If it holds no known reference, the caller's own words in
        the tracker are read, newest first: on voice the model can mangle a spelled code that the
        transcript still holds (the estimate call: Flux wrote "h z four r eight and" and GPT-5.5 passed
        "HZ4R8").
        """
        ref, booking, how = self._by_reference(traveller_id, value)
        if how != "no_reference":
            return ref, booking, how
        for text in reversed(list(caller_texts)):
            ref, booking, how = self._by_reference(traveller_id, text)
            if how == "reference":
                return ref, booking, "caller_words"
            if how == "not_found":
                return None, None, "not_found"
        own = {ref: b for ref, b in self.data["bookings"].items() if b["traveller_id"] == traveller_id}
        # Boston is on every trip, so only another city picks one; failing that, a date with one flight.
        places = [c for c in mentioned_cities(value) if c != "BOS"]
        if places:
            matches = [ref for ref, b in own.items()
                       if any(c in {s[k] for s in b["segments"].values() for k in ("from", "to")} for c in places)]
        else:
            day = parse_date(value)
            matches = [ref for ref, b in own.items()
                       if day and any(s["departs"].startswith(day) for s in b["segments"].values())]
        if len(matches) == 1:
            return matches[0], own[matches[0]], "trip"
        return None, None, "not_found"

    def own_trips(self, traveller_id: Optional[str]) -> list[dict]:
        return [{"booking": ref, "booking_spoken": spoken_code(ref), "trip": b["trip"]}
                for ref, b in self.data["bookings"].items() if b["traveller_id"] == traveller_id]

    def resolve_segment(self, booking: dict, words: Any) -> tuple[str, list[str]]:
        """('resolved' | 'ambiguous' | 'flown' | 'no_match', segment ids)."""
        segments = booking["segments"]
        candidates = list(segments)
        text = clean(words).lower()
        runs = digit_runs(words)
        by_flight = [sid for sid in candidates if segments[sid]["flight"].split()[-1] in runs]
        if by_flight:
            candidates = by_flight
        cities = mentioned_cities(words)
        if len(cities) >= 2:
            directed = [sid for sid in candidates
                        if segments[sid]["from"] == cities[0] and segments[sid]["to"] == cities[1]]
            if directed:
                candidates = directed
        elif len(cities) == 1:
            touching = [sid for sid in candidates if cities[0] in (segments[sid]["from"], segments[sid]["to"])]
            if touching:
                candidates = touching
        if _RETURN_WORDS.search(text):
            chosen = [sid for sid in candidates if segments[sid]["direction"] == "return"]
            candidates = chosen or candidates
        elif _OUTBOUND_WORDS.search(text):
            chosen = [sid for sid in candidates if segments[sid]["direction"] == "outbound"]
            candidates = chosen or candidates
        day = parse_date(words)
        if day:
            dated = [sid for sid in candidates if segments[sid]["departs"].startswith(day)]
            candidates = dated or candidates
        if len(candidates) == len(segments) and not (by_flight or cities or day or _RETURN_WORDS.search(text)
                                                     or _OUTBOUND_WORDS.search(text)):
            return ("resolved", candidates) if len(candidates) == 1 else ("ambiguous", candidates)
        open_ids = [sid for sid in candidates if segments[sid]["status"] == "open"]
        if len(candidates) == 1:
            return ("resolved" if open_ids else "flown"), candidates
        if len(open_ids) == 1:
            return "resolved", open_ids
        if not open_ids:
            return "flown", candidates
        return "ambiguous", open_ids

    # -- the journey plan ------------------------------------------------------

    def plan(self, booking: dict, segment_id: str, option: dict) -> list[dict]:
        """Every service linked to the change, with the state the change would leave it in."""
        segments = booking["segments"]
        times = {sid: {"flight": s["flight"], "departs": s["departs"], "arrives": s["arrives"]}
                 for sid, s in segments.items()}
        changed = {segment_id: {"flight": option["flight"], "departs": option["departs"],
                                "arrives": option["arrives"], "option": option["id"]}}
        times[segment_id] = dict(changed[segment_id])
        items: list[dict] = []
        # Connections: the onward flight the changed segment feeds, cascading, and the inbound one it
        # leaves from.
        queue = [segment_id]
        while queue:
            sid = queue.pop(0)
            for other_id, other in segments.items():
                if other.get("connects_from") != sid or other["status"] != "open":
                    continue
                need = _dt(times[sid]["arrives"]) + timedelta(minutes=other.get("min_connection_minutes", 60))
                item = {"id": other_id, "kind": "connection", "label": f"{route(other)} connection",
                        "short": f"{city(other['to'])} connection", "status_feed": "ok",
                        "before": _flight_id(other), "anchor": sid}
                if _dt(other["departs"]) >= need:
                    item.update(state="still_valid", after=_flight_id(other))
                else:
                    onward = next((o for o in booking["options"].get(other_id, [])
                                   if _dt(o["departs"]) >= need), None)
                    if onward is None:
                        item.update(state="unresolved", after=_flight_id(other),
                                    detail="no connecting flight after the new arrival")
                    else:
                        item.update(state="moved", after=_flight_id(onward), option=onward["id"])
                        changed[other_id] = {"flight": onward["flight"], "departs": onward["departs"],
                                             "arrives": onward["arrives"], "option": onward["id"]}
                        times[other_id] = dict(changed[other_id])
                        queue.append(other_id)
                items.append(item)
        inbound_id = segments[segment_id].get("connects_from")
        if inbound_id:
            inbound = segments[inbound_id]
            need = _dt(inbound["arrives"]) + timedelta(minutes=segments[segment_id].get("min_connection_minutes", 60))
            ok = _dt(times[segment_id]["departs"]) >= need
            items.insert(0, {"id": inbound_id, "kind": "inbound", "label": f"{route(inbound)} flight before it",
                             "short": f"{city(inbound['from'])} flight", "status_feed": "ok",
                             "before": _flight_id(inbound), "after": _flight_id(inbound), "anchor": segment_id,
                             "state": "still_valid" if ok else "unresolved",
                             **({} if ok else {"detail": "the new flight leaves before the connection time"})})
        for service_id, service in booking["services"].items():
            if service["kind"] == "bag":
                if not any(s in changed for s in service["segments"]):
                    continue
                routing = [f"{times[s]['flight']} {times[s]['departs'][:10]}" for s in service["segments"]]
                items.append({"id": service_id, "kind": "bag", "label": service["label"], "short": service["short"],
                              "status_feed": service["status_feed"], "before": list(service["routing"]),
                              "after": routing, "state": "re_tagged", "anchor": ",".join(service["segments"])})
                continue
            anchor = service["segment"]
            if anchor not in changed:
                continue
            base = _dt(times[anchor][service["event"]])
            item = {"id": service_id, "kind": service["kind"], "label": service["label"], "short": service["short"],
                    "provider": service.get("provider"), "status_feed": service["status_feed"],
                    "before": service["time"], "anchor": anchor}
            if service["kind"] == "timed":
                new_time = (base + timedelta(minutes=service["offset_minutes"])).isoformat(timespec="minutes")
                if new_time == service["time"]:
                    item.update(state="still_valid", after=service["time"])
                elif service["auto_retime"]:
                    item.update(state="moved", after=new_time)
                else:
                    item.update(state="unresolved", after=service["time"],
                                detail=f"{service.get('provider')} does not accept an automatic change")
            else:  # cover: the service must still cover the anchor time
                if base <= _dt(service["time"]):
                    item.update(state="still_valid", after=service["time"])
                else:
                    item.update(state="unresolved", after=service["time"],
                                detail=f"{service.get('provider')} cannot extend it automatically; "
                                       f"it ends {spoken_date(service['time'])} at {spoken_time(service['time'])}")
            items.append(item)
        for item in items:
            item["changes_segment"] = changed.get(item["id"])
        return items

    # -- state -----------------------------------------------------------------

    def apply(self, booking: dict, segment_id: str, option: dict, items: list[dict]) -> None:
        segments = booking["segments"]
        segments[segment_id].update(flight=option["flight"], departs=option["departs"], arrives=option["arrives"])
        for item in items:
            if item["state"] in ("still_valid", "unresolved"):
                continue
            if item["kind"] == "connection":
                seg = item["changes_segment"]
                segments[item["id"]].update(flight=seg["flight"], departs=seg["departs"], arrives=seg["arrives"])
            elif item["kind"] == "bag":
                booking["services"][item["id"]]["routing"] = list(item["after"])
            else:
                booking["services"][item["id"]]["time"] = item["after"]

    def reconcile(self, booking: dict, items: list[dict]) -> list[dict]:
        """Compare every affected identifier after the change with the new segments. One row per item."""
        segments = booking["segments"]
        rows = []
        for item in items:
            if item["kind"] == "connection":
                seg = segments[item["id"]]
                prev = segments[seg["connects_from"]]
                ok = _dt(seg["departs"]) >= _dt(prev["arrives"]) + timedelta(minutes=seg.get("min_connection_minutes", 60))
                now = _flight_id(seg)
            elif item["kind"] == "inbound":
                seg = segments[item["anchor"]]
                prev = segments[item["id"]]
                ok = _dt(seg["departs"]) >= _dt(prev["arrives"]) + timedelta(minutes=seg.get("min_connection_minutes", 60))
                now = _flight_id(prev)
            elif item["kind"] == "bag":
                service = booking["services"][item["id"]]
                expected = [f"{segments[s]['flight']} {segments[s]['departs'][:10]}" for s in service["segments"]]
                now = list(service["routing"])
                ok = now == expected
            else:
                service = booking["services"][item["id"]]
                base = _dt(segments[service["segment"]][service["event"]])
                now = service["time"]
                if service["kind"] == "timed":
                    ok = now == (base + timedelta(minutes=service["offset_minutes"])).isoformat(timespec="minutes")
                else:
                    ok = base <= _dt(now)
            rows.append({"id": item["id"], "points_at_new_times": ok, "now": now})
        return rows


def _flight_id(segment: dict) -> str:
    return f"{segment['flight']} {segment['departs']}"


_SERVICES: dict[str, JourneyService] = {}


def service_for(conversation_id: str) -> JourneyService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = JourneyService(conversation_id)
    return _SERVICES[conversation_id]


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------


def _not_found() -> dict:
    return {"status": "not_found",
            "next_step": "Say you cannot find that booking on this account and ask the caller to check the "
                         "reference. Never say whether it belongs to someone else."}


def _frozen(service: JourneyService, ref: str) -> dict:
    desk = service.frozen[ref]
    return {"status": "blocked", "reason": "journey_frozen", "effects": 0, "booking": ref,
            "desk_reference": desk, "desk_reference_spoken": spoken_reference(desk),
            "next_step": ("An earlier change on this booking left a linked service unresolved, so the booking "
                          "is frozen for the travel desk. Make no further changes and do not repeat the "
                          "request. Give the travel-desk reference.")}


def look_up_trip(service: JourneyService, traveller_id: Optional[str], booking_value: Any,
                 caller_texts: Iterable[str] = ()) -> dict:
    if not clean(booking_value):
        return {"status": "trips", "trips": service.own_trips(traveller_id),
                "next_step": "Ask which trip the caller means."}
    ref, booking, _ = service.find_booking(traveller_id, booking_value, caller_texts)
    if booking is None:
        return {**_not_found(), "trips": service.own_trips(traveller_id)}
    services = []
    for sid, s in booking["services"].items():
        row = {"service": sid, "label": s["label"]}
        if s["kind"] == "bag":
            row["routing"] = s["routing"]
        else:
            row.update(time=s["time"], time_spoken=f"{spoken_date(s['time'])} at {spoken_time(s['time'])}")
            if s.get("time_meaning"):
                row["time_meaning"] = s["time_meaning"]
        services.append(row)
    result = {"status": "found", "booking": ref, "booking_spoken": spoken_code(ref), "trip": booking["trip"],
              "segments": [segment_summary(sid, s) for sid, s in booking["segments"].items()],
              "linked_services": services,
              "note": "This is the booking. Flight status (delays) is a separate fact: use check_flight_status."}
    if ref in service.frozen:
        result["frozen_for_travel_desk"] = spoken_reference(service.frozen[ref])
    return result


def check_flight_status(service: JourneyService, traveller_id: Optional[str], flight_number: Any,
                        date: Any) -> dict:
    runs = digit_runs(flight_number)
    number = next((r for r in runs if len(r) == 3), None)
    if number is None:
        return {"status": "not_found", "next_step": "Ask for the flight number."}
    flight = f"HZ {number}"
    day = parse_date(date)
    own = [s for ref, b in service.data["bookings"].items() if b["traveller_id"] == traveller_id
           for s in b["segments"].values() if s["flight"] == flight]
    if day is None and len(own) == 1:
        day = own[0]["departs"][:10]
    live = service.data["flight_status"].get(f"{flight} {day}")
    scheduled = next((s for s in own if s["departs"].startswith(day or "-")), None)
    if live is None and scheduled is None:
        return {"status": "not_found", "flight": flight,
                "next_step": "Say you have no status for that flight and date."}
    info = live or {"state": "scheduled", "departs": scheduled["departs"], "arrives": scheduled["arrives"]}
    return {"status": info["state"], "flight": flight, "flight_spoken": spoken_code(flight), "date": day,
            "departs": info["departs"], "arrives": info["arrives"],
            "departs_spoken": spoken_time(info["departs"]), "arrives_spoken": spoken_time(info["arrives"]),
            **({"note": info["note"]} if info.get("note") else {}),
            "booking_changed": False,
            "next_step": ("This is the flight's operational status only. It changes nothing on the booking: "
                          "no connection or service has been moved because of it. Use look_up_trip for the "
                          "booking.")}


def find_change_options(service: JourneyService, traveller_id: Optional[str], booking_value: Any,
                        segment_words: Any, caller_texts: Iterable[str] = ()) -> dict:
    ref, booking, _ = service.find_booking(traveller_id, booking_value, caller_texts)
    if booking is None:
        return _not_found()
    if ref in service.frozen:
        return _frozen(service, ref)
    how, ids = service.resolve_segment(booking, segment_words)
    segments = booking["segments"]
    if how == "flown":
        return {"status": "not_changeable", "reason": "segment_already_flown", "booking": ref,
                "segments": [segment_summary(sid, segments[sid]) for sid in ids],
                "next_step": "That flight has already been flown and cannot be changed."}
    if how != "resolved":
        return {"status": "needs_segment", "reason": "wrong_segment", "booking": ref,
                "segments": [segment_summary(sid, segments[sid]) for sid in ids],
                "next_step": "Ask the caller which of these flights they mean. Do not guess."}
    sid = ids[0]
    current = segments[sid]
    options = []
    for option in booking["options"].get(sid, []):
        if option["flight"] == current["flight"] and option["departs"] == current["departs"]:
            continue
        options.append({"option_id": option["id"], "flight": option["flight"],
                        "flight_spoken": spoken_code(option["flight"]),
                        "departs": option["departs"], "arrives": option["arrives"],
                        "departs_spoken": f"{spoken_date(option['departs'])} at {spoken_time(option['departs'])}",
                        "arrives_spoken": f"{spoken_date(option['arrives'])} at {spoken_time(option['arrives'])}"})
    return {"status": "options", "booking": ref, "segment": segment_summary(sid, current), "options": options,
            "next_step": ("If the caller already named the new flight or date, call prepare_journey_change with "
                          "that option_id now; otherwise read the options and ask which one.")}


def _labels(booking: dict, segment_id: str, option: dict, items: list[dict]) -> dict:
    segment = booking["segments"][segment_id]
    same_day = option["departs"][:10] == segment["departs"][:10]
    when = (f"at {spoken_time(option['departs'])} the same day" if same_day
            else f"on {spoken_date(option['departs'])} at {spoken_time(option['departs'])}")
    change = (f"your {route(segment)} flight on {spoken_date(segment['departs'])} to "
              f"{spoken_code(option['flight'])} {when}")
    shorts = [i["short"] for i in items]
    if not shorts:
        services = "no linked services"
    elif len(shorts) == 1:
        services = f"your {shorts[0]}"
    else:
        services = "your " + ", ".join(shorts[:-1]) + " and " + shorts[-1]
    return {"change_label": change, "services_label": services}


def memory_values(ref: str, booking: dict, segment_id: str, option: dict, items: list[dict]) -> dict:
    segment = booking["segments"][segment_id]
    values = {
        "draft_booking": ref,
        "draft_option": option["id"],
        "draft_segment": f"{segment_id} {_flight_id(segment)}",
        "draft_services": ",".join(i["id"] for i in items),
        **_labels(booking, segment_id, option, items),
    }
    for key, value in values.items():
        if len(value) >= MEMORY_VALUE_LIMIT:
            raise ValueError(f"memory value {key} is {len(value)} characters; Mantle cuts at {MEMORY_VALUE_LIMIT}")
    return values


def _option(booking: dict, option_id: Any) -> tuple[Optional[str], Optional[dict]]:
    wanted = clean(option_id).upper().replace(" ", "")
    for sid, options in booking["options"].items():
        for option in options:
            if option["id"] == wanted:
                return sid, option
    return None, None


def prepare_journey_change(service: JourneyService, traveller_id: Optional[str], booking_value: Any,
                           option_id: Any, caller_texts: Iterable[str] = ()) -> tuple[dict, dict]:
    """(result, memory values). Resolves the draft and its linked services; changes nothing."""
    ref, booking, _ = service.find_booking(traveller_id, booking_value, caller_texts)
    if booking is None:
        return _not_found(), {}
    if ref in service.frozen:
        return _frozen(service, ref), {}
    sid, option = _option(booking, option_id)
    if option is None:
        return {"status": "blocked", "reason": "wrong_segment", "effects": 0, "booking": ref,
                "next_step": "That option is not on this booking. Call find_change_options for the segment."}, {}
    segment = booking["segments"][sid]
    if segment["status"] != "open":
        return {"status": "not_changeable", "reason": "segment_already_flown", "booking": ref,
                "next_step": "That flight has already been flown and cannot be changed."}, {}
    if option["flight"] == segment["flight"] and option["departs"] == segment["departs"]:
        return {"status": "no_change", "booking": ref,
                "next_step": "The booking already has that flight; nothing to change."}, {}
    items = service.plan(booking, sid, option)
    memory = memory_values(ref, booking, sid, option, items)
    return {"status": "ready", "booking": ref, "segment": segment_summary(sid, segment),
            "new_flight": {"flight": option["flight"], "departs": option["departs"], "arrives": option["arrives"]},
            "linked_services": [{"service": i["id"], "label": i["label"]} for i in items], "effects": 0,
            "next_step": ("Call apply_journey_change for this booking straight away; the engine reads the change "
                          "and the linked services back and asks the caller to confirm.")}, memory


def apply_journey_change(service: JourneyService, traveller_id: Optional[str], memory: dict,
                         booking_value: Any, caller_texts: Iterable[str] = ()) -> dict:
    """Check every linked service, change the segment, re-point the services, reconcile. After confirmation."""
    ref, booking, _ = service.find_booking(traveller_id, booking_value, caller_texts)
    if booking is None:
        return _not_found()
    if ref in service.frozen:
        return _frozen(service, ref)
    sid, option = _option(booking, memory.get("draft_option"))
    segment = booking["segments"].get(sid or "")
    identity = bool(
        option is not None and segment is not None and memory.get("draft_booking") == ref
        and segment["status"] == "open"
        and memory.get("draft_segment") == f"{sid} {_flight_id(segment)}"
        and not (option["flight"] == segment["flight"] and option["departs"] == segment["departs"]))
    items = service.plan(booking, sid, option) if identity else []
    unreadable = [i for i in items if i.get("status_feed") != "ok"]
    checked = identity and not unreadable and ",".join(i["id"] for i in items) == memory.get("draft_services")
    facts = {"segment_identity_confirmed": identity, "dependent_services_checked": checked}
    reason = evaluate(facts, "request")
    if reason == "wrong_segment":
        return {"status": "blocked", "reason": reason, "effects": 0, "booking": ref, "facts": facts,
                "next_step": ("The confirmed draft is not a current, open segment of this booking. Change "
                              "nothing; call find_change_options again for the flight the caller means.")}
    if reason == "connection_not_checked":
        desk = _reference("TD", service.conversation_id, ref, "unchecked")
        return {"status": "blocked", "reason": reason, "effects": 0, "booking": ref, "facts": facts,
                "not_checked": [{"service": i["id"], "label": i["label"], "provider": i.get("provider")}
                                for i in unreadable] or [{"service": "draft", "label": "the services read back"}],
                "desk_reference": desk, "desk_reference_spoken": spoken_reference(desk),
                "next_step": ("Nothing was changed. A linked service could not be checked, so the travel desk "
                              "takes it from here with this reference. Do not retry the change.")}
    before = {"segment": _flight_id(segment), "services": {i["id"]: i["before"] for i in items}}
    service.apply(booking, sid, option, items)
    rows = service.reconcile(booking, items)
    facts["change_receipt_reconciled"] = all(r["points_at_new_times"] for r in rows)
    status, reason, effects = lab_outcome(facts)
    change_ref = _reference("HC", service.conversation_id, ref, option["id"], str(len(service.changes)))
    result = {
        "status": status, "reason": reason, "effects": effects, "booking": ref, "facts": facts,
        "change_reference": change_ref, "change_reference_spoken": spoken_reference(change_ref),
        "segment": {"segment": sid, "before": before["segment"], "after": _flight_id(booking["segments"][sid]),
                    "route": route(segment)},
        "linked_services": [
            {"service": i["id"], "kind": i["kind"], "label": i["label"], "short": i["short"], "state": i["state"],
             "before": i["before"],
             "after": row["now"], "points_at_new_times": row["points_at_new_times"],
             **({"detail": i["detail"]} if i.get("detail") else {})}
            for i, row in zip(items, rows)],
    }
    # Flat per-service states, for tracker checks: "moved", "still_valid", "re_tagged" or "unresolved".
    result["service_states"] = {r["service"]: (r["state"] if r["points_at_new_times"] else "unresolved")
                                for r in result["linked_services"]}
    if status == "pending":
        desk = _reference("TD", service.conversation_id, ref, change_ref)
        service.frozen[ref] = desk
        result.update(frozen=True, desk_reference=desk, desk_reference_spoken=spoken_reference(desk),
                      unresolved=[r["id"] for r in rows if not r["points_at_new_times"]],
                      next_step=("The flight changed but a linked service still points at the old times. The "
                                 "booking is frozen for the travel desk. Do not repeat the change or say "
                                 "everything is updated."))
    service.changes.append({"booking": ref, "option": option["id"], "status": status})
    return result


def discard_journey_change(memory: dict) -> dict:
    return {"status": "discarded", "effects": 0, "discarded_option": memory.get("draft_option") or None,
            "next_step": "Nothing was changed. Resolve the segment the caller wants now, if any."}


# ----------------------------------------------------------------------------
# Receipts the tools send to the caller themselves
# ----------------------------------------------------------------------------


def _at(moment: str, day: str) -> str:
    """'3:30 PM', or '3:30 PM on October 25' when the day differs from the new flight's."""
    return spoken_time(moment) + ("" if moment[:10] == day else f" on {spoken_date(moment)}")


def _service_sentence(row: dict, day: str) -> str:
    short, state, after = row["short"], row["state"], row["after"]
    if row["kind"] == "connection" and state == "moved":
        flight, departs = after.rsplit(" ", 1)
        return f"your {short} is now {spoken_code(flight)} at {_at(departs, day)}"
    if state == "moved":
        return f"your {short} moves to {_at(after, day)}"
    if state == "re_tagged":
        return f"your {short} is re-tagged"
    if row["kind"] == "cover":
        return f"your {short} still covers it"
    if row["kind"] in ("connection", "inbound"):
        return f"your {short} still connects"
    return f"your {short} is unchanged"


def _unresolved_sentence(row: dict) -> str:
    before = row["before"]
    if row["kind"] == "cover":
        return f"your {row['short']} was not changed: it still ends {spoken_date(before)} at {spoken_time(before)}"
    if row["kind"] in ("connection", "inbound"):
        return f"your {row['short']} no longer connects"
    return f"your {row['short']} was not changed: it is still {spoken_date(before)} at {spoken_time(before)}"


def customer_receipt(tool_name: str, result: dict) -> Optional[str]:
    """The receipt a tool speaks to the caller itself, or None. Kept short: on voice the tool waits
    while it is spoken, and that wait counts against tool_timeout."""
    status = result.get("status")
    if tool_name == "apply_journey_change" and status in ("succeeded", "pending"):
        seg = result["segment"]
        flight, departs = seg["after"].rsplit(" ", 1)
        day = departs[:10]
        text = (("Done: your" if status == "succeeded" else "Your")
                + f" {seg['route']} flight is now {spoken_code(flight)} at {spoken_time(departs)}, "
                f"{spoken_date(departs)}.")
        rows = result["linked_services"]
        parts = [_service_sentence(r, day) for r in rows if r["points_at_new_times"]]
        if parts:
            joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
            text += " " + joined[0].upper() + joined[1:] + "."
        if status == "pending":
            missing = [_unresolved_sentence(r) for r in rows if not r["points_at_new_times"]]
            joined = " and ".join(missing)
            text += (f" But {joined}, so I've frozen this booking for the travel desk, reference "
                     f"{result['desk_reference_spoken']}.")
        else:
            text += f" Change reference {result['change_reference_spoken']}."
        return text
    if tool_name == "apply_journey_change" and status == "blocked" and result.get("reason") == "connection_not_checked":
        names = " and ".join(f"{r['label']}" + (f" with {r['provider']}" if r.get("provider") else "")
                             for r in result.get("not_checked", []))
        return (f"I haven't changed anything on booking {spoken_code(result['booking'])}: I couldn't check your "
                f"{names}. I've passed it to the travel desk, reference {result['desk_reference_spoken']}.")
    return None
