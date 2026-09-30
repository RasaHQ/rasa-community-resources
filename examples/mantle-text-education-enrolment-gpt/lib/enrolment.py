"""Pine University application records, enquiries and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three rules of the casebook contract for ``education-enrolment``
(vendored as ``lib/fixtures/case-contract.json``) when an enquiry is recorded:

- ``applicant_identity_resolved`` (request): the application reference resolves
  to exactly one record of the signed-in applicant, and it is the record the
  engine's question named (the one ``lookup_application`` last wrote to skill
  memory). Another applicant's reference and one that does not exist get the
  same answer. A record filed under a duplicate applicant record that is still
  being merged is not resolved either: only the team can say it is the same
  person.
- ``decision_stage_explicit`` (request): every source for the record reports
  the same stage, and that stage is one of the explicit stages in the fixture.
  When the applicant portal and the team's own record disagree (the portal
  says "awarded", the committee's record says the review is running), no stage
  and no decision can be given, and the case is routed to the team instead.
- ``followup_reference_recorded`` (receipt): the team's case queue
  acknowledges the enquiry and returns a support reference. When the
  acknowledgment is lost, the result is ``pending`` with an attempt id, never
  ``succeeded``, and ``check_enquiry`` finds the same enquiry instead of
  recording it again.

A receipt is the support reference with the responsible team, the record's
stage, its decision (``None`` unless the team issued one) and its deadlines as
the authoritative source gives them. No tool takes a deadline or can move one.

Facts are computed from trusted data: the session's applicant id, the records
and the skill memory the lookup tool wrote. The model supplies a reference or
the applicant's words for a form, a topic, the applicant's question and a
reason. It never supplies a fact, an applicant id, a stage, a decision or a
deadline. A fact that is not exactly ``True`` fails its rule, as in the lab's
``evaluate``.

The organisation guard runs at import and is an allowlist: every organisation
field in the fixture must be the casebook contract's own fictional university,
marked fictional.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "pine_records.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (rasa/mantle/prompts/memory_lines.py,
# MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5). Every value a tool writes to memory
# is one short field and must fit; tests/test_guard.py checks every record.
MEMORY_VALUE_LIMIT = 100
# The applicant's question is stored with the enquiry, not in memory.
QUESTION_LIMIT = 240

# The tools send the applicant the receipt themselves through ToolContext.send,
# so it reaches them whatever the model does next (the fix for the silent
# complete_skill found in the Northgate transfer build and confirmed in the
# HarborCover claim-filing build). The `receipt-in-result-only` variant sets
# this to False.
TOOL_SENDS_RECEIPT = True

TOPICS = ("missing_evidence", "deadline", "decision_timing", "decision_question", "enrolment_step", "other")

# Organisation fields the allowlist checks, wherever they appear in the fixture.
ORGANISATION_KEYS = ("organisation", "university", "institution", "school", "college", "provider")

REFERENCE_RE = re.compile(r"\b(ADM|AID|SCH|ENR)[\s-]?(\d{2})[\s-]?(\d{4})\b", re.IGNORECASE)
ENQUIRY_RE = re.compile(r"\bPU[\s-]?(SUP|ATT)[\s-]?([0-9A-F]{6})\b", re.IGNORECASE)


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
SESSION_APPLICANT_ID = _DATA["session_applicant_id"]
OWNER = _CONTRACT["owner"]
AS_OF = date.fromisoformat(_DATA["as_of"][:10])


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


def _words(text: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _has_phrase(words: list[str], phrase: str) -> bool:
    target = _words(phrase)
    n = len(target)
    return n > 0 and any(words[i : i + n] == target for i in range(len(words) - n + 1))


def spoken_date(value: str) -> str:
    d = date.fromisoformat(value)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def plain(text: Any) -> str:
    """Typographic apostrophes and quotes to ASCII, for the word patterns."""
    return str(text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')


# ----------------------------------------------------------------------------
# The records service: the fixture copy for one conversation
# ----------------------------------------------------------------------------


class Records:
    """The synthetic admissions, aid, scholarship and registrar records, plus the case queues."""

    def __init__(self, data: Optional[dict] = None):
        self.data = json.loads(json.dumps(data or _DATA))
        # attempt_id -> enquiry; each one is a recorded effect in a team's queue.
        self.enquiries: dict[str, dict] = {}
        # (application reference, topic) -> attempt_id, for replays.
        self.by_key: dict[tuple[str, str], str] = {}
        # application reference -> routing
        self.routes: dict[str, dict] = {}
        # support and desk references the applicant has been sent.
        self.delivered: set[str] = set(self.data.get("existing_enquiries", {}))

    def record(self, reference: str) -> Optional[dict]:
        return self.data["records"].get(reference)

    def team_name(self, team: str) -> str:
        return self.data["teams"][team]["name"]

    def kind_label(self, kind: str) -> str:
        return self.data["kinds"][kind]["label"]

    def own_references(self, applicant_id: Optional[str]) -> list[str]:
        return sorted(r for r, rec in self.data["records"].items() if rec["applicant_id"] == applicant_id)

    def effects(self) -> int:
        return len(self.enquiries)


_SERVICES: dict[str, Records] = {}


def service_for(conversation_id: str) -> Records:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = Records()
    return _SERVICES[conversation_id]


def session_profile(applicant_id: str = SESSION_APPLICANT_ID, data: Optional[dict] = None) -> dict:
    data = data or _DATA
    person = data["applicants"][applicant_id]
    service = Records(data)
    refs = service.own_references(applicant_id)
    return {
        "applicant_id": applicant_id,
        "first_name": person["first_name"],
        "applications": [{"reference": r, "form": service.kind_label(data["records"][r]["kind"])} for r in refs],
        # One short field: "ADM-26-4471 admission; AID-26-1182 financial aid; ..."
        "application_list": "; ".join(f"{r} {data['records'][r]['kind'].replace('_', ' ')}" for r in refs),
    }


# ----------------------------------------------------------------------------
# Resolving the applicant's words to one record, and the facts about it
# ----------------------------------------------------------------------------


def normalise_reference(value: Any) -> Optional[str]:
    m = REFERENCE_RE.search(str(value or ""))
    return f"{m.group(1).upper()}-{m.group(2)}-{m.group(3)}" if m else None


def identity_resolved(service: Records, applicant_id: Optional[str], reference: Optional[str]) -> bool:
    """The record exists and belongs to the signed-in applicant's own applicant record."""
    rec = service.record(reference or "")
    return bool(applicant_id) and rec is not None and rec["applicant_id"] == applicant_id


