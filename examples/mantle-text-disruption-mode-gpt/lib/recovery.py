"""Horizon Travel disruption recovery and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the three request rules of the casebook contract for
``disruption-mode`` (vendored as ``lib/fixtures/case-contract.json``) at the
moment a seat is held:

- ``incident_revision_current``: the option list the passenger chose from was
  built at the incident revision that is current when the hold is placed.
  Every search records the revision it was built at. A later revision (the
  storm spreads, a flight on the list is cancelled) makes the list stale, and
  the list is voided so the passenger chooses again from a new one.
- ``capacity_reserved``: the inventory service places the hold when the tool
  runs. The seat count a search shows is a read that lags the inventory
  during a disruption, never a reservation. When the inventory has no seat,
  or the hold service cannot confirm holds for the route, nothing is held.
- ``recovery_channel_available``: this chat can hold a seat only on a ticket
  Horizon issued. A ticket issued by a partner airline has no recovery
  channel here; a provisional hold is released in the same call.

A fact must be exactly ``True``, as in the lab's ``evaluate``. Facts are
computed from trusted data only: the signed-in session's passenger id, the
incident service, the inventory and the booking record. The model supplies
the passenger's words for a booking, and an option id or hold id copied from
a tool result. It never supplies a fact, a seat count, a revision or an
outcome.

The receipt is the case's: a held recovery option with its expiry, or an
honest queued status. Nothing in this chat confirms a journey, so no result
ever says one is confirmed (``journey_confirmed`` is always ``False``).

The organisation guard runs at import and is an allowlist: every
organisation field in the fixture must be the casebook contract's own
fictional organisation, marked ``(fictional ...)``.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "horizon_disruption.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (rasa/mantle/prompts/memory_lines.py,
# MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5; found in the GPT quote and
# diagnostics builds). Every value a tool writes to memory is one short field
# and must fit; tests/test_guard.py checks every fixture value.
MEMORY_VALUE_LIMIT = 100

# The engine's confirmation question for hold_recovery_option
# (skills/disruption_recovery/responses.yml).
CONFIRM_UTTER = "utter_confirm_hold"

# Fix for the silent complete_skill (found in the Northgate transfer and
# HarborCover builds): the tools send the passenger the outcome themselves
# through ToolContext.send, so a hold id, its expiry or a queue position
# reaches the passenger whatever the model does next. The
# `receipt-in-result-only` variant sets this to False.
TOOL_SENDS_RECEIPT = True


class FictionalOrganisationError(ValueError):
    """The fixture does not describe the casebook's fictional organisation."""


# Organisation fields the allowlist checks, wherever they appear in the fixture.
ORGANISATION_KEYS = ("organisation", "carrier", "airline", "operator", "partner", "issuer")


def load_contract() -> dict:
    return json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))


def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def allowed_organisations(contract: dict) -> frozenset[str]:
    return frozenset({contract["organisation"]})


