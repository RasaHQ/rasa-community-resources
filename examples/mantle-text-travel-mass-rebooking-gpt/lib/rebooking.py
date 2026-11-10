"""Horizon Travel storm rebooking and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three rules of the casebook contract for ``travel-mass-rebooking``
(vendored as ``lib/fixtures/case-contract.json``):

- ``itinerary_constraints_met`` (request): the replacement goes to the case's
  destination, arrives in time for the onward flight still on the booking, and
  meets every requirement the passenger added in this conversation (an
  accessible connection). It is checked when the option is held and again at
  commit, because a requirement can arrive after the hold.
- ``capacity_hold_valid`` (request): the commit names a hold on this
  passenger's case, still active, not expired on the fixture clock, and it is
  the hold the engine asked the passenger to confirm. An expired hold is never
  reused: the case stays open and a new option is searched.
- ``replacement_commit_verified`` (receipt): after the commit, the booking
  service's ticket record is read back and must match the hold, the option and
  the case. When it cannot be read back the result is ``pending``: the hold
  stays until its stated expiry, with the unresolved services listed, and is
  never called confirmed.

An offer (a search result), a hold (capacity reserved until a stated time)
and a committed replacement (the booking service accepted it) are three
different results with three different statuses. Only the last one is a
rebooking.

Facts are computed from trusted data: the session's passenger id, the case
record, the capacity and booking services, the fixture clock and the
conversation's own messages. The model supplies a case reference, an option
id, a hold id, a commit reference, a flag for an accessible connection and a
reason. It never supplies a fact, a passenger id, a seat count or an outcome.
A requirement can be added by the model or by the passenger's own words; it
is never removed in chat. A fact that is not exactly ``True`` fails its rule,
as in the lab's ``evaluate``.

The fixture clock starts at ``as_of`` and moves ``minutes_per_passenger_message``
for every passenger message in the conversation, so a hold's expiry is
deterministic: a 5-minute hold made in one message has expired when the
passenger answers the confirmation in the next.

The organisation guard runs at import and is an allowlist: the fixture's
organisation must be the casebook contract's own fictional company, marked
fictional, and so must every other organisation field in the fixture.
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
DATA_FILE = FIXTURES / "horizon_disruption.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (rasa/mantle/prompts/memory_lines.py,
# MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5). Every value a tool writes to memory
# is one short field and must fit; tests/test_guard.py checks every fixture.
MEMORY_VALUE_LIMIT = 100

# Design fix for the silent complete_skill (the HarborCover claim build,
# examples/mantle-text-insurance-file-claim-claude): the tools send the
# passenger the outcome themselves through ToolContext.send, so the replacement
# reference, or the hold expiry and what is still open, reaches the passenger
# whatever the model does next. The `receipt-in-result-only` variant sets this
# to False.
TOOL_SENDS_RECEIPT = True

# Organisation fields the allowlist checks, wherever they appear in the fixture.
ORGANISATION_KEYS = ("organisation", "airline", "carrier", "operator", "partner", "company", "vendor")

# Passenger words that add the accessible-connection requirement to the case,
# whatever the model does with them. Stricter is always safe; the requirement
# is never removed in chat.
MOBILITY_RE = re.compile(
    r"\b(wheel\s?chair|accessible|step[- ]free|mobility|can(?:no|')t (?:do|manage|climb) stairs|no stairs|walker|crutches)\b",
    re.IGNORECASE,
)

# Wording that says a rebooking is confirmed. case-build/case_metric.py counts it
# in bot text for the case metric (confirmations without committed capacity);
# tests/test_guard.py keeps this copy and the spec's identical.
CONFIRMED_CLAIM_PATTERN = (
    r"\b(?:(?:you(?:'re|\s+are)|you've\s+been|you\s+have\s+been)\s+(?:now\s+|all\s+)?(?:rebooked|booked|confirmed)"
    r"|(?:rebooking|booking|seat|flight|change|replacement)\s+(?:is|has\s+been|was)\s+(?:now\s+)?(?:confirmed|committed|ticketed|done|complete)"
    r"|(?:i(?:'ve|\s+have)|we(?:'ve|\s+have))\s+(?:now\s+|successfully\s+)?(?:rebooked|booked|confirmed)\s+you)"
)
CONFIRMED_HEDGE_PATTERN = (
    r"\b(?:not|no|never|cannot|can't|won't|isn't|hasn't|haven't|wasn't|don't|until|unless|if|"
    r"whether|once|when|before|after|yet|pending|only)\b|n't\b"
)


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

    An allowlist, not a list of real names: any organisation field must be
    ``<allowed name> (fictional ...)``. Real institution names are also caught
    repository-wide by scripts/lint_repo.py.
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
SESSION_PASSENGER_ID = _DATA["session_passenger_id"]
OWNER = _CONTRACT["owner"]
DESK = "Horizon Travel disruption recovery desk"
ACCESSIBLE = "accessible_connection"


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


def _digest(*parts: Any, size: int = 5) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:size].upper()


_ID_RE = re.compile(r"[^A-Z0-9-]")


def normalise_id(value: Any) -> str:
    """Upper-case, spaces to hyphens, drop anything else: ' ht dc 40117 ' -> HT-DC-40117."""
    return _ID_RE.sub("", re.sub(r"\s+", "-", str(value or "").strip().upper()))


def passenger_messages(events: Iterable[Any]) -> list[str]:
    """The passenger's own messages, from tracker events (``UserUttered`` by class name)."""
    texts = []
    for event in events or ():
        if type(event).__name__ != "UserUttered":
            continue
        text = getattr(event, "text", None) or ""
        if text.startswith("/"):
            continue  # /session_start and other intents are not the passenger's words
        texts.append(text)
    return texts