def merge_pending(service: Records, applicant_id: Optional[str], reference: Optional[str]) -> bool:
    """The record sits on a duplicate applicant record that is being merged into this applicant's."""
    rec = service.record(reference or "")
    if rec is None or not applicant_id:
        return False
    owner = service.data["applicants"].get(rec["applicant_id"], {})
    return owner.get("merge_pending_with") == applicant_id


def stage_of(service: Records, rec: dict) -> Optional[str]:
    """The stage every source agrees on, when it is an explicit stage; else None."""
    values = set(rec["sources"].values())
    if len(values) != 1:
        return None
    (stage,) = values
    return stage if stage in service.data["stages"] else None


def facts_for(service: Records, applicant_id: Optional[str], reference: Optional[str],
              selected: Optional[str]) -> dict:
    """The request facts for recording an enquiry on *reference*, from trusted data only."""
    rec = service.record(reference or "")
    return {
        "applicant_identity_resolved": identity_resolved(service, applicant_id, reference)
        and reference == selected,
        "decision_stage_explicit": rec is not None and stage_of(service, rec) is not None,
    }


def resolve(service: Records, applicant_id: Optional[str], words: Any) -> tuple[str, Optional[str], list[str]]:
    """(outcome, reference, candidates) for the applicant's words.

    outcome is ``own`` (one of their records), ``merge_pending``, ``not_found``
    (someone else's or no such record: the same answer) or ``ambiguous``.
    """
    own = service.own_references(applicant_id)
    ref = normalise_reference(words)
    if ref:
        if ref in own:
            return "own", ref, [ref]
        if merge_pending(service, applicant_id, ref):
            return "merge_pending", ref, [ref]
        return "not_found", None, own
    tokens = _words(words)
    kinds = [k for k, spec in service.data["kinds"].items() if any(_has_phrase(tokens, w) for w in spec["words"])]
    hits = [r for r in own if service.record(r)["kind"] in kinds]
    if len(kinds) == 1 and len(hits) == 1:
        return "own", hits[0], hits
    return "ambiguous", None, hits or own


