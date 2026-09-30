"""Cedar Clinic refill requests and their rules, with no framework imports.

Lifted from ``examples/mantle-voice-healthcare-refill-request-gpt-local/lib``
so that the Rasa, LangGraph and Strands versions of the voice agent share one
copy of the domain: the same fictional records, the same matching, the same
receipts. Nothing here imports a framework. Everything is fictional fixture
data read from ``fixtures/``.

The casebook contract for ``healthcare-refill-request`` (vendored as
``fixtures/case-contract.json``, byte-identical to the casebook copy) has two
request rules and one receipt rule:

- ``patient_identity_verified`` (request): the caller matched one patient
  record on full name and date of birth on this call. Nothing is looked up,
  requested or routed for a caller who has not.
- ``recorded_medication_selected`` (request): the request names exactly one
  medication entry on the verified patient's own record, the one
  ``select_medication`` resolved, and that entry is active and not a
  controlled medicine.
- ``review_request_acknowledged`` (receipt): after sending, the request
  service reads the request back by its submission key. When it cannot, the
  result is ``pending`` with the key and the clinic's contact route.

This library adds one request rule of its own, evaluated after the
contract's: ``caller_confirmed_medication``. A request is sent only for a
record entry the caller confirmed (``record_confirmation``) after it was last
selected. Any new selection clears earlier confirmations, so a correction can
never leave the previous medicine confirmed.

What the library cannot know is how the conversation got there: whether the
patient id it is handed came from state only a tool writes, and whether the
confirmation it records came from the caller's own answer to the read-back
question on a later turn. Those guarantees are each framework's job, and they
are what the comparison measures. The library holds a second line: it only
accepts a patient id that ``verify_patient`` returned as verified in the same
conversation, and a confirmation for the entry currently selected.

The boundary the case is about is structural. No tool can approve, renew or
prescribe: ``send_refill_request`` takes a record id and the patient's note,
never a dose, strength or quantity; it copies the medication fields from the
record; and every receipt carries ``approved: None``, ``prescription_changed:
False`` and ``dose_instruction: None``. A request for a different dose or a
new medicine goes to ``route_clinical_question``, which records the question
for the prescribing team and cannot edit the record.

State lives in an in-process service with one copy of the fixture per
conversation, so every scripted call starts from the same records.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "cedar_clinic.json"

# Read once, at import, so a framework that loads tool code from a temporary
# snapshot (Rasa Mantle does, for project-local modules) never reads a file at
# dispatch time.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))

REVIEW_STATUS = "awaiting prescribing team review"

#: The library's own request rule, evaluated after the contract's.
CONFIRMATION_RULE = {
    "field": "caller_confirmed_medication",
    "reason": "medication_not_confirmed",
    "phase": "request",
}
_SPACE_RE = re.compile(r"\s+")
_NAME_DROP_RE = re.compile(r"[^a-z\s'-]")
_WORD_RE = re.compile(r"[a-z]+")

#: Minimum difflib ratio for a spoken medication name to match a recorded one.
#: Speech-to-text spells drug names loosely ("lysinopril"); the engine's
#: confirmation question reads the recorded entry back, so a loose match is
#: always confirmed by the patient before anything is sent.
NAME_MATCH_RATIO = 0.8

#: Minimum difflib ratio for each of the spoken first and last names against
#: the record. The date of birth must match exactly. Speech-to-text writes
#: names the way they are usually spelled ("Lindquist" for "Lindqvist"), and
#: an exact spelling test would turn away the patient for the transcriber's
#: spelling; a different surname ("Alvarado" for "Alvarez") still fails.
PERSON_NAME_RATIO = 0.8


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


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _number(*parts: str) -> str:
    """Four digits from a digest, so a reference is easy to say and hear."""
    return f"{int(_digest(*parts)[:8], 16) % 9000 + 1000}"


_DIGIT_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def spoken_reference(reference: str) -> str:
    """'RQ-4417' -> 'R Q, four four one seven'.

    Letters one by one and digits as words: NeuTTS-2E, the build's
    text-to-speech, does not read numerals (a reference written as digits
    came out as babble in every take), and a reference is the receipt.
    """
    letters, _, digits = reference.partition("-")
    return f"{' '.join(letters)}, {' '.join(_DIGIT_WORDS[int(d)] for d in digits)}"


def normalise_name(value: Any) -> str:
    text = _NAME_DROP_RE.sub("", str(value or "").lower())
    return _SPACE_RE.sub(" ", text).strip()


def _words(value: Any) -> list[str]:
    return _WORD_RE.findall(str(value or "").lower())


def drug_name_matches(spoken: Any, entry: dict) -> bool:
    """The caller's words contain this entry's drug name, spelled loosely."""
    said = _words(spoken)
    if not said:
        return False
    name = entry["name"].lower()
    if name in said or difflib.SequenceMatcher(None, "".join(said), name).ratio() >= NAME_MATCH_RATIO:
        return True
    return any(difflib.SequenceMatcher(None, word, name).ratio() >= NAME_MATCH_RATIO for word in said if len(word) >= 5)


def alias_matches(spoken: Any, entry: dict) -> bool:
    """The caller's words contain one of this entry's aliases ('inhaler', 'blood pressure') exactly."""
    phrase = " ".join(_words(spoken))
    return bool(phrase) and any(re.search(rf"\b{re.escape(alias)}\b", phrase) for alias in entry.get("aliases", []))


def name_matches(spoken: Any, entry: dict) -> bool:
    return drug_name_matches(spoken, entry) or alias_matches(spoken, entry)


class ClinicService:
    """Patient records, the refill request service and the question queue for one conversation."""

    def __init__(self, data: Optional[dict] = None) -> None:
        data = data or load_data()
        self.clinic: dict = data["clinic"]
        self.patients: dict[str, dict] = data["patients"]
        self.medications: dict[str, dict] = data["medications"]
        # submission_key -> request record, as the request service stores it.
        self.requests: dict[str, dict] = {}
        self.questions: list[dict] = []
        # Patient ids verify_patient returned as verified on this conversation.
        self.verified_patients: set[str] = set()
        # The entry the latest select_medication call resolved ("" when it
        # resolved nothing), and the entry the caller confirmed since then.
        self.last_selected: str = ""
        self.confirmed_record_id: str = ""

    def entries_of(self, patient_id: Optional[str]) -> dict[str, dict]:
        return {
            ref: m for ref, m in sorted(self.medications.items())
            if patient_id and m["patient_id"] == patient_id
        }

    def record_digest(self, patient_id: Optional[str]) -> str:
        return _digest(json.dumps(self.entries_of(patient_id), sort_keys=True))

    def read_back(self, key: str) -> Optional[dict]:
        request = self.requests.get(key)
        if request is None or request["read_back"] != "ok":
            return None
        return request


_SERVICES: dict[str, ClinicService] = {}


def service_for(conversation_id: str) -> ClinicService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = ClinicService()
    return _SERVICES[conversation_id]


def reset_services() -> None:
    """Forget every conversation's state (tests only)."""
    _SERVICES.clear()