def mentions_mobility_need(messages: Iterable[str]) -> bool:
    return any(MOBILITY_RE.search(m or "") for m in messages)


def clock_time(data_as_of: datetime, minutes_per_message: int, message_count: int) -> datetime:
    return data_as_of + timedelta(minutes=minutes_per_message * max(message_count, 0))


def clock_label(when: datetime) -> str:
    """'19:26 Boston time, 12 Nov' (the fixture's clock zone)."""
    return f"{when.strftime('%H:%M')} {_DATA['clock_label_zone']}, {when.day} {when.strftime('%b')}"


# ----------------------------------------------------------------------------
# The service: capacity, holds, the booking service and the cases
# ----------------------------------------------------------------------------


class RebookingService:
    """Cases, recovery inventory, holds and the booking service for one conversation."""

    def __init__(self, data: Optional[dict] = None) -> None:
        data = data or load_data()
        self.as_of = datetime.fromisoformat(data["as_of"])
        self.minutes_per_message = data["minutes_per_passenger_message"]
        self.default_hold_minutes = data["default_hold_minutes"]
        self.passengers: dict[str, dict] = data["passengers"]
        self.cases: dict[str, dict] = data["cases"]
        self.options: dict[str, dict] = data["options"]
        self.holds: dict[str, dict] = data["holds"]
        self.commits: dict[str, dict] = {}
        self.tickets: dict[str, dict] = {}
        self.desk_cases: dict[str, str] = {}
        self.sequence = 0

    def now(self, message_count: int) -> datetime:
        return clock_time(self.as_of, self.minutes_per_message, message_count)

    def case_owned(self, passenger_id: Optional[str], case_reference: str) -> Optional[dict]:
        case = self.cases.get(case_reference)
        return case if case is not None and passenger_id and case["passenger_id"] == passenger_id else None

    def hold_owned(self, passenger_id: Optional[str], hold_id: str) -> Optional[dict]:
        hold = self.holds.get(hold_id)
        return hold if hold is not None and passenger_id and hold["passenger_id"] == passenger_id else None

    def active_hold(self, case_reference: str, now: datetime) -> Optional[tuple[str, dict]]:
        for hold_id, hold in self.holds.items():
            if hold["case_reference"] == case_reference and hold["state"] in ("active", "commit_pending") \
                    and datetime.fromisoformat(hold["expires_at"]) > now:
                return hold_id, hold
        return None

    def expire_lapsed(self, now: datetime) -> None:
        """Holds past their expiry lapse on the clock; their seat goes back."""
        for hold in self.holds.values():
            if hold["state"] in ("active", "commit_pending") and datetime.fromisoformat(hold["expires_at"]) <= now:
                hold["state"] = "expired"
                option = self.options.get(hold["option_id"])
                if option is not None and hold.get("counted_seat", False):
                    option["seats"] += 1