def _organisation_fields(value: Any, path: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            here = f"{path}.{key}" if path else key
            if key in ORGANISATION_KEYS and isinstance(item, str):
                yield here, item
            else:
                yield from _organisation_fields(item, here)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _organisation_fields(item, f"{path}[{i}]")


def assert_fictional(data: dict, contract: dict) -> None:
    """Refuse fixture data whose organisations are not the casebook's fictional one.

    An allowlist, not a list of real names: every organisation field must read
    ``<allowed name> (fictional ...)``.
    """
    allowed = allowed_organisations(contract)
    found = list(_organisation_fields(data))
    if not any(key == "organisation" for key, _ in found):
        raise FictionalOrganisationError("the fixture must name its organisation")
    for key, text in found:
        name, _, rest = text.partition(" (")
        if name not in allowed:
            raise FictionalOrganisationError(f"{key} {name!r} is not the casebook's organisation {sorted(allowed)}")
        if not rest.lower().startswith("fictional"):
            raise FictionalOrganisationError(f"{key} must be marked '(fictional ...)': {text!r}")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")


_CONTRACT = load_contract()
_DATA = load_data()
assert_fictional(_DATA, _CONTRACT)
ORGANISATION = _CONTRACT["organisation"]
SESSION_PASSENGER_ID = _DATA["session_passenger"]
INCIDENT_ID = _DATA["incident"]["incident_id"]


def request_rules(contract: Optional[dict] = None) -> list[dict]:
    return [r for r in (contract or _CONTRACT)["rules"] if r["phase"] == "request"]


def evaluate(facts: dict, contract: Optional[dict] = None, phase: str = "request") -> Optional[str]:
    """The lab's evaluate: the first rule of the phase whose fact is not exactly True."""
    for rule in (contract or _CONTRACT)["rules"]:
        if rule["phase"] == phase and facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


NOW = _DATA["now"].split("T")[1]
CLOCK = _DATA["clock_label"]


# ---------------------------------------------------------------------------
# Per-conversation service state: the incident, the inventory and the holds
# ---------------------------------------------------------------------------


class Disruption:
    """One conversation's view of the synthetic disruption services."""

    def __init__(self) -> None:
        data = copy.deepcopy(_DATA)
        self.data = data
        self.revision: int = data["incident"]["start_revision"]
        self.advanced = False
        self.inventory = {oid: o["inventory"] for oid, o in data["options"].items()}
        self.searches: dict[str, dict] = {}
        self.holds: dict[str, dict] = {}
        for hold_id, h in data["existing_holds"].items():
            state = h["state"]
            if state == "active" and _minutes(h["expires"]) <= _minutes(NOW):
                state = "expired"
            self.holds[hold_id] = {"booking": h["booking"], "option": h["option"], "expires": h["expires"],
                                   "state": state, "placed_in": h["placed_in"]}
            if state == "active":
                self.inventory[h["option"]] -= 1
        self.queue: dict[str, dict] = {}
        self.hold_count = 0

    def booking(self, ref: str) -> dict:
        return self.data["bookings"][ref]

    def option(self, option_id: str) -> Optional[dict]:
        return self.data["options"].get(option_id)

    def active_hold(self, booking_ref: str) -> Optional[str]:
        for hold_id, h in self.holds.items():
            if h["booking"] == booking_ref and h["state"] == "active":
                return hold_id
        return None

    def options_now(self, booking_ref: str) -> list[str]:
        return [oid for oid, o in self.data["options"].items()
                if o["booking"] == booking_ref and self.revision in o["revisions"]]


_SERVICES: dict[str, Disruption] = {}


def service_for(conversation_id: str) -> Disruption:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = Disruption()
    return _SERVICES[conversation_id]


# ---------------------------------------------------------------------------
# Session and booking resolution
# ---------------------------------------------------------------------------


def session_profile(passenger_id: str = SESSION_PASSENGER_ID) -> dict:
    p = _DATA["passengers"][passenger_id]
    trips = "; ".join(f"{b['city']} {ref}" for ref, b in _DATA["bookings"].items()
                      if b["passenger_id"] == passenger_id)
    return {"passenger_id": passenger_id, "first_name": p["first_name"], "affected_trips": trips}


REF_RE = re.compile(r"\b(?:HT-?)?([0-9][A-Z][0-9][A-Z][0-9])\b", re.IGNORECASE)


def resolve_booking(passenger_id: Optional[str], words: str) -> tuple[Optional[str], dict]:
    """The signed-in passenger's booking the words name, or a blocked result.

    Another passenger's booking reference gets the same answer as one that
    does not exist.
    """
    if not passenger_id:
        return None, {"status": "blocked", "reason": "no_signed_in_passenger"}
    mine = {ref: b for ref, b in _DATA["bookings"].items() if b["passenger_id"] == passenger_id}
    text = (words or "").strip().lower()
    trips = [f"{b['city']} ({ref})" for ref, b in mine.items()]
    m = REF_RE.search(text)
    if m:
        ref = "HT-" + m.group(1).upper()
        if ref in mine:
            return ref, {"status": "resolved", "booking_ref": ref}
        return None, {"status": "blocked", "reason": "booking_not_found",
                      "next_step": "Say there is no such booking on this account. Never say whether it is someone else's.",
                      "your_bookings": trips}
    hits = [ref for ref, b in mine.items()
            if any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text) for w in b["words"])]
    if len(hits) == 1:
        return hits[0], {"status": "resolved", "booking_ref": hits[0]}
    if hits:
        return None, {"status": "blocked", "reason": "ambiguous_booking",
                      "candidates": [f"{mine[r]['city']} ({r})" for r in hits],
                      "next_step": "Ask which booking the passenger means."}
    return None, {"status": "blocked", "reason": "booking_not_found",
                  "next_step": "Ask which of the passenger's bookings they mean.", "your_bookings": trips}


