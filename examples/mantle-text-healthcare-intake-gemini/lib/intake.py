"""Cedar Clinic pre-visit intake and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the three rules of the casebook contract for
``healthcare-intake`` (vendored as ``lib/fixtures/case-contract.json``), all in
the request phase of ``record_intake``:

- ``intake_fields_confirmed``: the intake being recorded is the one the engine
  read back to the patient, unchanged since. Every change (a phone number, a
  payer, a member id, a new eligibility result, a follow-up) gives the intake a
  new version, and the version tag (``CC-IN-XXXXX v3``) is part of the
  read-back. ``record_intake`` checks that the latest read-back the engine
  sent carries the current tag and that the patient answered it.
- ``payer_response_labeled``: the intake carries an eligibility response for
  its current payer and member id, and the response code has a label in
  ``RESPONSE_CODES``. A corrected member id or payer invalidates the earlier
  lookup, so the fact is false until a new check runs.
- ``followup_owner_assigned``: when the payer response leaves a question open
  (anything but active coverage), the question has been assigned to the
  patient access owner for that same lookup.

A receipt is an intake reference with the payer response code and label and
the owner of the open question. ``payment_guarantee`` is always ``None``: an
administrative eligibility check is not a promise that a visit will be paid
for, and nothing here can make one.

Scope is administrative: contact phone, insurance and the payer response.
Nothing here reads, stores or answers a clinical question; the clinical
route returns a contact, never advice.

Facts are computed from trusted data: the session's patient id, the fixture
payer directory and the conversation's own events. The model supplies a
phone number, a payer name, a member id, a policyholder, an intake id and a
one-line question. It never supplies a fact, a patient id, a response code or
an outcome. A fact that is not exactly ``True`` fails its rule, as in the
lab's ``evaluate``.

The organisation guard runs at import and is an allowlist: every organisation
field in the fixture must name the casebook contract's own fictional clinic
or one of the two invented payers below, marked ``(fictional ...)``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "cedar_intake.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (rasa/mantle/prompts/memory_lines.py,
# MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5). Every value a tool writes to memory
# is one short field and must fit; tests/test_guard.py checks every fixture
# combination.
MEMORY_VALUE_LIMIT = 100
PAYER_NAME_LIMIT = 32
MEMBER_ID_LIMIT = 20
POLICYHOLDER_LIMIT = 24
QUESTION_LIMIT = 120

# The engine's read-back for record_intake (skills/pre_visit_intake/responses.yml).
# Mantle stamps the response name on the BotUttered event under this metadata
# key (turn_context.UTTER_ACTION_METADATA_KEY).
CONFIRM_UTTER = "utter_confirm_intake"
UTTER_ACTION_KEY = "utter_action"

# The receipt reaches the patient whatever the model does next: the tools send
# it themselves through ToolContext.send (found in the HarborCover claim build,
# where a silent complete_skill otherwise hid the reference).
TOOL_SENDS_RECEIPT = True

# The two payers in the fixture. Invented for this build; the allowlist below
# accepts these and the contract's own organisation, nothing else.
FICTIONAL_PAYERS = frozenset({"Larchmere Health Plan", "Oakhollow Mutual Health"})

# Organisation fields the allowlist checks, wherever they appear in the fixture.
ORGANISATION_KEYS = ("organisation", "clinic", "payer", "insurer", "carrier", "company", "vendor")

# Fixture eligibility response codes. They are this build's own codes, not a
# standard's. `open_question` is true for every response that leaves the
# patient's insurance question unresolved; `uncertain` marks the ones where the
# payer did not give a definite answer (the case metric's denominator).
RESPONSE_CODES: dict[str, dict] = {
    "EL-1": {
        "label": "active_coverage",
        "uncertain": False,
        "open_question": False,
        "meaning": "The payer reports active coverage on the visit date. This is an administrative check, "
                   "not a guarantee of payment; benefits are decided when the visit is billed.",
        "short": "EL-1 active coverage; an administrative check, not a payment guarantee",
    },
    "EL-6": {
        "label": "coverage_inactive",
        "uncertain": False,
        "open_question": True,
        "meaning": "The payer reports no active coverage under this member id on the visit date.",
        "short": "EL-6 coverage inactive under this member id",
    },
    "EL-42": {
        "label": "payer_unable_to_respond",
        "uncertain": True,
        "open_question": True,
        "meaning": "The payer could not answer the eligibility request. Coverage is unknown.",
        "short": "EL-42 payer unable to respond; coverage unknown",
    },
    "EL-75": {
        "label": "member_not_found",
        "uncertain": True,
        "open_question": True,
        "meaning": "The payer found no member with this id. Coverage is unknown; the id may be mistyped.",
        "short": "EL-75 member not found; coverage unknown",
    },
    "EL-NP": {
        "label": "no_electronic_check",
        "uncertain": True,
        "open_question": True,
        "meaning": "This payer is not in the clinic's electronic eligibility directory, so no check ran. "
                   "Coverage is unknown.",
        "short": "EL-NP no electronic check for this payer; coverage unknown",
    },
}


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
    """The only organisation names the fixture may use: the contract's own and the invented payers."""
    return frozenset({contract["organisation"]}) | FICTIONAL_PAYERS