def decision_line(service: Records, rec: dict, stage: Optional[str]) -> str:
    team = service.team_name(rec["team"])
    if stage is None:
        return "The records for this form disagree, so no stage or decision can be confirmed."
    decision = rec.get("decision")
    if decision and decision.get("type") == "admission_offer":
        return f"The {team} issued a formal admission offer on {spoken_date(decision['issued_on'])}."
    return f"The {team} has not issued a decision yet."


def _deadlines(rec: dict) -> list[dict]:
    return [{"what": d["what"], "date": d["date"], "date_spoken": spoken_date(d["date"]), "source": d["source"]}
            for d in rec.get("deadlines") or []]


def _record_view(service: Records, reference: str) -> dict:
    rec = service.record(reference)
    stage = stage_of(service, rec)
    return {
        "application_reference": reference,
        "form": service.kind_label(rec["kind"]),
        "team": service.team_name(rec["team"]),
        "stage": stage,
        "stage_label": service.data["stages"][stage] if stage else None,
        "decision": rec.get("decision") if stage else None,
        "decision_line": decision_line(service, rec, stage),
        "outstanding_evidence": list(rec.get("outstanding") or []) if stage else [],
        # Deadlines come from the authoritative source named with each one, and
        # no tool can change them.
        "deadlines": _deadlines(rec),
        # The same dates as one flat string, for tracker checks.
        "deadline_dates": ", ".join(d["date"] for d in rec.get("deadlines") or []),
        "next_step": rec["next_step"] if stage else None,
    }


def memory_values(service: Records, reference: Optional[str]) -> dict:
    """What lookup_application writes to skill memory. Each value is one short field."""
    if not reference:
        return {key: "" for key in MEMORY_KEYS}
    view = _record_view(service, reference)
    return {
        "enquiry_ref": reference,
        "enquiry_form": view["form"],
        "enquiry_stage": view["stage_label"] or "",
        "enquiry_decision": view["decision_line"],
        "enquiry_next_step": view["next_step"] or "",
        "enquiry_team": view["team"],
    }


MEMORY_KEYS = ("enquiry_ref", "enquiry_form", "enquiry_stage", "enquiry_decision", "enquiry_next_step", "enquiry_team")


# ----------------------------------------------------------------------------
# The tools' logic
# ----------------------------------------------------------------------------

NOT_ON_RECORD = ("No application with that reference is on your applicant record. Never say whether it exists "
                 "or whose it is. Offer the applicant's own references.")


def lookup_application(service: Records, applicant_id: Optional[str], words: Any) -> tuple[dict, Optional[str]]:
    """(result, reference to write to skill memory or None)."""
    outcome, ref, candidates = resolve(service, applicant_id, words)
    if outcome == "ambiguous":
        return ({"status": "ambiguous",
                 "candidates": [{"reference": r, "form": service.kind_label(service.record(r)["kind"])} for r in candidates],
                 "next_step": "Ask which application they mean. Say nothing about any stage until one is looked up."},
                None)
    if outcome == "not_found":
        return ({"status": "not_found", "reason": "wrong_applicant_record", "your_references": candidates,
                 "next_step": NOT_ON_RECORD}, None)
    if outcome == "merge_pending":
        rec = service.record(ref)
        return ({"status": "blocked", "reason": "wrong_applicant_record", "application_reference": ref,
                 "applicant_identity_resolved": False,
                 "team": service.team_name(rec["team"]), "stage": None, "decision": None,
                 "detail": "This reference is on a separate applicant record that is being merged with yours. "
                           "Until the team confirms it, no stage, decision or deadline can be given for it.",
                 "next_step": "Call route_to_team with this reference. Give no status for it."}, None)
    view = _record_view(service, ref)
    if view["stage"] is None:
        return ({"status": "blocked", "reason": "submission_as_award", "decision_stage_explicit": False,
                 **{k: view[k] for k in ("application_reference", "form", "team", "stage", "decision", "decision_line",
                                         "deadlines", "deadline_dates")},
                 "sources_disagree": sorted(service.record(ref)["sources"]),
                 "next_step": "Say the records for this form disagree, so you cannot give a stage or confirm any "
                              "decision. Call route_to_team with this reference. Give the deadlines exactly as "
                              "listed."}, None)
    return ({"status": "found", "applicant_identity_resolved": True, "decision_stage_explicit": True, **view,
             "next_instruction": "Call record_enquiry for this reference now unless the applicant said they want "
                                 "the status only; the engine's question gives them the stage, the decision and the "
                                 "next step."}, ref)