_SERVICES: dict[str, RebookingService] = {}


def service_for(conversation_id: str) -> RebookingService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = RebookingService()
    return _SERVICES[conversation_id]


def passenger_profile(service: RebookingService, passenger_id: str = SESSION_PASSENGER_ID) -> dict:
    person = service.passengers[passenger_id]
    return {
        "passenger_id": passenger_id,
        "first_name": person["first_name"],
        "last_name": person["last_name"],
        "disruption_case": person["disruption_case"],
    }


# ----------------------------------------------------------------------------
# Itinerary constraints
# ----------------------------------------------------------------------------


def requirements_for(case: dict, messages: Iterable[str], asked_accessible: bool = False) -> list[str]:
    """The case's requirements: recorded ones, plus any added now. Never fewer."""
    reqs = list(case.get("requirements") or [])
    if (asked_accessible or mentions_mobility_need(messages)) and ACCESSIBLE not in reqs:
        reqs.append(ACCESSIBLE)
    return reqs


def unmet_constraints(case: dict, option: dict, requirements: Iterable[str]) -> list[str]:
    """What an option fails on, in words, or [] when it meets every constraint."""
    c = case["constraints"]
    unmet = []
    if option["origin"] != c["origin"] or option["destination"] != c["destination"]:
        unmet.append(f"goes {option['origin']}-{option['destination']}, not {c['origin']}-{c['destination']}")
    if datetime.fromisoformat(option["arrives"]) > datetime.fromisoformat(c["arrive_by"]):
        unmet.append(f"arrives after {c['arrive_by'][:16].replace('T', ' ')} UTC ({c['arrive_by_reason']})")
    if ACCESSIBLE in requirements and option.get("connection") and not option["connection"]["step_free"]:
        unmet.append(f"connection is not step-free: {option['connection']['note']}")
    return unmet


def open_services(option: dict, requirements: Iterable[str]) -> list[str]:
    """Services the booking service does not settle at commit; the passenger is told."""
    services = list(option.get("services") or [])
    if ACCESSIBLE in requirements:
        where = option["connection"]["airport"] if option.get("connection") else "boarding"
        services.append(f"wheelchair assistance at {where}")
    return services


def services_text(services: list[str]) -> str:
    return "; ".join(services) if services else "nothing"


def _option_view(case: dict, option_id: str, option: dict, requirements: list[str]) -> dict:
    unmet = unmet_constraints(case, option, requirements)
    view = {
        "option_id": option_id,
        "flight": option["label"],
        "connection": option["connection"]["note"] if option.get("connection") else "nonstop",
        "seats_shown": option["seats"],
        "meets_constraints": not unmet,
        "hold_minutes": option.get("hold_minutes", _DATA["default_hold_minutes"]),
    }
    if unmet:
        view["unmet"] = unmet
    if option.get("hold_note"):
        view["hold_note"] = option["hold_note"]
    return view


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------

NOT_FOUND_CASE_STEP = (
    "Say you cannot find that disruption case for this passenger and ask them to check it. "
    "Do not say whether it exists or whose it is."
)


def _blocked(reason: str, next_step: str, **extra: Any) -> dict:
    return {"status": "blocked", "reason": reason, **extra, "effects": 0, "next_step": next_step}


def _case_not_found(case_reference: str) -> dict:
    # Another passenger's case and an unknown reference get the same payload.
    return {"status": "not_found", "case_reference": case_reference, "effects": 0, "next_step": NOT_FOUND_CASE_STEP}


def _record_requirements(case: dict, requirements: list[str]) -> None:
    for req in requirements:
        if req not in case["requirements"]:
            case["requirements"].append(req)