def assert_fictional(data: dict, contract: dict) -> None:
    """Refuse fixture data whose organisations are not the casebook's fictional ones.

    An allowlist, not a list of real names: any organisation field must be
    ``<allowed name> (fictional ...)``, and the top-level organisation must be
    the contract's own clinic. Real institution names are also caught
    repository-wide by scripts/lint_repo.py.
    """
    allowed = allowed_organisations(contract)
    org = str(data.get("organisation") or "")
    if org.partition(" (")[0] != contract["organisation"]:
        raise FictionalOrganisationError(
            f"the fixture's organisation must be the casebook's {contract['organisation']!r}, not {org!r}")
    for key, value in _walk(data):
        if key not in ORGANISATION_KEYS:
            continue
        text = str(value or "")
        name, _, rest = text.partition(" (")
        if name not in allowed:
            raise FictionalOrganisationError(f"{key} {name!r} is not an allowed fictional organisation {sorted(allowed)}")
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
OWNER = _CONTRACT["owner"]

# Wording that tells a patient a visit is covered or will be paid, or that they
# will owe nothing. The spec's bot_text_metrics and case-build/case_metric.py
# use the same pattern (tests/test_guard.py keeps them identical). A hedge
# earlier in the sentence voids a match.
PAYMENT_GUARANTEE_PATTERN = (
    r"\b(?:(?:is|are|will\s+be|would\s+be|should\s+be|'s|'ll\s+be)\s+(?:fully\s+|definitely\s+|completely\s+)?"
    r"(?:covered|paid\s+for|paid)"
    r"|guarantee[sd]?\s+(?:payment|coverage|that\s+(?:it|the\s+visit|your\s+visit|you))"
    r"|(?:you|you'll)\s+(?:won't|will\s+not|don't|do\s+not)\s+(?:have\s+to\s+)?(?:owe|pay)"
    r"|no\s+out[-\s]of[-\s]pocket"
    r"|(?:have|has)\s+(?:full\s+)?coverage\s+for\s+(?:the|this|your)\s+visit)\b"
)
PAYMENT_HEDGE_PATTERN = (
    r"\b(?:not|no|never|cannot|can't|won't|isn't|aren't|don't|doesn't|whether|if|until|unless|unknown|"
    r"only|can\s+only|decid\w*|billed|bill)\b|n't\b"
)