def _hold_view(svc: Disruption, hold_id: str) -> dict:
    h = svc.holds[hold_id]
    return {"hold_id": hold_id, "booking_ref": h["booking"], "option": svc.option(h["option"])["summary"],
            "hold_state": h["state"], "expires": f"{h['expires']} {CLOCK}, 30 Sep", "journey_confirmed": False}


# ---------------------------------------------------------------------------
# Information: the incident, existing holds
# ---------------------------------------------------------------------------


def incident_status(svc: Disruption, passenger_id: Optional[str], booking_words: Optional[str] = None) -> dict:
    result = {"status": "read", "incident_id": INCIDENT_ID, "incident_revision": svc.revision,
              "incident_summary": svc.data["incident"]["revisions"][str(svc.revision)], "read_at": f"{NOW} {CLOCK}",
              "note": "Incident status is information. It does not hold or promise a seat."}
    if booking_words:
        ref, resolved = resolve_booking(passenger_id, booking_words)
        if ref is None:
            return {**result, "booking": resolved}
        b = svc.booking(ref)
        hold = svc.active_hold(ref)
        result["booking"] = {
            "booking_ref": ref, "flight": b["cancelled_flight"], "flight_status": "cancelled",
            "ticket_issued_by": "Horizon" if b["ticketed_by"] == "horizon" else "a partner airline",
            "active_hold": _hold_view(svc, hold) if hold else None,
            "in_recovery_queue": svc.queue.get(ref, {}).get("queue_reference"),
        }
    return result


def check_hold(svc: Disruption, passenger_id: Optional[str], hold_id: str) -> dict:
    key = (hold_id or "").strip().upper()
    h = svc.holds.get(key)
    if h is None or svc.booking(h["booking"])["passenger_id"] != passenger_id:
        return {"status": "blocked", "reason": "hold_not_found", "hold_id": key,
                "next_step": "Say there is no such hold on this account. Never say whether it is someone else's."}
    view = _hold_view(svc, key)
    note = {"active": "The seat is held until the expiry. A hold is not a confirmed journey.",
            "expired": "The hold expired; the seat is no longer held.",
            "released": "The hold was released; the seat is no longer held."}[h["state"]]
    return {"status": h["state"], **view, "placed_in": h["placed_in"], "note": note}


# ---------------------------------------------------------------------------
# Options, selection, the hold (the guarded action), release and the queue
# ---------------------------------------------------------------------------


def find_recovery_options(svc: Disruption, passenger_id: Optional[str], booking_words: str) -> dict:
    ref, resolved = resolve_booking(passenger_id, booking_words)
    if ref is None:
        return resolved
    held = svc.active_hold(ref)
    if held:
        return {"status": "blocked", "reason": "hold_active", "booking_ref": ref, "active_hold": _hold_view(svc, held),
                "next_step": ("This booking already has a held option. If the passenger rejects it, call "
                              "release_hold with its hold_id first, then search again.")}
    b = svc.booking(ref)
    revision = svc.revision
    option_ids = svc.options_now(ref)
    svc.searches[ref] = {"revision": revision, "options": option_ids}
    incident = svc.data["incident"]
    if ref == incident["advance_after_first_search_of"] and not svc.advanced:
        # The incident moves on right after this read: the storm spreads and
        # an option on this list is cancelled before the passenger chooses.
        svc.revision = incident["advance_to"]
        svc.advanced = True
    result = {
        "status": "options", "booking_ref": ref, "cancelled_flight": b["cancelled_flight"],
        "incident_id": INCIDENT_ID, "incident_revision": revision, "read_at": f"{NOW} {CLOCK}",
        "options": [{"option_id": oid, "flight": svc.option(oid)["summary"],
                     "seats_shown": svc.option(oid)["seats_shown"]} for oid in option_ids],
        "seats_shown_is_not_a_hold": True,
        "note": ("Seat counts lag the inventory during the disruption. A seat is the passenger's only when "
                 "hold_recovery_option returns held, and even then it is a hold with an expiry, not a confirmed journey."),
    }
    if b["ticketed_by"] != "horizon":
        result["recovery_channel"] = ("none in this chat: the ticket was issued by a partner airline, so changes "
                                      "go through that airline")
    if svc.data["hold_service"].get(ref) == "unverified":
        result["hold_service"] = "unverified: holds on this route cannot be confirmed right now"
    return result