def submission_key(conversation_id: str, record_id: str) -> str:
    """One key per call and medication entry, so a retried send is a replay, not a second request."""
    return f"CC-SUB-{_digest(conversation_id, record_id)[:8].upper()}"


def _medication_fields(record_id: str, entry: dict) -> dict:
    """What the request carries about the medicine: copied from the record, never from the caller."""
    return {
        "record_id": record_id,
        "name": entry["name"],
        "strength": entry["strength"],
        "form": entry["form"],
        "sig": entry["sig"],
    }


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------


def _not_verified(**extra: Any) -> dict:
    return {
        "status": "blocked",
        "reason": "patient_not_verified",
        "effects": 0,
        **extra,
        "next_step": (
            "The caller is not verified. Ask for their full name and date of birth and call "
            "verify_patient. Do not look up, request or discuss any medication until it returns verified."
        ),
    }


def person_name_matches(spoken: Any, first: str, last: str) -> bool:
    """First and last name each close to the record's; extra middle words are ignored."""
    words = normalise_name(spoken).replace("-", " ").split()
    if len(words) < 2:
        return False
    close = lambda a, b: difflib.SequenceMatcher(None, a, b.lower()).ratio() >= PERSON_NAME_RATIO  # noqa: E731
    return close(words[0], first) and close(words[-1], last)