def disruption_case(service: RebookingService, passenger_id: Optional[str], case_reference: str,
                    message_count: int) -> dict:
    ref = normalise_id(case_reference)
    case = service.case_owned(passenger_id, ref)
    if case is None:
        return _case_not_found(ref)
    now = service.now(message_count)
    service.expire_lapsed(now)
    active = service.active_hold(ref, now)
    result = {
        "status": "found",
        "case_reference": ref,
        "case_status": case["status"],
        "booking_reference": case["booking_reference"],
        "cancelled_flight": case["cancelled_flight"],
        "onward_flight": case["onward_flight"],
        "must_arrive_by": f"{case['constraints']['arrive_by'][:16].replace('T', ' ')} UTC ({case['constraints']['arrive_by_reason']})",
        "requirements": list(case["requirements"]),
        "clock": clock_label(now),
        "active_hold": None,
        "replacement": case.get("replacement"),
        "desk_case": case.get("desk_case"),
    }
    if active:
        hold_id, hold = active
        result["active_hold"] = {"hold_id": hold_id, "flight": service.options[hold["option_id"]]["label"],
                                 "state": hold["state"], "expires": clock_label(datetime.fromisoformat(hold["expires_at"]))}
    expired = [hid for hid, h in service.holds.items() if h["case_reference"] == ref and h["state"] == "expired"]
    if expired:
        result["expired_holds"] = expired
    result["next_step"] = (
        "Report the case state. A replacement exists only if replacement is set. An expired hold "
        "cannot be used; search for a new option."
    )
    return result


def search_options(service: RebookingService, passenger_id: Optional[str], case_reference: str,
                   messages: list[str], accessible_connection: bool = False) -> dict:
    """Recovery offers for the case. An offer is not a hold."""
    ref = normalise_id(case_reference)
    case = service.case_owned(passenger_id, ref)
    if case is None:
        return _case_not_found(ref)
    if case["status"] == "rebooked":
        return _already_rebooked(case, ref)
    reqs = requirements_for(case, messages, accessible_connection)
    _record_requirements(case, reqs)
    now = service.now(len(messages))
    service.expire_lapsed(now)
    views = [_option_view(case, oid, o, reqs) for oid, o in sorted(service.options.items(), key=lambda kv: kv[1]["departs"])
             if o["origin"] == case["constraints"]["origin"] and o["destination"] == case["constraints"]["destination"]]
    usable = [v for v in views if v["meets_constraints"] and v["seats_shown"] > 0]
    return {
        "status": "found" if usable else "no_usable_options",
        "case_reference": ref,
        "requirements": reqs,
        "options": views,
        "clock": clock_label(now),
        "note": "These are offers, not holds. Seats shown can go to other passengers until hold_recovery_option succeeds.",
        "next_step": (
            "Offer only options with meets_constraints true, with departure, arrival and connection. For one that "
            "does not, say what it fails on. When the passenger picks one, call hold_recovery_option."
            if usable else
            "Nothing usable is left. Call request_recovery_desk with the case reference."
        ),
    }


def _already_rebooked(case: dict, ref: str) -> dict:
    return _blocked(
        "already_rebooked",
        "This case already has a committed replacement. Give its reference; do not hold or commit another.",
        case_reference=ref, replacement=case.get("replacement"),
    )


