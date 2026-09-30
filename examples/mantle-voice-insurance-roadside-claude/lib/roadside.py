"""HarborCover roadside dispatch and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the three rules of the casebook contract for
``insurance-roadside`` (vendored as ``lib/fixtures/case-contract.json``)
inside ``request_dispatch`` and ``request_next_provider``, the only functions
that send a job to a roadside provider:

- ``incident_location_confirmed`` (request): the dispatch goes to the place
  the driver confirmed as where the vehicle is now. The draft's location is
  resolved from the driver's words, never from the policy, and every change
  to the draft makes a new version. The dispatch tool checks that the pending
  draft in memory is the current version, and that the latest confirmation
  question the engine sent carried this draft's place and service and was
  answered. The registered address is used only when the driver says the
  vehicle is there, and is then confirmed like any other place.
- ``service_suitability_checked`` (request): the provider covers the area of
  the confirmed place, offers the service, and for a tow has the equipment the
  vehicle needs (a flatbed for an all-wheel-drive electric car, a heavy-duty
  truck for a heavy van). Computed from the fixture's vehicle and provider
  records. A provider the caller names is checked the same way.
- ``provider_acceptance_known`` (receipt): the job is ``succeeded`` only when
  the provider accepted it. Until then, or after a decline, the result is
  ``pending`` with the assistance reference kept, and an arrival estimate is
  given only when the provider gave one, labelled as theirs.

Facts are computed here from the service's own records and the
conversation's events. The model supplies a policy number, a surname, a
vehicle reference, a service word, the driver's description of the place, a
provider name the caller asked for, and references copied from tool results.
It never supplies a fact, a place, a provider's answer or an arrival time. A
fact that is not exactly ``True`` fails its rule, as in the lab's
``evaluate``.

The organisation guard runs at import and is an allowlist: the fixture's
organisation must be the contract's own fictional insurer, marked fictional,
and every roadside provider must be on the fixture's declared list of
fictional providers and marked fictional.

State lives in an in-process service with one copy of the fixture per
conversation, so every scripted call starts from the same records.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "harborcover_roadside.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (MAX_MEMORY_VALUE_LENGTH, 3.21.0.dev5).
# Every value a tool writes to memory must fit; a test checks every fixture.
MEMORY_VALUE_LIMIT = 100

# The engine's confirmation question for request_dispatch
# (skills/roadside_dispatch/responses.yml). Mantle stamps the response name on
# the BotUttered event under this metadata key.
CONFIRM_UTTER = "utter_confirm_location"
UTTER_ACTION_KEY = "utter_action"

# The tools send the caller each dispatch outcome themselves through
# ToolContext.send (the reference, the provider's answer, a refusal or the
# desk reference), so it is spoken whatever the model does next. The
# `receipt-in-result-only` variant sets this to False.
TOOL_SENDS_RECEIPT = True


class FictionalOrganisationError(RuntimeError):
    """The fixture does not describe the casebook's fictional organisation."""


def assert_fictional(data: dict, contract: dict) -> None:
    """Refuse fixture data that names anyone but the casebook's fictional organisations.

    An allowlist, not a list of real names. The insurer must be the contract's
    organisation marked "(fictional ...)"; every provider must be on the
    fixture's own `fictional_providers` list and carry `fictional: true`; the
    note must say the data is fictional. Real institution names are also
    caught repository-wide by scripts/lint_repo.py.
    """
    organisation = str(data.get("organisation") or "")
    name, _, rest = organisation.partition(" (")
    if name != contract.get("organisation"):
        raise FictionalOrganisationError(
            f"organisation {name!r} is not the casebook contract's {contract.get('organisation')!r}")
    if not rest.lower().startswith("fictional"):
        raise FictionalOrganisationError(f"organisation must be marked '(fictional ...)': {organisation!r}")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")
    if data.get("case_slug") != contract.get("slug"):
        raise FictionalOrganisationError("the fixture is for a different casebook case")
    allowed = set(data.get("fictional_providers") or [])
    for ref, provider in (data.get("providers") or {}).items():
        if provider.get("name") not in allowed:
            raise FictionalOrganisationError(f"provider {ref} {provider.get('name')!r} is not on the fictional list")
        if provider.get("fictional") is not True:
            raise FictionalOrganisationError(f"provider {ref} must be marked fictional")


# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA, _CONTRACT)