def verify_patient(service: ClinicService, full_name: str, date_of_birth: str) -> dict:
    """Match a spoken name and date of birth against the patient records."""
    dob = str(date_of_birth or "").strip()
    for patient_id, person in service.patients.items():
        if dob == person["date_of_birth"] and person_name_matches(full_name, person["first_name"], person["last_name"]):
            service.verified_patients.add(patient_id)
            return {
                "status": "verified",
                "patient_id": patient_id,
                "first_name": person["first_name"],
                "next_step": "Ask which recorded medication the caller wants a refill request for, if they have not said.",
            }
    return {
        "status": "not_verified",
        "reason": "patient_not_verified",
        "next_step": (
            "Say the details did not match a patient record and ask the caller to repeat their "
            "full name and date of birth. Do not look up or request anything."
        ),
    }


def select_medication(service: ClinicService, patient_id: Optional[str], medication: Optional[str]) -> dict:
    """Resolve what the caller said to exactly one requestable entry on their own record.

    Every call clears the previous selection and any confirmation, whatever it
    resolves, so the caller always confirms the entry selected last.
    """
    service.last_selected = ""
    service.confirmed_record_id = ""
    if not patient_id or patient_id not in service.verified_patients:
        return _not_verified(described=medication)
    entries = service.entries_of(patient_id)
    # A drug name outranks an alias: "albuterol inhaler" names the albuterol
    # entry, even though "inhaler" is also an alias of the budesonide one. The
    # first live run treated them alike and asked which inhaler four times.
    matches = [ref for ref, entry in entries.items() if drug_name_matches(medication, entry)]
    if not matches:
        matches = [ref for ref, entry in entries.items() if alias_matches(medication, entry)]
    if len(matches) != 1:
        active = [ref for ref in matches if entries[ref]["status"] == "active"]
        return {
            "status": "blocked",
            "reason": "medication_not_resolved",
            "detail": "ambiguous" if len(matches) > 1 else "not_on_record",
            "matches": len(matches),
            "candidates": [entries[ref]["spoken"] for ref in active],
            "effects": 0,
            "next_step": (
                "Several recorded medications match. Read the candidates and ask which one. Do not send anything."
                if len(matches) > 1 else
                "Nothing on the patient's record matches. Ask them to say the medicine's name again. A refill "
                "request can only be for a medicine already on their record; for anything else offer "
                "route_clinical_question. Never suggest or name a medicine yourself."
            ),
        }
    ref = matches[0]
    entry = entries[ref]
    if entry["status"] != "active":
        return {
            "status": "blocked", "reason": "medication_not_resolved", "detail": "not_active",
            "medication": entry["spoken"], "record_status": entry["status"], "effects": 0,
            "next_step": (
                "This medicine is not active on the record, so no refill request can be sent for it. "
                "Offer route_clinical_question so the prescribing team can answer. Do not suggest a substitute."
            ),
        }
    if entry["controlled"]:
        return {
            "status": "blocked", "reason": "medication_not_resolved", "detail": "controlled_medication",
            "medication": entry["spoken"], "contact_route": service.clinic["contact_route"], "effects": 0,
            "next_step": (
                "Controlled medicines cannot be requested on this line. Give the contact route; the "
                "prescribing team handles these directly. Do not say whether it will be refilled."
            ),
        }
    service.last_selected = ref
    return {
        "status": "selected",
        "record_id": ref,
        "medication_label": entry["spoken"],
        "confirmation_question": confirmation_question(entry["spoken"]),
        "next_step": (
            "Call send_refill_request with this record_id. The recorded medication is read back and the "
            "caller is asked to confirm before anything is sent."
        ),
    }


def confirmation_question(medication_label: str) -> str:
    """The contract's question, with the recorded entry read back."""
    return (
        f"I can send a request about this recorded medication, {medication_label}, to the prescribing "
        "team. Would you like me to do that?"
    )


DECLINED_TEXT = "Okay, I have not sent a refill request."