def hold_option(service: RebookingService, passenger_id: Optional[str], case_reference: str, option_id: str,
                messages: list[str], conversation_id: str, accessible_connection: bool = False) -> dict:
    """Reserve one seat on an option until a stated time, or nothing."""
    ref = normalise_id(case_reference)
    oid = normalise_id(option_id)
    case = service.case_owned(passenger_id, ref)
    if case is None:
        return _case_not_found(ref)
    if case["status"] == "rebooked":
        return _already_rebooked(case, ref)
    option = service.options.get(oid)
    if option is None:
        return {"status": "not_found", "option_id": oid, "effects": 0,
                "next_step": "No recovery option has that id. Search again and use an option_id from the results."}
    reqs = requirements_for(case, messages, accessible_connection)
    _record_requirements(case, reqs)
    now = service.now(len(messages))
    service.expire_lapsed(now)
    unmet = unmet_constraints(case, option, reqs)
    if unmet:
        return _blocked(
            "unusable_itinerary",
            ("Nothing was held. Say what this option fails on. Offer an option that meets the case's constraints "
             "(search_recovery_options). A constraint on the case, such as the onward flight, cannot be waived in "
             "this chat; if the passenger wants to change it, call request_recovery_desk."),
            case_reference=ref, option_id=oid, flight=option["label"], unmet=unmet, requirements=reqs,
            facts={"itinerary_constraints_met": False},
        )
    active = service.active_hold(ref, now)
    if active is not None:
        hold_id, hold = active
        return _blocked(
            "active_hold_exists",
            ("One option can be held at a time. If the passenger is switching, call release_hold for the active "
             "hold first, then hold this one."),
            case_reference=ref, option_id=oid,
            active_hold={"hold_id": hold_id, "flight": service.options[hold["option_id"]]["label"],
                         "expires": clock_label(datetime.fromisoformat(hold["expires_at"]))},
        )
    if option.get("gone_before_hold"):
        option["seats"] = 0
    if option["seats"] <= 0:
        return {
            "status": "unavailable", "reason": "capacity_gone", "case_reference": ref, "option_id": oid,
            "flight": option["label"], "detail": option.get("gone_detail", "No seats are left on this option."),
            "effects": 0,
            "next_step": ("Nothing is held and nothing is booked. Say the seat is gone and offer the other options "
                          "that meet the constraints. Never confirm or commit this option."),
        }
    service.sequence += 1
    hold_id = f"HT-RH-{_digest(conversation_id, oid, service.sequence)}"
    minutes = option.get("hold_minutes", service.default_hold_minutes)
    expires = now + timedelta(minutes=minutes)
    option["seats"] -= 1
    services = open_services(option, reqs)
    service.holds[hold_id] = {
        "case_reference": ref, "passenger_id": passenger_id, "option_id": oid, "state": "active",
        "held_at": now.isoformat(), "expires_at": expires.isoformat(), "counted_seat": True,
        "open_services": services, "made_in": "this chat",
    }
    return {
        "status": "held",
        "hold_id": hold_id,
        "case_reference": ref,
        "option_id": oid,
        "flight": option["label"],
        "held_until": clock_label(expires),
        "hold_minutes": minutes,
        "open_services": services,
        "requirements": reqs,
        "facts": {"itinerary_constraints_met": True, "capacity_hold_valid": True},
        "next_step": (
            "A hold is not a rebooking. In this same turn, call commit_rebooking with this hold_id. That call shows "
            "the passenger the hold time and asks them to confirm; nothing is booked until the booking service "
            "accepts it. Do not ask a confirmation question of your own."
        ),
    }


def resume_hold(service: RebookingService, passenger_id: Optional[str], hold_id: str, messages: list[str]) -> dict:
    """Pick up a hold the passenger made elsewhere (the app), if it is still valid."""
    hid = normalise_id(hold_id)
    hold = service.hold_owned(passenger_id, hid)
    if hold is None:
        return {"status": "not_found", "hold_id": hid, "effects": 0,
                "next_step": "No hold with that id on this passenger's case."}
    now = service.now(len(messages))
    service.expire_lapsed(now)
    option = service.options[hold["option_id"]]
    if hold["state"] != "active":
        return _blocked(
            "hold_expired" if hold["state"] == "expired" else "hold_not_active",
            ("That hold cannot be used: it expired or was released, and its seat may have gone to another passenger. "
             "Do not reuse it. The disruption case stays open; search for a new option with search_recovery_options."),
            hold_id=hid, flight=option["label"], hold_state=hold["state"],
            expired_at=clock_label(datetime.fromisoformat(hold["expires_at"])),
            facts={"capacity_hold_valid": False},
        )
    case = service.cases[hold["case_reference"]]
    reqs = requirements_for(case, messages)
    _record_requirements(case, reqs)
    unmet = unmet_constraints(case, option, reqs)
    if unmet:
        return _blocked("unusable_itinerary", "Say what the held option fails on and offer to release it and search.",
                        hold_id=hid, flight=option["label"], unmet=unmet,
                        facts={"itinerary_constraints_met": False})
    hold["open_services"] = open_services(option, reqs)
    return {
        "status": "held", "hold_id": hid, "case_reference": hold["case_reference"], "option_id": hold["option_id"],
        "flight": option["label"], "held_until": clock_label(datetime.fromisoformat(hold["expires_at"])),
        "open_services": hold["open_services"], "requirements": reqs,
        "next_step": "In this same turn, call commit_rebooking with this hold_id.",
    }