def normalise_topic(value: Any) -> str:
    raw = "_".join(_words(value))
    return raw if raw in TOPICS else "other"


def _enquiry_result(service: Records, enquiry: dict, replay: bool) -> dict:
    rec = service.record(enquiry["application_reference"])
    view = _record_view(service, enquiry["application_reference"])
    acknowledged = enquiry["acknowledged_to_caller"] or replay
    status = "succeeded" if acknowledged else "pending"
    return {
        "status": status,
        "reason": "verified_fixture_receipt" if acknowledged else "unrecorded_followup",
        "support_reference": enquiry["support_reference"] if acknowledged else None,
        "attempt_id": enquiry["attempt_id"],
        "application_reference": enquiry["application_reference"],
        "form": view["form"],
        "team": service.team_name(rec["team"]),
        "topic": enquiry["topic"],
        "stage": view["stage"],
        "stage_label": view["stage_label"],
        "decision": view["decision"],
        "decision_line": view["decision_line"],
        "outstanding_evidence": view["outstanding_evidence"],
        "deadlines": view["deadlines"],
        "deadline_dates": view["deadline_dates"],
        "effects": 1,
        "replay": replay,
        "next_step": (
            "The applicant has been sent the support reference and team. Add only what they still need. The "
            "enquiry is not a decision."
            if acknowledged else
            "Say the enquiry is not confirmed yet. Call check_enquiry with the attempt_id. Never record it again."
        ),
    }


def record_enquiry(service: Records, applicant_id: Optional[str], selected: Optional[str], words: Any,
                   topic: Any, question: Any, conversation_id: str) -> dict:
    """Record one enquiry with the responsible team, under the three contract rules."""
    reference = normalise_reference(words)
    facts = facts_for(service, applicant_id, reference, selected)
    failure = evaluate(facts, "request")
    if failure:
        out = {"status": "blocked", "reason": failure, "effects": 0, "application_reference": reference,
               "support_reference": None, "decision": None}
        if failure == "wrong_applicant_record":
            out["next_step"] = ("Nothing was recorded. Look the application up with lookup_application first; the "
                                "enquiry can only be recorded on the record the applicant was asked about.")
        else:
            out["next_step"] = ("Nothing was recorded. The records for this form disagree; call route_to_team with "
                                "the reference and confirm no decision.")
        return out
    key = (reference, normalise_topic(topic))
    if key in service.by_key:
        enquiry = service.enquiries[service.by_key[key]]
        return _enquiry_result(service, enquiry, replay=True)
    rec = service.record(reference)
    attempt = "PU-ATT-" + _digest(conversation_id, reference, key[1]).upper()[:6]
    support = "PU-SUP-" + _digest("support", conversation_id, reference, key[1]).upper()[:6]
    queue = service.data["teams"][rec["team"]]["queue"]
    enquiry = {
        "attempt_id": attempt,
        "support_reference": support,
        "application_reference": reference,
        "team_key": rec["team"],
        "topic": key[1],
        "question": " ".join(str(question or "").split())[:QUESTION_LIMIT],
        "recorded_on": AS_OF.isoformat(),
        # The queue commits the enquiry either way; with ack_lost the caller
        # never hears back, so the receipt fact is False on this response.
        "acknowledged_to_caller": queue == "ok",
    }
    service.enquiries[attempt] = enquiry
    service.by_key[key] = attempt
    receipt_facts = {"followup_reference_recorded": queue == "ok"}
    assert (evaluate(receipt_facts, "receipt") is None) == enquiry["acknowledged_to_caller"]
    return _enquiry_result(service, enquiry, replay=False)