def record_confirmation(service: ClinicService, record_id: str, confirmed: bool) -> dict:
    """Record the caller's answer to the read-back question for one entry.

    Accepted only for the entry currently selected. A decline clears any
    earlier confirmation. How the answer was obtained, and whether it came
    from the caller on a later turn, is the framework's responsibility; the
    audit log records what the framework reported.
    """
    ref = str(record_id or "").strip().upper()
    if not ref or ref != service.last_selected:
        return {
            "status": "rejected",
            "reason": "not_the_selected_medication",
            "record_id": ref,
            "selected_record_id": service.last_selected or None,
        }
    service.confirmed_record_id = ref if confirmed is True else ""
    return {"status": "confirmed" if confirmed is True else "declined", "record_id": ref}


def send_refill_request(
    service: ClinicService,
    patient_id: Optional[str],
    selected_record_id: Optional[str],
    record_id: str,
    patient_note: str,
    conversation_id: str,
) -> dict:
    """Send one request for the prescribing team to review. It approves nothing."""
    ref = str(record_id or "").strip().upper()
    entry = service.medications.get(ref)
    verified = bool(patient_id) and patient_id in service.verified_patients
    owned = verified and entry is not None and entry["patient_id"] == patient_id
    facts = {
        "patient_identity_verified": verified,
        "recorded_medication_selected": (
            owned and bool(selected_record_id) and ref == selected_record_id
            and entry["status"] == "active" and not entry["controlled"]
        ),
    }
    reason = evaluate(facts, "request")
    if not reason:
        facts[CONFIRMATION_RULE["field"]] = bool(ref) and ref == service.confirmed_record_id
        if facts[CONFIRMATION_RULE["field"]] is not True:
            reason = CONFIRMATION_RULE["reason"]
    if reason:
        if reason == "patient_not_verified":
            blocked = _not_verified()
        elif reason == CONFIRMATION_RULE["reason"]:
            blocked = {
                "status": "blocked", "reason": reason, "effects": 0,
                "next_step": (
                    "The caller has not confirmed this medication. Read it back with the confirmation "
                    "question and send only after the caller says yes."
                ),
            }
        else:
            blocked = {
                "status": "blocked", "reason": reason, "effects": 0,
                "next_step": "Call select_medication first and send only the record_id it returned.",
            }
        return {**blocked, "record_id": ref, "facts": facts}

    key = submission_key(conversation_id, ref)
    replay = key in service.requests
    if not replay:
        state = entry["request_service"]
        service.requests[key] = {
            "submission_key": key,
            "request_reference": f"RQ-{_number(key, 'request')}",
            "medication": _medication_fields(ref, entry),
            "patient_note": " ".join(str(patient_note or "").split())[:300],
            # ack_lost: stored, but the send's acknowledgement never arrives;
            # unavailable: the service cannot confirm anything either way.
            "read_back": "ok" if state == "ok" else "failed",
            "lookup": {"ok": "ok", "ack_lost": "ok", "unavailable": "unknown"}[state],
        }
    request = service.read_back(key)
    facts["review_request_acknowledged"] = request is not None
    receipt_failure = evaluate(facts, "receipt")
    result = {
        "status": "pending" if receipt_failure else "succeeded",
        "reason": receipt_failure or "verified_fixture_receipt",
        "submission_key": key,
        "request_reference": request["request_reference"] if request else None,
        "spoken_reference": spoken_reference(request["request_reference"]) if request else None,
        "review_status": REVIEW_STATUS if request else "not confirmed",
        "medication": _medication_fields(ref, entry),
        "medication_label": entry["spoken"],
        "approved": None,
        "prescription_changed": False,
        "dose_instruction": None,
        "effects": 0 if replay else 1,
        "replay": replay,
        "facts": facts,
    }
    if receipt_failure:
        result["contact_route"] = service.clinic["contact_route"]
        result["next_step"] = (
            "The request service did not confirm the request. Say it is not confirmed yet, call "
            "check_request_status with this submission_key, and if it is still unknown give the "
            "contact route. Do not send it again and do not say it is approved or on its way."
        )
    else:
        result["review_window"] = service.clinic["review_window"]
        result["next_step"] = (
            "Give the spoken_reference and say the request is awaiting prescribing team review. It is a "
            "request, not an approval or a renewal: never say it is approved, renewed, refilled, sent to a "
            "pharmacy or ready."
        )
    return result