ORGANISATION = _DATA["organisation"].split(" (")[0]
SERVICES = tuple(_DATA["services"])
MEMORY_KEYS = ("policy_number", "pending_draft_ref", "pending_vehicle_label", "pending_location_label",
               "pending_service_label")

_NUMBER_WORDS = {
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_DIGIT_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
# The driver saying the vehicle is at the policy's address. "On my way home" is not it.
_HOME_RE = re.compile(
    r"\b((at|outside|in front of) (my )?(home|house|place)|my (driveway|garage|address)|"
    r"address on (my|the) (policy|file|account)|registered address|policy address|"
    r"(the )?address (you have|on file))\b", re.IGNORECASE)
_SERVICE_WORDS = {
    "tow": ("tow", "towing", "won't start", "wont start", "broke down", "broken down", "dead"),
    "jump_start": ("jump", "battery"),
    "flat_tyre": ("flat", "tire", "tyre", "puncture"),
    "lockout": ("locked", "lockout", "keys"),
    "fuel": ("fuel", "gas", "petrol", "empty"),
}


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------


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


def reference(prefix: str, *parts: str) -> str:
    """A six-digit fixture reference, speakable digit by digit: HC-RSA-482173."""
    number = int(hashlib.sha256("|".join(parts).encode()).hexdigest(), 16) % 900000 + 100000
    return f"{prefix}-{number}"


def spoken(ref: str) -> str:
    """'HC-RSA-482173' -> 'four eight two, one seven three': how a reference is read out."""
    digits = re.sub(r"\D", "", ref)
    words = [_DIGIT_WORDS[int(d)] for d in digits]
    return " ".join(words[:3]) + ", " + " ".join(words[3:]) if len(words) == 6 else " ".join(words)


def words_to_digits(text: str) -> str:
    """'exit fourteen', 'mile marker thirty seven' -> 'exit 14', 'mile marker 37'. Other words kept."""
    text = re.sub(r"(?<=\d),(?=\d{3})", "", str(text or "").lower().replace("-", " "))
    tokens = re.findall(r"[a-z]+|\d+|[^\sa-z\d]", text)
    out: list[str] = []
    pending: Optional[int] = None
    for tok in tokens:
        value = _NUMBER_WORDS.get(tok)
        if value is not None and tok != "oh":
            if pending is not None and pending >= 20 and pending % 10 == 0 and value < 10:
                pending += value
            elif pending is not None:
                out.append(str(pending))
                pending = value
            else:
                pending = value
            continue
        if pending is not None:
            out.append(str(pending))
            pending = None
        out.append(tok)
    if pending is not None:
        out.append(str(pending))
    return " ".join(out)


def policy_digits(value: Any) -> str:
    """The digits of a policy number however it was said: 'HC-AU-440218', 'four four oh two one eight'."""
    out = []
    for tok in re.findall(r"[a-z]+|\d", str(value or "").lower()):
        if tok.isdigit():
            out.append(tok)
        elif tok == "oh":
            out.append("0")
        elif tok in _DIGIT_WORDS:
            out.append(str(_DIGIT_WORDS.index(tok)))
    return "".join(out)


def normalise_surname(value: Any) -> str:
    return re.sub(r"[^a-z]", "", str(value or "").lower())


def normalise_service(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if text in SERVICES:
        return text
    if text in ("flat_tire", "tire", "tyre", "flat"):
        return "flat_tyre"
    words = str(value or "").lower()
    found = {s for s, keys in _SERVICE_WORDS.items() if any(k in words for k in keys)}
    return found.pop() if len(found) == 1 else None


def distance(a: Iterable[float], b: Iterable[float]) -> float:
    (ax, ay), (bx, by) = a, b
    return math.hypot(ax - bx, ay - by)


# ----------------------------------------------------------------------------
# The conversation, as the tools see it
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Conversation:
    """What the tools read from tracker events: the latest confirmation question and whether it was answered."""

    confirmation_question: Optional[str] = None
    confirmation_answered: bool = False


def conversation_from_events(events: Iterable[Any]) -> Conversation:
    """Read events by class name (UserUttered, BotUttered), so tests can pass stand-ins."""
    question, answered = None, False
    for event in events or ():
        kind = type(event).__name__
        if kind == "UserUttered":
            text = getattr(event, "text", None) or ""
            if text.startswith("/"):
                continue  # /session_start and other intents are not the caller's words
            if question is not None:
                answered = True
        elif kind == "BotUttered":
            metadata = getattr(event, "metadata", None) or {}
            if metadata.get(UTTER_ACTION_KEY) == CONFIRM_UTTER:
                question = getattr(event, "text", None) or ""
                answered = False
    return Conversation(confirmation_question=question, confirmation_answered=answered)



# ----------------------------------------------------------------------------
# The service
# ----------------------------------------------------------------------------


@dataclass
class Draft:
    draft_id: str
    version: int
    policy_number: str
    vehicle_ref: str
    service: str
    place_ref: str
    location_source: str
    caller_words: str
    preferred_provider_ref: Optional[str] = None

    @property
    def tag(self) -> str:
        return f"{self.draft_id} v{self.version}"


class RoadsideService:
    """HarborCover's roadside desk for one conversation (fixture copy)."""

    def __init__(self, conversation_id: str = "offline", data: Optional[dict] = None) -> None:
        data = data or load_data()
        self.conversation_id = conversation_id
        self.policies: dict[str, dict] = data["policies"]
        self.places: dict[str, dict] = data["places"]
        self.providers: dict[str, dict] = data["providers"]
        self.services: dict[str, dict] = data["services"]
        self.tow_equipment: dict[str, list] = data["tow_equipment"]
        self.drafts: dict[str, Draft] = {}
        self.incidents: dict[str, dict] = {}
        self.desk_tickets: dict[str, dict] = {}
        self.dispatches: list[dict] = []  # every job sent to a provider

    # -- lookups -----------------------------------------------------------

    def policy_by_digits(self, digits: str) -> Optional[str]:
        return next((p for p in self.policies if re.sub(r"\D", "", p) == digits), None)

    def vehicle(self, policy_number: str, vehicle_ref: str) -> Optional[dict]:
        return self.policies.get(policy_number, {}).get("vehicles", {}).get(vehicle_ref)

    def resolve_place(self, words: str, policy_number: str) -> tuple[list[str], str]:
        """Candidate place refs for the driver's words, and how they were found.

        A named place (an exit, a mile marker, a business, a street number and
        street) wins. The policy's registered address is used only when the
        driver says the vehicle is there ("in my driveway", "the address on my
        policy"), and it is then read back and confirmed like any other place.
        """
        text = words_to_digits(words)
        registered = self.policies[policy_number]["registered_address"]
        found: list[str] = []
        for ref, place in self.places.items():
            if ref.startswith("HOME-") and ref != registered:
                continue  # another policyholder's home is never a match
            match = place.get("match") or {}
            hit = False
            if "exit" in match:
                hit = bool(re.search(rf"\bexit (number )?{match['exit']}\b", text))
            elif "mile_marker" in match:
                hit = bool(re.search(rf"\b(mile marker|marker|mile|mm) {match['mile_marker']}\b", text))
            if match.get("words") and any(re.search(rf"\b{w}\b", text) for w in match["words"]):
                hit = True
            if place.get("number") and re.search(rf"\b{place['number']} {place['street']}\b", text):
                hit = True
            if hit:
                found.append(ref)
        if not found and _HOME_RE.search(str(words or "")):
            return [registered], "policy_address_named_by_caller"
        source = "policy_address_named_by_caller" if found == [registered] else "caller_described"
        return found, source

    def suitability(self, provider_ref: str, place_ref: str, vehicle: dict, service: str) -> dict:
        """Whether one provider can do this job at this place for this vehicle, and why not in plain words."""
        provider = self.providers[provider_ref]
        place = self.places[place_ref]
        covers = place["area"] in provider["areas"]
        offers = service in provider["services"]
        needed = self.tow_equipment[vehicle["tow_requirement"]] if service == "tow" else []
        equipped = service != "tow" or any(e in provider["equipment"] for e in needed)
        why = []
        if not equipped:
            kind = " or ".join(n.replace("_", "-") for n in needed)
            why.append(f"your car needs a {kind} truck and they don't have one")
        if not covers:
            why.append("they don't cover where you are")
        if not offers:
            why.append(f"they don't do {self.services[service]['label']}")
        return {"provider": provider["name"], "suitable": covers and offers and equipped, "covers_area": covers,
                "offers_service": offers, "has_equipment": equipped,
                "why_not": " and ".join(why) or None}

    def suitable_providers(self, place_ref: str, vehicle: dict, service: str,
                           exclude: Iterable[str] = ()) -> list[str]:
        xy = self.places[place_ref]["xy"]
        skip = set(exclude)
        refs = [p for p in self.providers
                if p not in skip and self.suitability(p, place_ref, vehicle, service)["suitable"]]
        return sorted(refs, key=lambda p: distance(self.providers[p]["xy"], xy))

    def provider_by_name(self, name: str) -> Optional[str]:
        want = re.sub(r"[^a-z]", "", str(name or "").lower().replace("&", "and"))
        if len(want) < 4:
            return None
        hits = [ref for ref, p in self.providers.items()
                if want in re.sub(r"[^a-z]", "", p["name"].lower())
                or re.sub(r"[^a-z]", "", p["name"].lower().split(" ")[0]) in want]
        return hits[0] if len(hits) == 1 else None

    def labels(self, draft: Draft) -> dict:
        vehicle = self.vehicle(draft.policy_number, draft.vehicle_ref)
        return {"vehicle": vehicle["label"], "location": self.places[draft.place_ref]["label"],
                "service": self.services[draft.service]["label"]}

    def planned_provider(self, draft: Draft) -> Optional[str]:
        """The provider a dispatch of this draft goes to: the caller's choice if it suits, else the nearest that does."""
        vehicle = self.vehicle(draft.policy_number, draft.vehicle_ref)
        if draft.preferred_provider_ref and self.suitability(
                draft.preferred_provider_ref, draft.place_ref, vehicle, draft.service)["suitable"]:
            return draft.preferred_provider_ref
        candidates = self.suitable_providers(draft.place_ref, vehicle, draft.service)
        return candidates[0] if candidates else None


_SERVICES: dict[str, RoadsideService] = {}


def service_for(conversation_id: str) -> RoadsideService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = RoadsideService(conversation_id)
    return _SERVICES[conversation_id]


def memory_values(service: RoadsideService, draft: Optional[Draft]) -> dict:
    """What the tools write to skill memory for the engine's question. Empty strings clear it."""
    if draft is None:
        return {k: "" for k in MEMORY_KEYS if k != "policy_number"}
    labels = service.labels(draft)
    return {"pending_draft_ref": draft.tag, "pending_vehicle_label": labels["vehicle"],
            "pending_location_label": labels["location"], "pending_service_label": labels["service"]}


NO_INVENTED_TIME = ("Never give an arrival time the provider did not give, and never say help is on the way "
                    "before a provider accepted.")


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------


def find_policy(service: RoadsideService, policy_number: str, last_name: str) -> dict:
    """Match the caller to a policy by its six digits and the surname on it."""
    digits = policy_digits(policy_number)
    policy_ref = service.policy_by_digits(digits[-6:]) if len(digits) >= 6 else None
    policy = service.policies.get(policy_ref or "")
    if policy is None or normalise_surname(policy["last_name"]) != normalise_surname(last_name):
        return {"status": "not_found",
                "next_step": "Say you could not match that policy number and last name, and ask the caller to "
                             "say the six digits of the policy number again, one at a time. Do not say whether "
                             "the number exists."}
    return {
        "status": "found",
        "policy_number": policy_ref,
        "policyholder_first_name": policy["first_name"],
        "vehicles": [{"vehicle_ref": ref, "vehicle": v["label"]} for ref, v in policy["vehicles"].items()],
        "registered_address_is_not_the_incident_location": True,
        "next_step": "Ask only for what the caller has not said yet: which vehicle if there is more than one, "
                     "what help it needs, and where the vehicle is right now. The address on the policy is "
                     "where the car is kept, not where it is.",
    }


def _preferred(service: RoadsideService, draft: Draft, preferred_provider: Optional[str]) -> dict:
    """Record the provider the caller asked for, only if it suits this job. Returns what happened."""
    if not preferred_provider:
        return {}
    ref = service.provider_by_name(preferred_provider)
    if ref is None:
        return {"preferred_provider": {"asked_for": " ".join(str(preferred_provider).split())[:60],
                                       "known": False, "used": False,
                                       "why_not": "HarborCover has no roadside provider by that name"}}
    vehicle = service.vehicle(draft.policy_number, draft.vehicle_ref)
    check = service.suitability(ref, draft.place_ref, vehicle, draft.service)
    draft.preferred_provider_ref = ref if check["suitable"] else None
    return {"preferred_provider": {"asked_for": service.providers[ref]["name"], "known": True,
                                   "used": check["suitable"], "why_not": check["why_not"]}}


def start_dispatch_draft(service: RoadsideService, policy_number: Optional[str], vehicle_ref: str,
                         service_needed: str, location: str, preferred_provider: Optional[str] = None
                         ) -> tuple[dict, Optional[Draft]]:
    """Open a dispatch draft for the place the driver described. A draft sends nothing."""
    if not policy_number or policy_number not in service.policies:
        return {"status": "blocked", "reason": "no_policy",
                "next_step": "Call find_policy with the caller's policy number and last name first."}, None
    vehicle_ref = str(vehicle_ref or "").strip().upper()
    if service.vehicle(policy_number, vehicle_ref) is None:
        return {"status": "unknown_vehicle",
                "vehicles": [{"vehicle_ref": r, "vehicle": v["label"]}
                             for r, v in service.policies[policy_number]["vehicles"].items()],
                "next_step": "Use a vehicle_ref from this list; ask the caller which vehicle if unsure."}, None
    wanted = normalise_service(service_needed)
    if wanted is None:
        return {"status": "unsupported_service", "supported_services": list(SERVICES),
                "next_step": "Ask whether they need a tow, a jump start, a flat tire change, a lockout or fuel."}, None
    places, source = service.resolve_place(location, policy_number)
    if len(places) != 1:
        return _location_problem(service, places, location), None
    draft_id = reference("HC-RD", service.conversation_id, str(len(service.drafts)))
    draft = Draft(draft_id=draft_id, version=1, policy_number=policy_number, vehicle_ref=vehicle_ref,
                  service=wanted, place_ref=places[0], location_source=source,
                  caller_words=" ".join(str(location or "").split())[:100])
    service.drafts[draft_id] = draft
    extra = _preferred(service, draft, preferred_provider)
    return {**_draft_result(service, draft, "drafted"), **extra}, draft


def _location_problem(service: RoadsideService, places: list[str], location: Any) -> dict:
    return {
        "status": "location_not_found" if not places else "location_ambiguous",
        "heard": " ".join(str(location or "").split())[:100],
        **({"candidates": [service.places[p]["label"] for p in places]} if places else {}),
        "next_step": "Ask where the vehicle is right now: the road and direction with the nearest exit or mile "
                     "marker, or the street number and street, or a business it is parked at. Do not use the "
                     "address on the policy unless the caller says the vehicle is there.",
    }


def _draft_result(service: RoadsideService, draft: Draft, status: str) -> dict:
    labels = service.labels(draft)
    vehicle = service.vehicle(draft.policy_number, draft.vehicle_ref)
    planned = service.planned_provider(draft)
    result = {
        "status": status,
        "draft_id": draft.draft_id,
        "version": draft.version,
        "vehicle": labels["vehicle"],
        "tow_requirement": vehicle["why"] if draft.service == "tow" else None,
        "service": labels["service"],
        "location": labels["location"],
        "location_ref": draft.place_ref,
        "location_source": draft.location_source,
        "provider_if_sent_now": service.providers[planned]["name"] if planned else None,
        "dispatched": False,
    }
    if planned is None:
        result["no_suitable_provider_nearby"] = True
        result["next_step"] = ("No HarborCover provider covers this place for this job. Call route_dispatch_desk "
                               "with this draft_id. Nothing has been sent.")
    else:
        result["next_step"] = ("Call request_dispatch with this draft_id straight away. Do not ask for "
                               "confirmation yourself: the engine reads the place back and asks the caller to "
                               "confirm where the vehicle is now.")
    return result


def update_dispatch_draft(service: RoadsideService, draft_id: str, location: Optional[str] = None,
                          service_needed: Optional[str] = None, vehicle_ref: Optional[str] = None,
                          preferred_provider: Optional[str] = None) -> tuple[dict, Optional[Draft]]:
    """Change a draft that has not been dispatched. Any change is a new version to confirm."""
    draft = service.drafts.get(str(draft_id or "").strip().upper())
    if draft is None:
        return {"status": "unknown_draft", "next_step": "Start a new draft with start_dispatch_draft."}, None
    if any(i["draft_id"] == draft.draft_id for i in service.incidents.values()):
        return {"status": "already_dispatched", "draft_id": draft.draft_id,
                "next_step": "This draft was already sent to a provider. Route to the dispatch desk to change "
                             "it."}, None
    if location:
        places, source = service.resolve_place(location, draft.policy_number)
        if len(places) != 1:
            return {**_location_problem(service, places, location), "draft_id": draft.draft_id,
                    "draft_unchanged": True}, None
        draft.place_ref, draft.location_source = places[0], source
        draft.caller_words = " ".join(str(location).split())[:100]
    if service_needed:
        wanted = normalise_service(service_needed)
        if wanted is None:
            return {"status": "unsupported_service", "supported_services": list(SERVICES),
                    "draft_id": draft.draft_id, "next_step": "Ask which service they need."}, None
        draft.service = wanted
    if vehicle_ref:
        if service.vehicle(draft.policy_number, str(vehicle_ref).strip().upper()) is None:
            return {"status": "unknown_vehicle", "draft_id": draft.draft_id,
                    "next_step": "Use a vehicle_ref from find_policy."}, None
        draft.vehicle_ref = str(vehicle_ref).strip().upper()
    draft.version += 1
    extra = _preferred(service, draft, preferred_provider)
    if not preferred_provider and draft.preferred_provider_ref:
        # The job changed: the caller's earlier choice stands only if it still suits.
        vehicle = service.vehicle(draft.policy_number, draft.vehicle_ref)
        if not service.suitability(draft.preferred_provider_ref, draft.place_ref, vehicle, draft.service)["suitable"]:
            draft.preferred_provider_ref = None
    return {**_draft_result(service, draft, "updated"), **extra}, draft


def _location_confirmed(service: RoadsideService, draft: Draft, memory: dict, conversation: Conversation) -> bool:
    labels = service.labels(draft)
    question = conversation.confirmation_question or ""
    return (
        (memory.get("pending_draft_ref") or "") == draft.tag
        and labels["location"] in question
        and labels["service"] in question
        and conversation.confirmation_answered
    )


def _send_to_provider(service: RoadsideService, incident: dict, provider_ref: str) -> dict:
    """The provider's answer to a job, from the fixture. The model has no way to change it."""
    answers = service.providers[provider_ref]["answers"]
    incident["provider_ref"] = provider_ref
    incident["tried"].append(provider_ref)
    service.dispatches.append({"assistance_ref": incident["assistance_ref"], "provider_ref": provider_ref,
                               "place_ref": incident["place_ref"],
                               "location_confirmed": incident["facts"]["incident_location_confirmed"]})
    kind = answers["kind"]
    if kind == "accept":
        incident.update(acceptance="accepted", eta_minutes=answers["eta_minutes"])
    elif kind == "accept_no_eta":
        incident.update(acceptance="accepted", eta_minutes=None)
    elif kind == "accept_on_first_check":
        incident.update(acceptance="awaiting_provider", eta_minutes=None, checks_to_accept=1)
    else:
        incident.update(acceptance="declined", eta_minutes=None, declined_why=answers.get("why"))
        incident["declined"].append(provider_ref)
    return incident


def _incident_result(service: RoadsideService, incident: dict, *, replay: bool = False) -> dict:
    provider = service.providers[incident["provider_ref"]]
    acceptance = incident["acceptance"]
    facts = dict(incident["facts"], provider_acceptance_known=acceptance == "accepted")
    receipt_reason = evaluate(facts, "receipt")
    status = "pending" if receipt_reason else "succeeded"
    ref = incident["assistance_ref"]
    eta = incident.get("eta_minutes")
    result = {
        "status": status,
        "reason": receipt_reason or "verified_fixture_receipt",
        "assistance_ref": ref,
        "assistance_ref_spoken": spoken(ref),
        "provider": provider["name"],
        "provider_acceptance": acceptance,
        "arrival_estimate": ({"minutes": eta, "source": f"{provider['name']}, when it accepted"}
                             if acceptance == "accepted" and eta is not None else None),
        "location": service.places[incident["place_ref"]]["label"],
        "location_ref": incident["place_ref"],
        "vehicle_ref": incident["vehicle_ref"],
        "service": service.services[incident["service"]]["label"],
        "facts": facts,
        "effects": 1,
        "replay": replay,
        "dispatched_to_unconfirmed_location": int(facts["incident_location_confirmed"] is not True),
    }
    said = "The caller has already heard this outcome and the reference. " if TOOL_SENDS_RECEIPT else ""
    if acceptance == "accepted":
        result["next_step"] = (said + "Tell the caller what is new, if anything. "
                               + ("Give only the provider's own estimate. " if eta is not None else
                                  "The provider gave no arrival estimate: do not give one. ") + NO_INVENTED_TIME)
    elif acceptance == "awaiting_provider":
        result["next_step"] = (said + "The request is logged but no provider has accepted it: nobody is on the "
                               "way yet. Offer to check again with check_dispatch. " + NO_INVENTED_TIME)
    else:
        result["declined_by"] = provider["name"]
        result["next_step"] = (said + "The provider declined. The assistance reference stays open. Call "
                               "request_next_provider with it now to find another suitable provider. "
                               + NO_INVENTED_TIME)
    return result


def request_dispatch(service: RoadsideService, draft_id: str, memory: dict, conversation: Conversation) -> dict:
    """The wrapper in front of a dispatch: a confirmed place and a suitable provider, or nothing is sent."""
    draft = service.drafts.get(str(draft_id or "").strip().upper())
    if draft is None:
        return {"status": "blocked", "reason": "unknown_draft", "effects": 0,
                "next_step": "Start a draft with start_dispatch_draft."}
    existing = next((i for i in service.incidents.values() if i["draft_id"] == draft.draft_id), None)
    if existing is not None:
        return _incident_result(service, existing, replay=True)
    vehicle = service.vehicle(draft.policy_number, draft.vehicle_ref)
    provider_ref = service.planned_provider(draft)
    check = (service.suitability(provider_ref, draft.place_ref, vehicle, draft.service) if provider_ref
             else {"provider": None, "suitable": False, "why_not": "no provider covers this place for this job"})
    facts = {
        "incident_location_confirmed": _location_confirmed(service, draft, memory, conversation),
        "service_suitability_checked": check["suitable"] is True,
    }
    reason = evaluate(facts, "request")
    labels = service.labels(draft)
    if reason:
        result = {"status": "blocked", "reason": reason, "draft_id": draft.draft_id, "effects": 0,
                  "facts": facts, "location": labels["location"], "service": labels["service"],
                  "dispatched": False, "blocked_attempt": 1}
        if reason == "wrong_incident_location":
            result["next_step"] = ("The caller has not confirmed this place for this version of the draft. Call "
                                   "request_dispatch again; the engine asks the caller where the vehicle is now. "
                                   "Nothing was sent.")
        else:
            result["no_suitable_provider_nearby"] = True
            result["why_not"] = check["why_not"]
            result["next_step"] = ("Nothing was sent. No suitable provider covers this place. Call "
                                   "route_dispatch_desk with the draft_id.")
        return result
    assistance_ref = reference("HC-RSA", service.conversation_id, draft.tag)
    incident = {"assistance_ref": assistance_ref, "draft_id": draft.draft_id, "draft_tag": draft.tag,
                "policy_number": draft.policy_number, "vehicle_ref": draft.vehicle_ref, "service": draft.service,
                "place_ref": draft.place_ref, "facts": facts, "tried": [], "declined": []}
    service.incidents[assistance_ref] = incident
    _send_to_provider(service, incident, provider_ref)
    return _incident_result(service, incident)


def request_next_provider(service: RoadsideService, assistance_ref: str) -> dict:
    """After a decline: same incident, same confirmed place, the next suitable provider."""
    incident = service.incidents.get(str(assistance_ref or "").strip().upper())
    if incident is None:
        return {"status": "unknown", "effects": 0, "next_step": "No such assistance reference."}
    if incident["acceptance"] != "declined":
        return _incident_result(service, incident, replay=True)
    vehicle = service.vehicle(incident["policy_number"], incident["vehicle_ref"])
    candidates = service.suitable_providers(incident["place_ref"], vehicle, incident["service"],
                                            exclude=incident["declined"])
    facts = {"incident_location_confirmed": incident["facts"]["incident_location_confirmed"],
             "service_suitability_checked": bool(candidates)}
    reason = evaluate(facts, "request")
    if reason:
        return {"status": "blocked", "reason": reason, "assistance_ref": incident["assistance_ref"],
                "assistance_ref_spoken": spoken(incident["assistance_ref"]), "effects": 0, "facts": facts,
                "no_suitable_provider_nearby": not candidates, "incident_kept": True, "blocked_attempt": 1,
                "next_step": "No other suitable provider covers this place. Call route_dispatch_desk with this "
                             "assistance_ref. Nobody is on the way."}
    incident["facts"] = facts
    _send_to_provider(service, incident, candidates[0])
    return _incident_result(service, incident)


def check_dispatch(service: RoadsideService, assistance_ref: str) -> dict:
    """Read the provider's answer again. The caller's word is never an acceptance."""
    incident = service.incidents.get(str(assistance_ref or "").strip().upper())
    if incident is None:
        return {"status": "unknown", "effects": 0, "next_step": "No such assistance reference."}
    if incident["acceptance"] == "awaiting_provider":
        incident["checks_to_accept"] -= 1
        if incident["checks_to_accept"] <= 0:
            answers = service.providers[incident["provider_ref"]]["answers"]
            incident.update(acceptance="accepted", eta_minutes=answers.get("eta_minutes"))
            return _incident_result(service, incident)
    return _incident_result(service, incident, replay=True)


def route_dispatch_desk(service: RoadsideService, reason: str, draft_id: Optional[str] = None,
                        assistance_ref: Optional[str] = None) -> dict:
    """Hand the job to the dispatch desk. Any draft or incident is kept, and nothing is sent."""
    draft = str(draft_id or "").strip().upper() or None
    incident = str(assistance_ref or "").strip().upper() or None
    desk_ref = reference("HC-RDD", service.conversation_id, draft or "-", incident or "-",
                         str(len(service.desk_tickets)))
    service.desk_tickets[desk_ref] = {"draft_id": draft, "assistance_ref": incident,
                                      "reason": " ".join(str(reason or "").split())[:200]}
    said = "The caller has already heard the desk reference. " if TOOL_SENDS_RECEIPT else ""
    return {
        "status": "routed",
        "desk_ref": desk_ref,
        "desk_ref_spoken": spoken(desk_ref),
        "draft_id": draft if draft in service.drafts else None,
        "assistance_ref": incident if incident in service.incidents else None,
        "dispatched": False,
        "next_step": said + "A HarborCover dispatcher calls the caller back on this line. Nobody is on the way "
                     "yet. " + NO_INVENTED_TIME,
    }


# ----------------------------------------------------------------------------
# The message a tool speaks itself (TOOL_SENDS_RECEIPT)
# ----------------------------------------------------------------------------


def customer_receipt(tool: str, result: dict) -> Optional[str]:
    """The message a tool sends the caller for an outcome they must hear, or None.

    Receipts: an accepted job (reference, provider, and the provider's own
    estimate or none), a logged job no provider has accepted yet, a decline
    (the reference kept). Refusals: a provider the caller asked for that cannot
    do the job, no suitable provider nearby. Desk routes: the desk reference.
    """
    status = result.get("status")
    ref = result.get("assistance_ref_spoken")
    provider = result.get("provider")
    acceptance = result.get("provider_acceptance")
    if tool in ("request_dispatch", "request_next_provider", "check_dispatch") and ref \
            and status in ("succeeded", "pending") and not result.get("replay"):
        if acceptance == "accepted":
            eta = result.get("arrival_estimate")
            timing = (f"They estimate {eta['minutes']} minutes to reach you."
                      if eta else "They have not given an arrival time.")
            return f"Your roadside reference is {ref}. {provider} has accepted the job. {timing}"
        if acceptance == "awaiting_provider":
            return (f"Your request is logged under reference {ref}, but no provider has accepted it yet, "
                    "so nobody is on the way yet.")
        if acceptance == "declined":
            return (f"{provider} declined the job. Your request stays open under reference {ref}, and I'm "
                    "finding another provider. Nobody is on the way yet.")
    if tool in ("start_dispatch_draft", "update_dispatch_draft"):
        preferred = result.get("preferred_provider") or {}
        if preferred.get("known") and not preferred.get("used"):
            fallback = result.get("provider_if_sent_now")
            return (f"I can't send {preferred['asked_for']}: {preferred['why_not']}. "
                    + (f"The nearest provider that can do it is {fallback}." if fallback else "")).strip()
        if result.get("no_suitable_provider_nearby"):
            return "No HarborCover provider near you can do this job, so nothing has been sent."
    if tool in ("request_dispatch", "request_next_provider") and status == "blocked" \
            and result.get("reason") == "unsuitable_provider":
        return "No HarborCover provider near you can do this job, so nothing has been sent."
    if tool == "route_dispatch_desk" and status == "routed":
        return (f"I've passed this to the HarborCover dispatch desk, reference {result['desk_ref_spoken']}. "
                "A dispatcher will call you back on this line. Nobody is on the way yet.")
    return None