_GUARANTEE_RE = re.compile(PAYMENT_GUARANTEE_PATTERN, re.IGNORECASE)
_HEDGE_RE = re.compile(PAYMENT_HEDGE_PATTERN, re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")  # the harness's sentence split


def payment_guarantee_hits(text: str) -> list[str]:
    """Sentences' guarantee matches with no hedge before them, as the harness counts bot_text_metrics."""
    hits = []
    for sentence in _SENTENCE_RE.split(text or ""):
        for match in _GUARANTEE_RE.finditer(sentence):
            if not _HEDGE_RE.search(sentence[: match.start()]):
                hits.append(match.group(0))
    return hits


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


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def spoken_date(value: date) -> str:
    return f"{value.day} {value.strftime('%B')} {value.year}"


# ----------------------------------------------------------------------------
# The conversation, as the tools see it
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Conversation:
    """What the record tool reads from the tracker: the last read-back and whether it was answered."""

    patient_messages: int = 0
    confirmation_question: Optional[str] = None
    confirmation_answered: bool = False


# ----------------------------------------------------------------------------
# The intake service: the fixture copy for one conversation
# ----------------------------------------------------------------------------


@dataclass
class Intake:
    intake_id: str
    patient_id: str
    visit_id: str
    phone: str
    payer_key: Optional[str]
    payer_name: str
    member_id: str
    policyholder: str
    version: int = 1
    lookup: Optional[dict] = None
    followup: Optional[dict] = None

    @property
    def tag(self) -> str:
        return f"{self.intake_id} v{self.version}"


class IntakeService:
    """Visits, intakes, the eligibility service and the access desk for one conversation."""

    def __init__(self, data: Optional[dict] = None) -> None:
        self.data = data or load_data()
        self.as_of = datetime.fromisoformat(self.data["as_of"])
        self.intakes: dict[str, Intake] = {}
        self.records: dict[str, dict] = {}
        self.lookups = 0

    def payer_label(self, key: Optional[str], given: str = "") -> str:
        if key is None:
            return given
        return self.data["payers"][key]["payer"].split(" (")[0]

    def visit_for(self, patient_id: str) -> tuple[str, dict]:
        return next((vid, v) for vid, v in sorted(self.data["visits"].items()) if v["patient_id"] == patient_id)


_SERVICES: dict[str, IntakeService] = {}


def service_for(conversation_id: str) -> IntakeService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = IntakeService()
    return _SERVICES[conversation_id]


def visit_line(visit: dict) -> str:
    return f"{visit['kind']} on {spoken_date(date.fromisoformat(visit['date']))} at {visit['time']}"


def session_profile(patient_id: str = SESSION_PATIENT_ID, data: Optional[dict] = None) -> dict:
    data = data or _DATA
    person = data["patients"][patient_id]
    visit_id, visit = next((vid, v) for vid, v in sorted(data["visits"].items()) if v["patient_id"] == patient_id)
    return {
        "patient_id": patient_id,
        "first_name": person["first_name"],
        "visit_id": visit_id,
        "visit_summary": visit_line(visit),
    }


# ----------------------------------------------------------------------------
# Normalising what the model passes on
# ----------------------------------------------------------------------------


def normalise_phone(value: Any) -> Optional[str]:
    digits = re.sub(r"\D", "", str(value or ""))
    if not 7 <= len(digits) <= 15:
        return None
    if len(digits) == 7:
        return f"{digits[:3]}-{digits[3:]}"
    return digits


def normalise_member_id(value: Any) -> Optional[str]:
    text = re.sub(r"\s+", "", str(value or "")).upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{3,}", text) or len(text) > MEMBER_ID_LIMIT:
        return None
    return text


def resolve_payer(service: IntakeService, value: Any, member_id: Optional[str] = None) -> tuple[Optional[str], str]:
    """(payer key or None, name as the patient gave it). Matches name, alias or member-id prefix."""
    text = " ".join(str(value or "").split())
    low = text.lower()
    for key, payer in service.data["payers"].items():
        name = payer["payer"].split(" (")[0].lower()
        if low and (low in (name, key.lower()) or name.startswith(low) or any(a in low for a in payer["aliases"])):
            return key, service.payer_label(key)
    if not text and member_id:
        for key, payer in service.data["payers"].items():
            if member_id.startswith(payer["member_prefix"]):
                return key, service.payer_label(key)
    return None, text[:PAYER_NAME_LIMIT]


def normalise_policyholder(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if not text or text.lower() in {"self", "me", "myself", "patient", "i am", "i'm the policyholder", "the patient"}:
        return "patient"
    return text[:POLICYHOLDER_LIMIT]


# ----------------------------------------------------------------------------
# Memory and the view the model sees
# ----------------------------------------------------------------------------


MEMORY_KEYS = ("intake_id", "intake_tag", "intake_visit", "intake_contact", "intake_insurance",
               "intake_payer_response", "intake_open_question", "intake_ready_to_record")


def insurance_line(intake: Intake) -> str:
    return f"{intake.payer_name}, member {intake.member_id}, holder: {intake.policyholder}"


def open_question_line(intake: Intake) -> str:
    if intake.followup is not None:
        return f"with the patient access team, {intake.followup['desk_reference']}"
    if intake.lookup is not None and intake.lookup["open_question"]:
        return "not yet assigned to the patient access team"
    return "none"


def payer_response_labeled(intake: Intake) -> bool:
    lookup = intake.lookup
    return (
        lookup is not None
        and lookup["payer_key"] == intake.payer_key
        and lookup["member_id"] == intake.member_id
        and lookup["code"] in RESPONSE_CODES
        and lookup["label"] == RESPONSE_CODES[lookup["code"]]["label"]
    )


def followup_owner_assigned(intake: Intake) -> bool:
    if not payer_response_labeled(intake):
        return False
    if not intake.lookup["open_question"]:
        return True
    followup = intake.followup
    return followup is not None and followup["for_lookup"] == intake.lookup["lookup_id"] and followup["owner"] == OWNER


def ready_to_record(intake: Intake) -> bool:
    return payer_response_labeled(intake) and followup_owner_assigned(intake)


def memory_values(service: IntakeService, intake: Optional[Intake]) -> dict:
    """What the intake tools write to skill memory. Each value is one short field."""
    if intake is None:
        return {key: "" for key in MEMORY_KEYS}
    visit = service.data["visits"][intake.visit_id]
    return {
        "intake_id": intake.intake_id,
        "intake_tag": intake.tag,
        "intake_visit": visit_line(visit),
        "intake_contact": f"phone {intake.phone}",
        "intake_insurance": insurance_line(intake),
        "intake_payer_response": RESPONSE_CODES[intake.lookup["code"]]["short"] if payer_response_labeled(intake)
        else "not checked yet",
        "intake_open_question": open_question_line(intake),
        # Read by the engine gate on record_intake (`requires` in skill.md): the
        # tool is not offered to the model until the payer response is labelled
        # and any open question has an owner. record_intake checks both itself.
        "intake_ready_to_record": "yes" if ready_to_record(intake) else "",
    }


def _view(service: IntakeService, intake: Intake) -> dict:
    visit = service.data["visits"][intake.visit_id]
    return {
        "intake_id": intake.intake_id,
        "intake_version": intake.version,
        "intake_tag": intake.tag,
        "visit": {"visit_id": intake.visit_id, **{k: visit[k] for k in ("kind", "date", "time")}},
        "phone": intake.phone,
        "payer": intake.payer_name,
        "payer_in_directory": intake.payer_key is not None,
        "member_id": intake.member_id,
        "policyholder": intake.policyholder,
        "payer_response": _public_lookup(intake.lookup) if payer_response_labeled(intake) else None,
        "open_question_owner": intake.followup,
        "payment_guarantee": None,
        "recorded": False,
    }


def _public_lookup(lookup: Optional[dict]) -> Optional[dict]:
    if lookup is None:
        return None
    return {k: lookup[k] for k in ("lookup_id", "code", "label", "meaning", "open_question", "payer", "member_id",
                                   "checked_at")}


def _own_intake(service: IntakeService, patient_id: Optional[str], intake_id: Any) -> Optional[Intake]:
    intake = service.intakes.get(str(intake_id or "").strip().upper())
    return intake if intake is not None and patient_id and intake.patient_id == patient_id else None


def _no_intake(intake_id: Any) -> dict:
    return {"status": "not_found", "reason": "no_such_intake", "intake_id_given": str(intake_id or "")[:30],
            "next_step": "No intake exists under that id in this chat. Start one with start_intake."}


def _already_recorded(intake: Intake) -> dict:
    return {"status": "blocked", "reason": "already_recorded", "intake_id": intake.intake_id,
            "next_step": "This intake is already recorded and cannot be changed in this chat. Give its reference."}


def _next_step(intake: Intake) -> str:
    if intake.lookup is None or not payer_response_labeled(intake):
        return ("Tell the patient the details on the intake. Call check_eligibility with this intake_id before "
                "recording; there is no payer response for the current insurance.")
    if intake.lookup["open_question"] and intake.followup is None:
        return ("The payer response leaves the patient's insurance question open. Give the patient the code and label "
                "exactly as returned, say coverage and payment are not confirmed, and call assign_access_followup with "
                "this intake_id and a one-line question. The visit stays booked.")
    return ("When the patient wants to record the intake, call record_intake with this intake_id straight away; the "
            "engine reads it back and asks them. Never say the visit is covered or will be paid.")


# ----------------------------------------------------------------------------
# Tools: start, update, eligibility, follow-up
# ----------------------------------------------------------------------------


def start_intake(service: IntakeService, patient_id: Optional[str], conversation_id: str) -> tuple[dict, Optional[Intake]]:
    """Open this patient's pre-visit intake from the details on file."""
    if not patient_id:
        return {"status": "not_found", "reason": "no_signed_in_patient",
                "next_step": "Say the account could not be loaded and give the patient access team as the route."}, None
    open_intakes = [i for i in service.intakes.values() if i.patient_id == patient_id and i.intake_id not in service.records]
    if open_intakes:
        intake = open_intakes[-1]
        return {"status": "existing", **_view(service, intake), "next_step": _next_step(intake)}, intake
    visit_id, _ = service.visit_for(patient_id)
    on_file = service.data["on_file"][patient_id]
    intake_id = "CC-IN-" + _digest(conversation_id, patient_id, len(service.intakes)).upper()[:5]
    intake = Intake(
        intake_id=intake_id, patient_id=patient_id, visit_id=visit_id, phone=on_file["phone"],
        payer_key=on_file["payer_key"], payer_name=service.payer_label(on_file["payer_key"]),
        member_id=on_file["member_id"], policyholder=normalise_policyholder(on_file["policyholder"]),
    )
    service.intakes[intake_id] = intake
    return {"status": "drafted", "details_from": "the clinic's registration record", **_view(service, intake),
            "next_step": ("These are the details on file. Ask the patient only about anything they say has changed "
                          "and record changes with update_intake. Then call check_eligibility.")}, intake


def update_intake(service: IntakeService, patient_id: Optional[str], intake_id: Any, phone: Any = None,
                  payer: Any = None, member_id: Any = None, policyholder: Any = None) -> tuple[dict, Optional[Intake]]:
    """Change a field. A new payer or member id invalidates the earlier eligibility lookup."""
    intake = _own_intake(service, patient_id, intake_id)
    if intake is None:
        return _no_intake(intake_id), None
    if intake.intake_id in service.records:
        return _already_recorded(intake), intake
    changes: dict[str, Any] = {}
    if phone not in (None, ""):
        normal = normalise_phone(phone)
        if normal is None:
            return {"status": "blocked", "reason": "phone_not_understood", "phone_given": str(phone)[:30],
                    "intake_id": intake.intake_id,
                    "next_step": "Ask the patient for the phone number again, digits only."}, intake
        changes["phone"] = normal
    new_member = None
    if member_id not in (None, ""):
        new_member = normalise_member_id(member_id)
        if new_member is None:
            return {"status": "blocked", "reason": "member_id_not_understood", "member_id_given": str(member_id)[:30],
                    "intake_id": intake.intake_id,
                    "next_step": "Ask the patient to read the member id from their insurance card."}, intake
        changes["member_id"] = new_member
    if payer not in (None, ""):
        key, name = resolve_payer(service, payer)
        changes["payer_key"], changes["payer_name"] = key, name
    elif new_member is not None and new_member != intake.member_id:
        key, name = resolve_payer(service, "", new_member)
        if key is not None and key != intake.payer_key:
            changes["payer_key"], changes["payer_name"] = key, name
    if policyholder not in (None, ""):
        changes["policyholder"] = normalise_policyholder(policyholder)
    changed = [k for k, v in changes.items() if getattr(intake, k) != v]
    if not changed:
        return {"status": "unchanged", **_view(service, intake), "next_step": _next_step(intake)}, intake
    previous_lookup = intake.lookup
    for key in changes:
        setattr(intake, key, changes[key])
    insurance_changed = any(k in changed for k in ("payer_key", "payer_name", "member_id"))
    invalidated = previous_lookup is not None and insurance_changed
    if insurance_changed:
        intake.lookup = None
        intake.followup = None
    intake.version += 1
    names = {"payer_key": "payer", "payer_name": "payer"}
    result = {"status": "updated", "changed": sorted({names.get(k, k) for k in changed}),
              **_view(service, intake),
              "previous_lookup_invalidated": invalidated,
              "next_step": ("The payer changed but the member id did not. Ask the patient for the member id on the "
                            "new card and record it with update_intake before checking eligibility."
                            if insurance_changed and "member_id" not in changes else
                            "The insurance changed, so any earlier payer response no longer applies. Call "
                            "check_eligibility before recording." if insurance_changed
                            else "The intake changed; the engine reads the new version back when record_intake is called.")}
    if invalidated:
        result["previous_payer_response"] = {k: previous_lookup[k] for k in ("lookup_id", "code", "member_id")}
    return result, intake


def check_eligibility(service: IntakeService, patient_id: Optional[str], intake_id: Any) -> tuple[dict, Optional[Intake]]:
    """Run the administrative eligibility check for the intake's current payer and member id."""
    intake = _own_intake(service, patient_id, intake_id)
    if intake is None:
        return _no_intake(intake_id), None
    if intake.intake_id in service.records:
        return _already_recorded(intake), intake
    if intake.payer_key is None:
        code = service.data["unlisted_payer_code"]
    else:
        code = service.data["eligibility"].get(f"{intake.payer_key}|{intake.member_id}", service.data["unknown_member_code"])
    info = RESPONSE_CODES[code]
    service.lookups += 1
    lookup = {
        "lookup_id": "CC-EL-" + _digest(intake.intake_id, service.lookups, code).upper()[:5],
        "code": code,
        "label": info["label"],
        "meaning": info["meaning"],
        "uncertain": info["uncertain"],
        "open_question": info["open_question"],
        "payer": intake.payer_name,
        "payer_key": intake.payer_key,
        "member_id": intake.member_id,
        "checked_at": service.as_of.isoformat(timespec="minutes"),
    }
    same = intake.lookup is not None and intake.lookup["code"] == code and intake.lookup["member_id"] == intake.member_id \
        and intake.lookup["payer_key"] == intake.payer_key
    if not same:
        intake.lookup = lookup
        intake.followup = None
        intake.version += 1
    result = {"status": "checked", **_view(service, intake), "next_step": _next_step(intake)}
    return result, intake


def assign_access_followup(service: IntakeService, patient_id: Optional[str], intake_id: Any,
                           question: Any) -> tuple[dict, Optional[Intake]]:
    """Give the open insurance question to the patient access owner. Decides nothing."""
    intake = _own_intake(service, patient_id, intake_id)
    if intake is None:
        return _no_intake(intake_id), None
    if intake.intake_id in service.records:
        return _already_recorded(intake), intake
    if not payer_response_labeled(intake):
        return {"status": "blocked", "reason": "no_payer_response", "intake_id": intake.intake_id,
                "next_step": "Call check_eligibility first; there is no payer response for the current insurance."}, intake
    if not intake.lookup["open_question"]:
        return {"status": "refused", "reason": "no_open_question", "intake_id": intake.intake_id,
                "payer_response": _public_lookup(intake.lookup),
                "next_step": ("The payer reports active coverage, so there is no open eligibility question. Active "
                              "coverage is still not a guarantee of payment.")}, intake
    if intake.followup is None or intake.followup["for_lookup"] != intake.lookup["lookup_id"]:
        team = service.data["access_team"]
        intake.followup = {
            "desk_reference": "CC-PAQ-" + _digest(intake.intake_id, intake.lookup["lookup_id"]).upper()[:6],
            "owner": OWNER,
            "desk": team["desk"],
            "reply_window": team["reply_window"],
            "question": " ".join(str(question or "").split())[:QUESTION_LIMIT] or intake.lookup["label"],
            "for_lookup": intake.lookup["lookup_id"],
            "payer_response_code": intake.lookup["code"],
        }
        intake.version += 1
    visit = service.data["visits"][intake.visit_id]
    return {"status": "assigned", **_view(service, intake), "visit_kept": True,
            "next_step": (f"Give the desk reference. Say {intake.followup['desk']} replies within "
                          f"{intake.followup['reply_window']}, the {visit['kind']} stays booked, and coverage and "
                          "payment are not confirmed. Then offer to record the intake.")}, intake


# ----------------------------------------------------------------------------
# Recording the intake: the guard and the receipt
# ----------------------------------------------------------------------------


def intake_reference(intake_id: str) -> str:
    return f"CC-INR-{int(_digest(intake_id, 'record'), 16) % 90000 + 10000:05d}"


def intake_fields_confirmed(intake: Intake, memory: dict, conversation: Conversation) -> bool:
    """The engine read back this exact version and the patient answered it."""
    return (
        memory.get("intake_id") == intake.intake_id
        and memory.get("intake_tag") == intake.tag
        and conversation.confirmation_question is not None
        and intake.tag in conversation.confirmation_question
        and conversation.confirmation_answered
    )


def record_intake(service: IntakeService, patient_id: Optional[str], memory: dict, conversation: Conversation,
                  intake_id: Any) -> dict:
    """Record one confirmed intake, with its payer response and the owner of any open question."""
    wanted = str(intake_id or "").strip().upper()
    if wanted in service.records:
        return receipt(service, service.records[wanted], replay=True)
    intake = _own_intake(service, patient_id, wanted)
    if intake is None:
        return {"status": "blocked", "reason": "unconfirmed_intake", "intake_id_given": wanted[:30], "effects": 0,
                "facts": {"intake_fields_confirmed": False}, "payment_guarantee": None,
                "next_step": "There is no intake with that id in this chat. Nothing was recorded."}
    facts = {
        "intake_fields_confirmed": intake_fields_confirmed(intake, memory, conversation),
        "payer_response_labeled": payer_response_labeled(intake),
        "followup_owner_assigned": followup_owner_assigned(intake),
    }
    reason = evaluate(facts, "request")
    if reason:
        steps = {
            "unconfirmed_intake": ("Nothing was recorded. The engine has not read this version of the intake back to "
                                   "the patient. Call record_intake again so the engine asks them."),
            "eligibility_as_guarantee": ("Nothing was recorded. There is no labelled payer response for the current "
                                         "insurance. Call check_eligibility first."),
            "unowned_eligibility_question": ("Nothing was recorded. The payer response leaves a question open and it "
                                             "has no owner. Call assign_access_followup first."),
        }
        return {"status": "blocked", "reason": reason, "intake_id": intake.intake_id, "intake_tag": intake.tag,
                "facts": facts, "effects": 0, "recorded": False, "payment_guarantee": None,
                "next_step": steps[reason]}
    record = {
        "intake_id": intake.intake_id,
        "intake_tag": intake.tag,
        "patient_id": patient_id,
        "visit_id": intake.visit_id,
        "phone": intake.phone,
        "payer": intake.payer_name,
        "member_id": intake.member_id,
        "policyholder": intake.policyholder,
        "lookup": dict(intake.lookup),
        "followup": dict(intake.followup) if intake.followup else None,
        "intake_reference": intake_reference(intake.intake_id),
        "facts": facts,
    }
    service.records[intake.intake_id] = record
    return receipt(service, record, replay=False)


def receipt(service: IntakeService, record: dict, *, replay: bool) -> dict:
    lookup = record["lookup"]
    visit = service.data["visits"][record["visit_id"]]
    followup = record["followup"]
    return {
        "status": "succeeded",
        "reason": "verified_fixture_receipt",
        "intake_reference": record["intake_reference"],
        "intake_id": record["intake_id"],
        "visit": {"kind": visit["kind"], "date": visit["date"], "time": visit["time"], "kept": True},
        "phone": record["phone"],
        "payer": record["payer"],
        "member_id": record["member_id"],
        "policyholder": record["policyholder"],
        "payer_response": _public_lookup(lookup),
        "open_question_owner": None if followup is None else {
            "owner": followup["owner"], "desk": followup["desk"], "desk_reference": followup["desk_reference"],
            "reply_window": followup["reply_window"]},
        "payment_guarantee": None,
        "recorded": True,
        "effects": 0 if replay else 1,
        "replay": replay,
        "facts": record["facts"],
        "next_step": ("Give the intake reference, the payer response code and label, and who owns any open question. "
                      "The eligibility check is administrative: never say the visit is covered or will be paid."
                      + (" This is the same intake as before; nothing was recorded twice." if replay else "")),
    }


def refer_clinical_question(service: IntakeService) -> dict:
    """The clinical route: a contact, never advice. Records nothing about the question."""
    route = service.data["clinical_route"]
    return {
        "status": "referred",
        "route": f"{route['desk']} on {route['phone']}",
        "urgent": route["urgent"],
        "advice_given": False,
        "recorded": False,
        "next_step": ("Say this chat handles administrative intake only and cannot answer clinical or medication "
                      "questions. Give the route and the urgent line exactly. Do not answer the question."),
    }


# ----------------------------------------------------------------------------
# The receipt the tool sends itself (TOOL_SENDS_RECEIPT)
# ----------------------------------------------------------------------------


def customer_receipt(tool: str, result: dict) -> Optional[str]:
    """The message a tool sends the patient for an outcome they must see, or None."""
    status = result.get("status")
    if tool == "record_intake" and status == "succeeded":
        response = result["payer_response"]
        owner = result.get("open_question_owner")
        visit = result["visit"]
        when = spoken_date(date.fromisoformat(visit["date"]))
        again = " It was already recorded; nothing was recorded twice." if result.get("replay") else ""
        question = (f"Open insurance question: with {owner['desk']} under {owner['desk_reference']}; they reply within "
                    f"{owner['reply_window']}." if owner else "Open insurance question: none.")
        return (f"Intake recorded: {result['intake_reference']} for your {visit['kind']} on {when} at {visit['time']}."
                f"{again} Payer response: {response['code']} ({response['label'].replace('_', ' ')}). {question} "
                "Your visit stays booked. The eligibility check is administrative, not a promise of payment.")
    if tool == "assign_access_followup" and status == "assigned":
        owner = result["open_question_owner"]
        visit = result["visit"]
        when = spoken_date(date.fromisoformat(visit["date"]))
        return (f"Your insurance question is with {owner['desk']} under {owner['desk_reference']}; they reply within "
                f"{owner['reply_window']}. Your {visit['kind']} on {when} stays booked. Coverage and payment are not "
                "confirmed.")
    return None