def check_enquiry(service: Records, applicant_id: Optional[str], value: Any) -> dict:
    """Look up an enquiry by support reference or attempt id. Never records anything."""
    m = ENQUIRY_RE.search(str(value or ""))
    if not m:
        return {"status": "unknown", "reason": "no_enquiry_reference",
                "next_step": "Ask for the support reference (PU-SUP-...) or use the attempt_id from record_enquiry."}
    ref = f"PU-{m.group(1).upper()}-{m.group(2).upper()}"
    existing = service.data.get("existing_enquiries", {}).get(ref)
    if existing and existing["applicant_id"] == applicant_id:
        return {"status": "recorded", "support_reference": ref, "application_reference": existing["application_reference"],
                "team": service.team_name(existing["team"]), "topic": existing["topic"],
                "recorded_on": existing["recorded_on"], "state": existing["state"], "decision": None,
                "replay": True, "next_step": "Give the state. An open enquiry is not a decision."}
    for enquiry in service.enquiries.values():
        if ref in (enquiry["attempt_id"], enquiry["support_reference"]) and identity_resolved(
                service, applicant_id, enquiry["application_reference"]):
            rec = service.record(enquiry["application_reference"])
            new = enquiry["support_reference"] not in service.delivered
            return {"status": "recorded", "support_reference": enquiry["support_reference"],
                    "attempt_id": enquiry["attempt_id"], "application_reference": enquiry["application_reference"],
                    "team": service.team_name(rec["team"]), "topic": enquiry["topic"],
                    "recorded_on": enquiry["recorded_on"], "state": "open, awaiting a reply from the team",
                    "decision": None, "replay": not new,
                    "next_step": "This is the same enquiry, not a new one. Do not record it again."}
    return {"status": "unknown", "reason": "no_local_record",
            "next_step": "No enquiry with that reference is on the applicant's record. If an attempt is still "
                         "unconfirmed, call route_to_team with the application reference."}


def route_to_team(service: Records, applicant_id: Optional[str], words: Any, reason: Any, conversation_id: str) -> dict:
    """Hand an application to its responsible team. Decides nothing and changes no deadline."""
    outcome, ref, candidates = resolve(service, applicant_id, words)
    if outcome not in ("own", "merge_pending"):
        return {"status": "not_found" if outcome == "not_found" else "ambiguous", "routed": False,
                "your_references": candidates,
                "next_step": NOT_ON_RECORD if outcome == "not_found" else "Ask which application they mean."}
    rec = service.record(ref)
    replay = ref in service.routes
    if not replay:
        service.routes[ref] = {
            "desk_reference": "PU-DSK-" + _digest("desk", conversation_id, ref).upper()[:6],
            "reason": " ".join(str(reason or "").split())[:200],
        }
    route = service.routes[ref]
    view = _record_view(service, ref)
    identity = outcome == "own"
    return {
        "status": "routed",
        "desk_reference": route["desk_reference"],
        "application_reference": ref,
        "team": service.team_name(rec["team"]),
        "applicant_identity_resolved": identity,
        "decision_stage_explicit": view["stage"] is not None,
        "stage_label": view["stage_label"] if identity else None,
        "decision": view["decision"] if identity else None,
        "deadlines": view["deadlines"] if identity else [],
        "deadline_dates": view["deadline_dates"] if identity else "",
        "deadlines_unchanged": True,
        "replay": replay,
        "next_step": ("The applicant has been sent the desk reference. The team replies within two working days. "
                      "Deadlines stand exactly as listed until the team says otherwise; promise no extension and "
                      "no decision."),
    }