def select_option(svc: Disruption, passenger_id: Optional[str], option_id: str) -> dict:
    oid = (option_id or "").strip().upper()
    o = svc.option(oid)
    if o is None or svc.booking(o["booking"])["passenger_id"] != passenger_id:
        return {"status": "blocked", "reason": "unknown_option", "option_id": oid,
                "next_step": "Use an option_id from find_recovery_options."}
    search = svc.searches.get(o["booking"])
    if not search or oid not in search["options"]:
        return {"status": "blocked", "reason": "option_not_listed", "option_id": oid,
                "next_step": "Call find_recovery_options for this booking and let the passenger choose from that list."}
    return {"status": "selected", "option_id": oid, "booking_ref": o["booking"], "flight": o["summary"],
            "incident_revision": search["revision"]}


def selection_memory(result: dict) -> dict[str, str]:
    """Skill memory written by select_option; the confirmation question reads it."""
    if result.get("status") != "selected":
        return {"selected_option_id": "", "selected_option_summary": "", "selected_booking_ref": ""}
    return {"selected_option_id": result["option_id"], "selected_booking_ref": result["booking_ref"],
            "selected_option_summary": f"{result['flight']} (booking {result['booking_ref']})"}


def hold_recovery_option(svc: Disruption, passenger_id: Optional[str], selected_option_id: Optional[str],
                         option_id: str, conversation_id: str) -> dict:
    oid = (option_id or "").strip().upper()
    if not selected_option_id or oid != selected_option_id.upper():
        return {"status": "blocked", "reason": "option_not_selected", "option_id": oid, "effects": 0,
                "next_step": "Call select_option with the passenger's choice, then hold that option."}
    o = svc.option(oid)
    if o is None or svc.booking(o["booking"])["passenger_id"] != passenger_id:
        return {"status": "blocked", "reason": "unknown_option", "option_id": oid, "effects": 0}
    ref = o["booking"]
    held = svc.active_hold(ref)
    if held:
        return {"status": "blocked", "reason": "hold_active", "option_id": oid, "booking_ref": ref, "effects": 0,
                "active_hold": _hold_view(svc, held),
                "next_step": "One hold per booking. If the passenger rejects the held option, release_hold it first."}
    search = svc.searches.get(ref)
    if not search or oid not in search["options"]:
        return {"status": "blocked", "reason": "option_not_listed", "option_id": oid, "booking_ref": ref, "effects": 0,
                "next_step": "Call find_recovery_options again and let the passenger choose from the new list."}

    facts: dict[str, Any] = {"incident_revision_current": search["revision"] == svc.revision}
    provisional = False
    hold_service = svc.data["hold_service"].get(ref, "ok")
    if facts["incident_revision_current"]:
        if hold_service != "ok":
            facts["capacity_reserved"] = False
        elif svc.inventory[oid] > 0:
            svc.inventory[oid] -= 1
            provisional = True
            facts["capacity_reserved"] = True
        else:
            facts["capacity_reserved"] = False
    facts["recovery_channel_available"] = svc.booking(ref)["ticketed_by"] == "horizon"
    reason = evaluate(facts)
    base = {"option_id": oid, "booking_ref": ref, "flight": o["summary"], "facts": facts,
            "incident_revision": svc.revision, "journey_confirmed": False}
    if reason:
        if provisional:
            svc.inventory[oid] += 1  # the provisional hold is released in the same call
        result = {"status": "blocked", "reason": reason, **base, "effects": 0, "seat_held": False}
        if reason == "stale_incident_state":
            svc.searches.pop(ref, None)
            result["list_revision"] = search["revision"]
            result["next_step"] = ("The incident changed after this list was read; the list is void. Call "
                                   "find_recovery_options again and let the passenger choose from the new list.")
        elif reason == "capacity_not_reserved":
            if hold_service != "ok":
                result["hold_service"] = "unverified"
                result["next_step"] = ("Holds on this route cannot be confirmed right now. Do not promise a seat. "
                                       "Offer join_recovery_queue for an honest queued status.")
            else:
                result["seats_now"] = 0
                result["next_step"] = ("The seat count shown was out of date; nothing is held. Offer another option "
                                       "from the list or join_recovery_queue.")
        else:
            result["next_step"] = ("This ticket was issued by a partner airline; this chat cannot hold or change it. "
                                   "Give the incident status and say changes go through the issuing airline.")
        return result
    svc.hold_count += 1
    hold_id = "HT-HLD-" + digest({"c": conversation_id, "o": oid, "n": svc.hold_count})[:6].upper()
    expires = _hhmm(_minutes(NOW) + svc.data["hold_minutes"])
    svc.holds[hold_id] = {"booking": ref, "option": oid, "expires": expires, "state": "active", "placed_in": "this chat"}
    return {"status": "held", "reason": "verified_fixture_receipt", **base, "hold_id": hold_id,
            "expires": f"{expires} {CLOCK}, 30 Sep", "effects": 1, "seat_held": True,
            "next_step": ("Give the hold id and expiry. It is a hold, not a confirmed journey: to keep it the "
                          "passenger accepts it in Manage booking before it expires.")}