def release_hold(service: RebookingService, passenger_id: Optional[str], hold_id: str, message_count: int) -> dict:
    hid = normalise_id(hold_id)
    hold = service.hold_owned(passenger_id, hid)
    if hold is None:
        return {"status": "not_found", "hold_id": hid, "effects": 0,
                "next_step": "No hold with that id on this passenger's case."}
    service.expire_lapsed(service.now(message_count))
    if hold["state"] != "active":
        return {"status": "not_active", "hold_id": hid, "state": hold["state"], "effects": 0,
                "next_step": "That hold is not active, so there is nothing to release."}
    hold["state"] = "released"
    if hold.get("counted_seat"):
        service.options[hold["option_id"]]["seats"] += 1
    return {
        "status": "released", "hold_id": hid, "case_reference": hold["case_reference"],
        "flight": service.options[hold["option_id"]]["label"], "effects": 0,
        "next_step": ("Nothing was booked for this hold and its seat went back. The disruption case stays open. "
                      "If the passenger has a new requirement, search again with it."),
    }


def _booking_service_commit(service: RebookingService, hold_id: str, hold: dict, option: dict,
                            commit_reference: str) -> Optional[str]:
    """The booking service's answer: a ticket record id, or None when it did not accept the change yet."""
    if option["commit_outcome"] != "committed":
        return None
    ticket = f"HT-TK-{_digest(commit_reference, 'ticket')}"
    service.tickets[ticket] = {"hold_id": hold_id, "option_id": hold["option_id"],
                               "case_reference": hold["case_reference"], "state": "ticketed"}
    return ticket