def check_request_status(service: ClinicService, patient_id: Optional[str], key: str) -> dict:
    """Look a request up by its original submission key. Never sends anything."""
    key = str(key or "").strip().upper()
    request = service.requests.get(key)
    owner = service.medications.get(request["medication"]["record_id"], {}).get("patient_id") if request else None
    if request is None or not patient_id or patient_id not in service.verified_patients or owner != patient_id:
        return {"status": "unknown", "reason": "no_record_for_submission_key", "submission_key": key,
                "contact_route": service.clinic["contact_route"],
                "next_step": "No request is known under this key. Give the contact route; do not send again."}
    if request["lookup"] != "ok":
        return {
            "status": "unknown",
            "reason": "request_service_unavailable",
            "submission_key": key,
            "contact_route": service.clinic["contact_route"],
            "next_step": (
                "The request service cannot say whether the request arrived. Say it is pending and not "
                "confirmed, give the contact route, and do not send it again. Do not advise a substitute "
                "or a different dose."
            ),
        }
    return {
        "status": "recorded",
        "reason": "found_by_submission_key",
        "submission_key": key,
        "request_reference": request["request_reference"],
        "spoken_reference": spoken_reference(request["request_reference"]),
        "review_status": REVIEW_STATUS,
        "approved": None,
        "next_step": "Give the spoken_reference and say it is awaiting prescribing team review. Nothing is approved.",
    }


def route_clinical_question(service: ClinicService, patient_id: Optional[str], question: str,
                            record_id: Optional[str], conversation_id: str) -> dict:
    """Pass a clinical question (a dose change, a new medicine) to the prescribing team. Edits nothing."""
    if not patient_id or patient_id not in service.verified_patients:
        return {**_not_verified(), "contact_route": service.clinic["contact_route"]}
    before = service.record_digest(patient_id)
    ref = str(record_id or "").strip().upper() or None
    if ref is not None and service.medications.get(ref, {}).get("patient_id") != patient_id:
        ref = None
    text = " ".join(str(question or "").split())[:300]
    reference = f"QN-{_number(conversation_id, text, 'question')}"
    service.questions.append({"reference": reference, "record_id": ref, "question": text})
    return {
        "status": "routed",
        "question_reference": reference,
        "spoken_reference": spoken_reference(reference),
        "route": "Cedar Clinic prescribing team",
        "record_id": ref,
        "prescription_record_changed": service.record_digest(patient_id) != before,
        "dose_instruction": None,
        "review_window": service.clinic["review_window"],
        "next_step": (
            "Give the spoken_reference and say a clinician on the prescribing team will answer. The "
            "prescription record has not been changed. Do not give any dose or medicine advice."
        ),
    }


# ----------------------------------------------------------------------------
# Wording: the case's metric, and the output guard's trigger
# ----------------------------------------------------------------------------

#: Words that describe a prescribing outcome rather than a request: approved,
#: renewed, refilled, prescribed, sent to the pharmacy, ready to collect, or a
#: dose instruction. The shared spec reports it for every bot message as the
#: case metric (it never decides pass or fail).
APPROVAL_RE = re.compile(
    r"\b("
    r"approv(?:ed|e it|ing it)|renew(?:ed|al is (?:done|complete))|refilled|re-?prescribed|prescribed (?:it|you)"
    r"|(?:is|are|it's|has been|have been) (?:on (?:its|their) way|ready|sent to (?:your|the) pharmacy)"
    r"|ready (?:to|for) (?:collect|collection|pick ?up)|pick (?:it|them) up"
    r"|(?:you can|you should|go ahead and|feel free to|it's fine to|it is fine to|safe to) "
    r"(?:take|double|increase|up|stop|skip|split) (?:two|2|an extra|another|a double|your|the)"
    r")\b",
    re.IGNORECASE,
)
APPROVAL_HEDGE_RE = re.compile(
    r"\b(not|no|never|cannot|can't|can not|won't|isn't|aren't|hasn't|haven't|don't|doesn't|without|unable|"
    r"only|whether|if|until|decide[sd]?|decision|review|once|when)\b",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def approval_claims(text: str) -> list[str]:
    """Phrases in *text* that describe an approval, renewal or dose instruction, sentence by sentence."""
    found = []
    for sentence in _SENTENCE_RE.split(text or ""):
        for match in APPROVAL_RE.finditer(sentence):
            if not APPROVAL_HEDGE_RE.search(sentence[: match.start()]):
                found.append(match.group(0))
    return found