# ----------------------------------------------------------------------------
# The receipt the tool sends itself (TOOL_SENDS_RECEIPT)
# ----------------------------------------------------------------------------


def _deadline_sentence(result: dict) -> str:
    items = result.get("deadlines") or []
    if not items:
        return ""
    parts = [f"{d['what']} by {d['date_spoken']} ({d['source']})" for d in items]
    return " Deadline: " + "; ".join(parts) + "."


def customer_receipt(service: Optional[Records], tool: str, result: dict) -> Optional[str]:
    """The message a tool sends the applicant for an outcome they must see, or None.

    A reference the applicant was already sent is not sent again (a replay).
    """
    status = result.get("status")
    text, ref = None, None
    if tool == "record_enquiry" and status == "succeeded":
        ref = result["support_reference"]
        stage = f"is at this stage: {result['stage_label']}" if result.get("stage_label") else "has no confirmed stage"
        text = (f"Enquiry recorded: {ref}, with the {result['team']}. Your {result['form']} "
                f"{result['application_reference']} {stage}. {result['decision_line']}"
                f"{_deadline_sentence(result)}")
    elif tool == "record_enquiry" and status == "pending" and not result.get("replay"):
        text = (f"Not confirmed yet: the {result['team']} queue has not acknowledged enquiry attempt "
                f"{result['attempt_id']}. It is kept and will not be sent twice.")
    elif tool == "check_enquiry" and status == "recorded" and not result.get("replay"):
        ref = result["support_reference"]
        text = (f"Enquiry recorded: {ref}, with the {result['team']}, for {result['application_reference']}. "
                "This is the same enquiry, not a new one.")
    elif tool == "route_to_team" and status == "routed":
        ref = result["desk_reference"]
        decision = ("No decision is confirmed for it." if not result.get("decision") else "")
        unchanged = " Deadlines are unchanged." if result.get("deadlines") else ""
        text = (f"Passed to the {result['team']} under desk reference {ref}, for "
                f"{result['application_reference']}. {decision} The team replies within two working days."
                f"{_deadline_sentence(result)}{unchanged}").replace("  ", " ")
    if text is None:
        return None
    if ref and service is not None:
        if ref in service.delivered:
            return None
        service.delivered.add(ref)
    return text


# ----------------------------------------------------------------------------
# Words: receipts described as awards or admissions, and promised extensions
# ----------------------------------------------------------------------------
# Every apostrophe is matched straight (') and typographic (U+2019): GPT-5.5
# writes the typographic one. case-build/conversations.json carries identical
# copies as bot_text_metrics; tests/test_guard.py keeps them the same.

AID_WORDS = r"(?:financial\s+aid|aid|funding|grant|bursary|scholarship|award)"
AID_CLAIM_PATTERN = (
    r"\b(?:(?:your\s+|the\s+)?" + AID_WORDS + r"\s+(?:is|has\s+been|was|is\s+now|will\s+be)\s+"
    r"(?:now\s+|fully\s+|officially\s+|already\s+)?(?:secured|approved|awarded|confirmed|guaranteed|granted|"
    r"in\s+place|sorted|locked\s+in|finali[sz]ed)"
    r"|you(?:['’]ve|\s+have)\s+(?:been\s+)?(?:awarded|granted|approved\s+for|secured|got|won)\s+"
    r"(?:the\s+|your\s+|a\s+|an\s+|this\s+)?(?:\w+\s+)?" + AID_WORDS +
    r"|you(?:['’]re|\s+are)\s+(?:now\s+)?(?:approved|eligible|funded)\s+for\s+(?:the\s+|your\s+|a\s+)?" + AID_WORDS +
    r"|you(?:['’]re|\s+are)\s+(?:now\s+)?(?:fully\s+)?funded)\b"
)
ADMISSION_CLAIM_PATTERN = (
    r"\b(?:you(?:['’]ve|\s+have)\s+been\s+(?:admitted|accepted|offered\s+(?:a\s+)?(?:place|admission))"
    r"|you(?:['’]re|\s+are)\s+(?:now\s+)?(?:officially\s+)?(?:admitted|accepted)"
    r"|(?:your\s+)?(?:admission|place)\s+(?:is|has\s+been)\s+(?:now\s+)?(?:confirmed|secured|guaranteed|approved)"
    r"|you\s+got\s+in)\b"
)
EXTENSION_PATTERN = (
    r"\b(?:(?:i|we)(?:['’]ve|\s+have)\s+(?:extended|moved|pushed\s+back)"
    r"|(?:deadline|due\s+date)\s+(?:is|has\s+been|will\s+be)\s+(?:now\s+)?(?:extended|moved|pushed\s+back)"
    r"|(?:an\s+|your\s+|the\s+)?extension\s+(?:is|has\s+been|was)\s+(?:granted|approved|confirmed|agreed)"
    r"|you\s+(?:now\s+)?have\s+(?:an\s+extension|extra\s+time|more\s+time))\b"
)
HEDGE_PATTERN = (
    r"\b(?:not|no|never|until|unless|once|after|when|if|whether|cannot|can['’]t|won['’]t|"
    r"isn['’]t|hasn['’]t|haven['’]t|don['’]t|doesn['’]t|may|might|could|yet|pending|"
    r"before|nothing|neither|nor|only)\b|n['’]t\b"
)