def release_hold(svc: Disruption, passenger_id: Optional[str], hold_id: str) -> dict:
    key = (hold_id or "").strip().upper()
    h = svc.holds.get(key)
    if h is None or svc.booking(h["booking"])["passenger_id"] != passenger_id:
        return {"status": "blocked", "reason": "hold_not_found", "hold_id": key}
    if h["state"] == "released":
        return {"status": "released", **_hold_view(svc, key), "replay": True}
    if h["state"] == "expired":
        return {"status": "expired", **_hold_view(svc, key),
                "note": "The hold had already expired; nothing to release."}
    h["state"] = "released"
    svc.inventory[h["option"]] += 1
    return {"status": "released", **_hold_view(svc, key), "replay": False,
            "next_step": "The seat is no longer held. Search again if the passenger wants a replacement."}


def join_recovery_queue(svc: Disruption, passenger_id: Optional[str], booking_words: str,
                        conversation_id: str) -> dict:
    ref, resolved = resolve_booking(passenger_id, booking_words)
    if ref is None:
        return resolved
    b = svc.booking(ref)
    if b["ticketed_by"] != "horizon":
        return {"status": "blocked", "reason": "no_recovery_channel", "booking_ref": ref,
                "next_step": "The ticket was issued by a partner airline; changes go through that airline."}
    held = svc.active_hold(ref)
    if held:
        return {"status": "blocked", "reason": "hold_active", "booking_ref": ref, "active_hold": _hold_view(svc, held),
                "next_step": "This booking already has a held option. Release it first if the passenger rejects it."}
    if ref in svc.queue:
        return {**svc.queue[ref], "replay": True}
    entry = {"status": "queued", "booking_ref": ref, "cancelled_flight": b["cancelled_flight"],
             "queue_reference": "HT-Q-" + digest({"c": conversation_id, "b": ref})[:6].upper(),
             "position": b["queue_base_position"], "seat_held": False, "journey_confirmed": False,
             "note": ("A queued status is not a seat. Horizon offers a held option when capacity is confirmed; "
                      "the position can move."), "replay": False}
    svc.queue[ref] = entry
    return entry


# ---------------------------------------------------------------------------
# What the passenger is told: tool receipts and the promise patterns
# ---------------------------------------------------------------------------