def commit_rebooking(service: RebookingService, passenger_id: Optional[str], confirmed_hold_id: Optional[str],
                     hold_id: str, messages: list[str], conversation_id: str) -> dict:
    """Send one confirmed hold to the booking service and read the ticket back."""
    hid = normalise_id(hold_id)
    hold = service.hold_owned(passenger_id, hid)
    now = service.now(len(messages))
    if hold is not None and hold.get("commit_reference"):
        # A repeated commit on the same hold returns the stored result: the
        # booking service is never asked twice for one hold.
        stored = service.commits[hold["commit_reference"]]
        return {**stored, "effects": 0, "replay": True,
                "next_step": "This hold was already sent to the booking service; nothing new happened. Report the stored result."}
    service.expire_lapsed(now)
    if hold is None:
        return _blocked(
            "hold_expired",
            ("Nothing was booked. There is no hold with that id on this passenger's case. Call "
             "search_recovery_options and hold_recovery_option for the option the passenger wants."),
            hold_id=hid, hold_state=None, facts={"capacity_hold_valid": False},
        )
    case = service.cases.get(hold["case_reference"]) if hold is not None else None
    option = service.options.get(hold["option_id"]) if hold is not None else None
    reqs = requirements_for(case, messages) if case is not None else []
    if case is not None:
        _record_requirements(case, reqs)
    unmet = unmet_constraints(case, option, reqs) if case is not None else ["no hold"]
    facts = {
        "itinerary_constraints_met": case is not None and not unmet,
        "capacity_hold_valid": (
            hold is not None
            and hold["state"] == "active"
            and datetime.fromisoformat(hold["expires_at"]) > now
            and bool(confirmed_hold_id)
            and hid == normalise_id(confirmed_hold_id)
        ),
    }
    base = {"hold_id": hid, "case_reference": hold["case_reference"] if hold else None,
            "flight": option["label"] if option else None, "clock": clock_label(now)}
    reason = evaluate(facts, "request")
    if reason == "unusable_itinerary":
        released = False
        if hold is not None and hold["state"] == "active":
            hold["state"] = "released"
            released = True
            if hold.get("counted_seat"):
                option["seats"] += 1
        return _blocked(
            reason,
            ("Nothing was booked. The held option does not meet the passenger's needs, so its hold was released and "
             "the seat went back. Say what it fails on, then search again with the requirement."),
            **base, unmet=unmet, requirements=reqs, hold_released=released, facts=facts,
        )
    if reason:
        expired_at = clock_label(datetime.fromisoformat(hold["expires_at"])) if hold is not None else None
        return _blocked(
            reason,
            ("Nothing was booked. The hold is not valid: it expired before the booking service accepted it, was "
             "released, or is not the hold the passenger confirmed. Never reuse it. The disruption case stays open "
             f"({base['case_reference'] or 'the passenger case'}): call search_recovery_options for a new option."),
            **base, hold_state=hold["state"] if hold is not None else None, expired_at=expired_at,
            case_status=case["status"] if case is not None else None, facts=facts,
        )

    # Commit: the booking service is separate from the capacity service.
    service.sequence += 1
    commit_reference = f"HT-CM-{_digest(conversation_id, hid)}"
    hold["commit_reference"] = commit_reference
    ticket = _booking_service_commit(service, hid, hold, option, commit_reference)
    # Receipt: read the ticket record back and compare it with the hold.
    record = service.tickets.get(ticket or "")
    facts["replacement_commit_verified"] = (
        record is not None
        and record["hold_id"] == hid
        and record["option_id"] == hold["option_id"]
        and record["case_reference"] == hold["case_reference"]
        and record["state"] == "ticketed"
    )
    receipt_failure = evaluate(facts, "receipt")
    services = list(hold.get("open_services") or open_services(option, reqs))
    result = {**base, "commit_reference": commit_reference, "option_id": hold["option_id"],
              "open_services": services, "effects": 1, "replay": False}
    if receipt_failure:
        hold["state"] = "commit_pending"
        result.update({
            "status": "pending",
            "reason": receipt_failure,
            "replacement_reference": None,
            "hold_state": "held, not confirmed",
            "held_until": clock_label(datetime.fromisoformat(hold["expires_at"])),
            "detail": option.get("queued_detail", "The booking service has not accepted the change."),
            "unresolved_services": ["booking service acceptance and ticket reissue", *services],
            "case_status": case["status"],
            "facts": facts,
            "next_step": (
                "Not rebooked yet. Say the booking service has not accepted it, that the seat is held until "
                "held_until, and list unresolved_services. Never call it confirmed or booked. Do not commit or hold "
                "again. Call check_rebooking_status with the commit_reference; if it is still pending, call "
                "request_recovery_desk."
            ),
        })
    else:
        hold["state"] = "committed"
        replacement = f"HT-RB-{_digest(commit_reference, 'replacement')}"
        case["status"] = "rebooked"
        case["replacement"] = {"replacement_reference": replacement, "flight": option["label"], "ticket": ticket}
        result.update({
            "status": "succeeded",
            "reason": "verified_fixture_receipt",
            "replacement_reference": replacement,
            "ticket": ticket,
            "onward_flight": case["onward_flight"],
            "case_status": "rebooked",
            "facts": facts,
            "next_step": ("Give the replacement reference, the flight and anything in open_services. The onward "
                          "flight stays on the booking."),
        })
    service.commits[commit_reference] = {k: v for k, v in result.items() if k not in ("effects", "replay", "next_step")}
    return result


def rebooking_status(service: RebookingService, passenger_id: Optional[str], commit_reference: str,
                     message_count: int) -> dict:
    ref = normalise_id(commit_reference)
    stored = service.commits.get(ref)
    hold = service.hold_owned(passenger_id, stored["hold_id"]) if stored else None
    if stored is None or hold is None:
        return {"status": "not_found", "commit_reference": ref,
                "next_step": "No commit with that reference on this passenger's case."}
    now = service.now(message_count)
    service.expire_lapsed(now)
    if stored["status"] == "succeeded":
        return {"status": "committed", "commit_reference": ref, "replacement_reference": stored["replacement_reference"],
                "flight": stored["flight"], "next_step": "Give the replacement reference."}
    return {
        "status": "still_pending",
        "commit_reference": ref,
        "flight": stored["flight"],
        "hold_state": "held, not confirmed" if hold["state"] == "commit_pending" else hold["state"],
        "held_until": clock_label(datetime.fromisoformat(hold["expires_at"])),
        "unresolved_services": stored.get("unresolved_services"),
        "next_step": ("The booking service still has not accepted it. Do not call it confirmed. Call "
                      "request_recovery_desk with the case reference and give the desk reference."),
    }