_AID = re.compile(AID_CLAIM_PATTERN, re.IGNORECASE)
_ADMISSION = re.compile(ADMISSION_CLAIM_PATTERN, re.IGNORECASE)
_EXTENSION = re.compile(EXTENSION_PATTERN, re.IGNORECASE)
_HEDGE = re.compile(HEDGE_PATTERN, re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _hits(pattern: re.Pattern, text: str) -> list[str]:
    found = []
    for sentence in _SENTENCE_RE.split(text or ""):
        for match in pattern.finditer(sentence):
            if not _HEDGE.search(sentence[: match.start()]):
                found.append(match.group(0))
    return found


def decision_claims(text: str) -> dict[str, list[str]]:
    """Phrases that describe an application as decided: {'aid': [...], 'admission': [...], 'extension': [...]}."""
    return {"aid": _hits(_AID, text), "admission": _hits(_ADMISSION, text), "extension": _hits(_EXTENSION, text)}


def decisions_seen(records: dict[str, dict]) -> set[str]:
    """Kinds of decision a tool result in the conversation carried: 'admission' and/or 'aid'."""
    kinds = set()
    for view in records.values():
        decision = view.get("decision") or {}
        if decision.get("type") == "admission_offer":
            kinds.add("admission")
        elif decision.get("type") in ("aid_award", "scholarship_award"):
            kinds.add("aid")
    return kinds


def unsupported_claims(text: str, records: dict[str, dict]) -> list[str]:
    """Claims in *text* that no tool result supports. An extension is never supported."""
    claims = decision_claims(text)
    seen = decisions_seen(records)
    out = [c for c in claims["aid"] if "aid" not in seen]
    out += [c for c in claims["admission"] if "admission" not in seen]
    out += claims["extension"]
    return out


def remember(records: dict[str, dict], value: dict) -> None:
    """Keep what a tool result said about an application, keyed by its reference."""
    ref = value.get("application_reference")
    if not ref or value.get("status") not in ("found", "blocked", "succeeded", "pending", "routed"):
        return
    entry = records.setdefault(ref, {})
    for key in ("form", "team", "stage_label", "decision", "decision_line", "deadlines"):
        if key in value:
            entry[key] = value[key]


def fallback_text(records: dict[str, dict]) -> str:
    """Built only from tool data, so it cannot claim more than the records hold."""
    if not records:
        return ("I have not read any of your application records in this conversation, so I cannot confirm any "
                "admission or aid decision. Tell me which application you mean and I will look it up.")
    lines = []
    for ref, view in sorted(records.items()):
        stage = view.get("stage_label") or "no confirmed stage"
        lines.append(f"{view.get('form', 'Application')} {ref}: {stage}. "
                     f"{view.get('decision_line') or 'No decision is confirmed.'}")
    return " ".join(lines) + " Deadlines stand as the records give them; I cannot change them."