def customer_receipt(tool: str, result: dict) -> Optional[str]:
    """The message a tool sends the passenger for an outcome they must see, or None."""
    status, reason = result.get("status"), result.get("reason")
    if tool == "hold_recovery_option" and status == "held":
        return (f"Seat held: {result['flight']}, hold {result['hold_id']}, until {result['expires']}. "
                "This is a hold, not a confirmed journey. To keep it, accept it in Manage booking before it expires.")
    if tool == "hold_recovery_option" and status == "blocked" and reason == "capacity_not_reserved":
        if result.get("hold_service") == "unverified":
            return (f"No seat held on {result['flight']}: holds on this route can't be confirmed right now, "
                    "so I can't promise a seat. The recovery queue is still open.")
        return (f"No seat held on {result['flight']}: the seat count shown was out of date and the inventory has "
                "no seat to hold.")
    if tool == "hold_recovery_option" and status == "blocked" and reason == "stale_incident_state":
        return ("No seat held: the disruption plan changed after these options were listed, so the list is out "
                "of date. I need to look again.")
    if tool == "hold_recovery_option" and status == "blocked" and reason == "no_recovery_channel":
        return ("No seat held: this ticket was issued by a partner airline, so it can't be held or changed in "
                "this chat. Changes go through the airline that issued it.")
    if tool == "join_recovery_queue" and status == "queued":
        return (f"You're in the recovery queue for booking {result['booking_ref']}: reference "
                f"{result['queue_reference']}, position {result['position']}. This is not a seat or a confirmed "
                "journey; Horizon will offer a held option when capacity is confirmed.")
    if tool == "release_hold" and status == "released" and not result.get("replay"):
        return f"Hold {result['hold_id']} on {result['option']} is released. That seat is no longer held for you."
    return None


# A sentence that commits a journey. The chat never commits one, so any such
# sentence is an unbacked promise.
COMMITMENT_PATTERN = (
    r"\b(?:you(?:'re|\s+are|'ve\s+been|\s+have\s+been)\s+(?:now\s+)?"
    r"(?:all\s+set|(?:re)?booked|confirmed|ticketed|re-?accommodated|rebooked)\s+(?:on|onto|for|in)\b"
    r"|(?:i|we)(?:'ve|\s+have)\s+(?:now\s+|successfully\s+)?(?:re)?booked\s+you"
    r"|(?:your|the)\s+(?:new\s+)?(?:seat|flight|booking|journey|rebooking|itinerary|place)\s+(?:is|has\s+been)\s+"
    r"(?:now\s+)?(?:confirmed|booked|secured|guaranteed|ticketed|locked\s+in)"
    r"|guarantee(?:d)?\s+(?:you\s+)?(?:a\s+)?(?:seat|place|spot)"
    r"|(?:seat|place|spot)\s+is\s+guaranteed"
    r"|you(?:'ll|\s+will)\s+(?:definitely\s+|certainly\s+)?(?:get|have)\s+a\s+seat"
    r"|you\s+(?:now\s+)?have\s+a\s+(?:confirmed\s+)?seat\s+on"
    r"|(?:the\s+)?seat(?:'s|\s+is)\s+yours)"
)
# A sentence that says a seat is held. Backed only while a hold the tools
# placed or found is active in this conversation.
HOLD_CLAIM_PATTERN = (
    r"\b(?:(?:i|we)(?:'ve|\s+have)\s+(?:now\s+|successfully\s+)?(?:held|reserved|secured|placed\s+a\s+hold)"
    r"|(?:seat|option|flight|it)\s+(?:is|has\s+been)\s+(?:now\s+)?(?:held|reserved|secured|on\s+hold)"
    r"|you\s+(?:now\s+)?have\s+(?:a\s+)?(?:seat\s+)?(?:held|hold|reserved))"
)
PROMISE_HEDGE_PATTERN = (
    r"\b(?:not|no|never|cannot|can't|won't|isn't|wasn't|hasn't|haven't|until|unless|if|whether|once|when|before|"
    r"yet|only|would|may|might)\b|n't\b"
)
_COMMIT = re.compile(COMMITMENT_PATTERN, re.IGNORECASE)
_HOLD = re.compile(HOLD_CLAIM_PATTERN, re.IGNORECASE)
_HEDGE = re.compile(PROMISE_HEDGE_PATTERN, re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def promise_claims(text: str) -> list[tuple[str, str]]:
    """(kind, sentence) for each sentence that commits a journey or says a seat is held, unhedged."""
    hits = []
    for sentence in _SENTENCE.split(text or ""):
        for kind, pattern in (("commitment", _COMMIT), ("hold", _HOLD)):
            m = pattern.search(sentence)
            if m and not _HEDGE.search(sentence[: m.start()]):
                hits.append((kind, sentence.strip()))
                break
    return hits