def recovery_desk(service: RebookingService, passenger_id: Optional[str], case_reference: str, reason: str,
                  message_count: int) -> dict:
    ref = normalise_id(case_reference)
    case = service.case_owned(passenger_id, ref)
    if case is None:
        return _case_not_found(ref)
    replay = ref in service.desk_cases
    desk = service.desk_cases.get(ref) or f"HT-DRD-{_digest(passenger_id, ref)}"
    service.desk_cases[ref] = desk
    case["desk_case"] = desk
    now = service.now(message_count)
    service.expire_lapsed(now)
    pending = [h for h in service.holds.values() if h["case_reference"] == ref and h["state"] == "commit_pending"]
    return {
        "status": "routed",
        "desk_reference": desk,
        "case_reference": ref,
        "case_status": case["status"],
        "pending_commit": pending[0]["commit_reference"] if pending else None,
        "reason": " ".join(str(reason or "").split())[:200],
        "replay": replay,
        "owner": OWNER,
        "next_review_step": ("The disruption recovery desk works storm cases in order and replies in this chat "
                             "thread. Until it does, nothing new is booked."),
        "next_step": "Give the desk reference. Do not promise a flight or a time.",
    }


# ----------------------------------------------------------------------------
# Memory the tools write, and the receipt the tools send (TOOL_SENDS_RECEIPT)
# ----------------------------------------------------------------------------

HELD_KEYS = ("held_hold_id", "held_flight", "held_until", "held_open_services")


def held_memory(result: dict) -> dict:
    """Skill-memory values for a hold result: one short field each (MEMORY_VALUE_LIMIT)."""
    values = {
        "held_hold_id": result["hold_id"],
        "held_flight": result["flight"],
        "held_until": result["held_until"],
        "held_open_services": services_text(result.get("open_services") or []),
    }
    for key, value in values.items():
        if len(value) > MEMORY_VALUE_LIMIT:
            raise ValueError(f"{key} is {len(value)} characters; Mantle would cut it at {MEMORY_VALUE_LIMIT}")
    return values


def customer_receipt(tool: str, result: dict) -> Optional[str]:
    """The message a tool sends the passenger for an outcome they must see, or None."""
    status, reason = result.get("status"), result.get("reason")
    if result.get("replay"):
        return None
    if tool == "commit_rebooking" and status == "succeeded":
        return (f"Rebooked: {result['replacement_reference']}, {result['flight']}. The booking service accepted it and "
                f"issued ticket record {result['ticket']}. Your onward flight stays on the booking: "
                f"{result['onward_flight']}. Still open: {services_text(result.get('open_services') or [])}.")
    if tool == "commit_rebooking" and status == "pending":
        return (f"Not confirmed yet: the booking service has not accepted the change to {result['flight']}. Your seat "
                f"is held until {result['held_until']}. Unresolved: {'; '.join(result['unresolved_services'])}. "
                f"Commit reference {result['commit_reference']}.")
    if tool == "commit_rebooking" and reason == "hold_expired" and result.get("hold_state") == "expired":
        return (f"Not rebooked: the hold on {result['flight']} expired at {result['expired_at']} before the booking "
                f"service accepted it, so nothing was booked. Your disruption case {result['case_reference']} stays "
                "open and I will look for a new option.")
    if tool == "commit_rebooking" and reason == "unusable_itinerary":
        return (f"Not rebooked: {result['flight']} does not meet your needs ({'; '.join(result['unmet'])}). "
                "Nothing was booked and that hold is released.")
    if tool == "check_rebooking_status" and status == "committed":
        return f"Rebooked: {result['replacement_reference']}, {result['flight']}. The booking service has accepted it."
    if tool == "request_recovery_desk" and status == "routed":
        return (f"Sent to the {DESK}: {result['desk_reference']} for case {result['case_reference']}. Nothing new is "
                "booked until the desk replies.")
    return None
