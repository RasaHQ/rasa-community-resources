"""HarborCover claim intake and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three rules of the casebook contract for ``insurance-file-claim``
(vendored as ``lib/fixtures/case-contract.json``):

- ``report_confirmed`` (request): the draft being submitted is the one the
  engine read back to the customer, unchanged since. Every change to a draft
  (a corrected date, a new file, a file left out) gives it a new version, and
  the version tag (``HC-FD-XXXXX v2``) is part of the confirmation question.
  The submit tool checks that the latest confirmation question the engine sent
  carries the current tag and that the customer answered it.
- ``required_attachment_state_known`` (request): every attachment the loss type
  requires is known to be received, failed or not provided. A file the
  attachment service is still scanning is unknown, and blocks submission.
  The state comes from the attachment service, never from the model or from
  the customer saying "I sent it".
- ``submission_acknowledged`` (receipt): after the report is submitted, the
  claims system's acknowledgment is read back by draft id. When it cannot be,
  the result is ``pending`` with the draft id, never ``succeeded``, and
  ``check_claim_submission`` reconciles the same submission instead of filing
  again.

A receipt is a claim-intake reference listing the material received and any
follow-up still required. ``coverage_decision`` is always ``None``: intake
records a loss, it does not decide one.

Facts are computed from trusted data: the session's customer id, the
attachment service and the conversation's own events. The model supplies a
policy number, a loss type, a date, the customer's account of the loss, file
names to leave out, a reference and a reason. It never supplies a fact, a
customer id, an attachment state or an outcome. A fact that is not exactly
``True`` fails its rule, as in the lab's ``evaluate``.

The organisation guard runs at import and is an allowlist: the fixture's
organisation must be the casebook contract's own fictional insurer, marked
fictional, and so must every other organisation field in the fixture.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "harborcover_claims.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (rasa/mantle/prompts/memory_lines.py,
# MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5). Every value a tool writes to memory
# is one short field and must fit; tests/test_guard.py checks every fixture.
MEMORY_VALUE_LIMIT = 100
# The customer's one-line account of the loss is read back in the confirmation
# question from memory, so the tool refuses a longer one instead of letting
# Mantle cut it.
LOSS_SUMMARY_LIMIT = 80

# The engine's confirmation question for submit_claim_report
# (skills/file_claim/responses.yml). Mantle stamps the response name on the
# BotUttered event under this metadata key (turn_context.UTTER_ACTION_METADATA_KEY).
CONFIRM_UTTER = "utter_confirm_claim_report"
UTTER_ACTION_KEY = "utter_action"

# Design fix for the silent complete_skill (see README): the tools send the
# claim reference to the customer themselves through ToolContext.send, so the
# receipt reaches the customer whatever the model does next. The
# `receipt-in-result-only` variant sets this to False.
TOOL_SENDS_RECEIPT = True

# Web chat carries no files, so the scripted conversations mark an attachment
# the way a chat widget would describe it: "[attached: a.jpg, b.pdf]". On
# Microsoft Teams, Rasa's botframework channel puts the activity's attachments
# in the user message metadata under "attachments"; both are read.
ATTACH_MARKER_RE = re.compile(r"\[attached:\s*([^\]]+)\]", re.IGNORECASE)

# Organisation fields the allowlist checks, wherever they appear in the fixture.
ORGANISATION_KEYS = ("organisation", "insurer", "carrier", "administrator", "vendor", "company")


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
SESSION_CUSTOMER_ID = _DATA["session_customer_id"]
OWNER = _CONTRACT["owner"]

# Wording that says a claim has been filed. case-build/case_metric.py counts it
# in bot text for the case metric (drafts described as filed without an
# acknowledgment); tests/test_guard.py keeps this copy and the spec's identical.
FILED_CLAIM_PATTERN = (
    r"\b(?:(?:claim|report)\s+(?:has\s+been|have\s+been|is|was|is\s+now|now)\s+"
    r"(?:officially\s+|successfully\s+)?(?:filed|submitted|lodged|registered|on\s+file)"
    r"|claim\s+filed"
    r"|(?:i|we)(?:'ve|\s+have)\s+(?:now\s+|successfully\s+)?(?:filed|submitted|lodged)\s+(?:your|the|this)\s+(?:claim|report)"
    r"|(?:your|the)\s+claim\s+(?:reference|number)\s+is)"
)
FILED_HEDGE_PATTERN = (
    r"\b(?:not|no|never|cannot|can't|won't|isn't|hasn't|haven't|wasn't|don't|until|unless|if|"
    r"whether|once|when|before|after|yet|pending)\b|n't\b"
)


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


def spoken_date(value: date) -> str:
    return f"{value.day} {value.strftime('%B')} {value.year}"


# ----------------------------------------------------------------------------
# The conversation, as the tools see it
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class UserMessage:
    text: str
    attachments: tuple[str, ...] = ()


@dataclass(frozen=True)
class Conversation:
    """What the tools read from the tracker: the customer's messages and the last confirmation question."""

    user_messages: tuple[UserMessage, ...] = ()
    # Text of the latest bot message stamped with CONFIRM_UTTER, and whether a
    # customer message came after it.
    confirmation_question: Optional[str] = None
    confirmation_answered: bool = False


def attachments_in(text: str, metadata: Optional[dict] = None) -> tuple[str, ...]:
    """File names a customer message carries: text markers, then channel metadata."""
    names: list[str] = []
    for block in ATTACH_MARKER_RE.findall(text or ""):
        names.extend(n.strip() for n in block.split(",") if n.strip())
    for item in (metadata or {}).get("attachments") or []:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]).strip())
    return tuple(dict.fromkeys(names))


def attached_files(conversation: Conversation) -> dict[str, int]:
    """File name -> index of the customer message that attached it (first time)."""
    out: dict[str, int] = {}
    for index, message in enumerate(conversation.user_messages):
        for name in message.attachments:
            out.setdefault(name.lower(), index)
    return out


# ----------------------------------------------------------------------------
# The claims intake service: the fixture copy for one conversation
# ----------------------------------------------------------------------------


@dataclass
class Draft:
    draft_id: str
    customer_id: str
    policy_number: str
    loss_type: str
    loss_date: date
    loss_summary: str
    loss_details: str
    loss_location: str
    version: int = 1
    excluded: set = field(default_factory=set)
    material: Optional[dict] = None

    @property
    def tag(self) -> str:
        return f"{self.draft_id} v{self.version}"


class ClaimsIntake:
    """Policies, drafts, the attachment service and the claims system for one conversation."""

    def __init__(self, data: Optional[dict] = None) -> None:
        self.data = data or load_data()
        self.as_of = datetime.fromisoformat(self.data["as_of"])
        self.drafts: dict[str, Draft] = {}
        # draft_id -> submission record, as the claims system stores it.
        self.submissions: dict[str, dict] = {}

    def policy(self, number: str) -> Optional[dict]:
        return self.data["policies"].get(number)

    def own_policies(self, customer_id: Optional[str]) -> dict[str, dict]:
        return {n: p for n, p in self.data["policies"].items() if customer_id and p["customer_id"] == customer_id}

    def requirement_label(self, key: str) -> str:
        return self.data["requirements"][key]

    def loss_label(self, key: str) -> str:
        return self.data["loss_types"][key]["label"]


_SERVICES: dict[str, ClaimsIntake] = {}


def service_for(conversation_id: str) -> ClaimsIntake:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = ClaimsIntake()
    return _SERVICES[conversation_id]


def session_profile(customer_id: str = SESSION_CUSTOMER_ID, data: Optional[dict] = None) -> dict:
    data = data or _DATA
    person = data["customers"][customer_id]
    policies = sorted((n, p) for n, p in data["policies"].items() if p["customer_id"] == customer_id)
    return {
        "customer_id": customer_id,
        "first_name": person["first_name"],
        "policies": [{"policy_number": n, "line": p["line"], "insured": p["insured"]} for n, p in policies],
        "policy_list": "; ".join(f"{n} {p['line']}" for n, p in policies),
    }


# ----------------------------------------------------------------------------
# Normalising what the model passes on
# ----------------------------------------------------------------------------


def resolve_policy(service: ClaimsIntake, customer_id: Optional[str], value: Any) -> Optional[str]:
    """'HC-HO-552104', '552104', 'hc ho 552104' -> the customer's own policy number, else None."""
    digits = re.sub(r"\D", "", str(value or ""))
    cleaned = re.sub(r"[^A-Z0-9-]", "", str(value or "").upper())
    for number in service.own_policies(customer_id):
        if cleaned == number or (len(digits) == 6 and re.sub(r"\D", "", number) == digits):
            return number
    return None


def resolve_loss_type(service: ClaimsIntake, value: Any, line: str) -> tuple[Optional[str], list[str]]:
    """(loss type key, candidates). The key is None when the words match no type, or several."""
    types = {k: t for k, t in service.data["loss_types"].items() if line in t["lines"]}
    raw = str(value or "").strip().lower().replace(" ", "_")
    if raw in types:
        return raw, [raw]
    words = _words(value)
    hits = [k for k, t in types.items() if _has_phrase(words, t["label"]) or any(_has_phrase(words, a) for a in t["aliases"])]
    if len(hits) == 1:
        return hits[0], hits
    return None, hits or sorted(types)


_DATE_FORMATS = ("%Y-%m-%d", "%d %B %Y", "%B %d %Y", "%d %b %Y", "%b %d %Y", "%d/%m/%Y")


def parse_loss_date(value: Any, today: date) -> Optional[date]:
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", str(value or "").strip()).replace(",", "")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    for fmt in ("%d %B", "%B %d", "%d %b", "%b %d"):
        # No year given: the fixture clock's year.
        try:
            return datetime.strptime(f"{text} {today.year}", f"{fmt} %Y").date()
        except ValueError:
            continue
    return None


# ----------------------------------------------------------------------------
# Attachments: what the attachment service says about each file
# ----------------------------------------------------------------------------


def file_state(service: ClaimsIntake, name: str, attached_at: int, conversation: Conversation) -> dict:
    """The attachment service's state for one file the customer attached.

    ``states`` advances with each customer message after the one that attached
    the file (a virus scan finishing between messages). A name the service has
    no record of was never received.
    """
    upload = next((u for n, u in service.data["uploads"].items() if n.lower() == name.lower()), None)
    if upload is None:
        return {"file": name, "state": "not_received", "satisfies": None,
                "detail": "the attachment service has no file with this name"}
    later = len(conversation.user_messages) - 1 - attached_at
    states = upload["states"]
    state = states[min(max(later, 0), len(states) - 1)]
    out = {"file": name, "state": state, "satisfies": upload["satisfies"]}
    if state != "received" and upload.get("detail"):
        out["detail"] = upload["detail"]
    return out


_FOLLOW_UP_WHY = {"failed": "upload failed", "not_received": "not received", "not_provided": "not provided"}


def material(service: ClaimsIntake, draft: Draft, conversation: Conversation) -> dict:
    """Per required item: received, failed, not provided or unknown, from the attachment service."""
    loss = service.data["loss_types"][draft.loss_type]
    files = [file_state(service, name, index, conversation)
             for name, index in attached_files(conversation).items() if name not in draft.excluded]
    required = []
    for key in loss["required"]:
        mine = [f for f in files if f["satisfies"] == key]
        states = {f["state"] for f in mine}
        if "received" in states:
            state = "received"
        elif "processing" in states:
            state = "unknown"
        elif "failed" in states:
            state = "failed"
        else:
            state = "not_provided"
        required.append({"requirement": service.requirement_label(key), "key": key, "state": state,
                         "files": [f["file"] for f in mine if f["state"] == "received"]})
    return {
        "required": required,
        "files": files,
        "excluded": sorted(draft.excluded),
        "required_attachment_state_known": all(r["state"] != "unknown" for r in required),
    }


def material_received(mat: dict) -> list[dict]:
    return [{"requirement": r["requirement"], "files": r["files"]} for r in mat["required"] if r["state"] == "received"]


def follow_up_required(mat: dict) -> list[dict]:
    return [{"requirement": r["requirement"], "why": _FOLLOW_UP_WHY[r["state"]]}
            for r in mat["required"] if r["state"] in _FOLLOW_UP_WHY]


def received_line(mat: dict) -> str:
    parts = []
    for r in material_received(mat):
        n = len(r["files"])
        parts.append(f"{r['requirement']} ({n} file{'s' if n != 1 else ''})")
    return ", ".join(parts) or "nothing yet"


def follow_up_line(mat: dict) -> str:
    parts = [f"{f['requirement']} ({f['why']})" for f in follow_up_required(mat)]
    parts += [f"{r['requirement']} (still scanning)" for r in mat["required"] if r["state"] == "unknown"]
    return ", ".join(parts) or "nothing"


# ----------------------------------------------------------------------------
# Drafts
# ----------------------------------------------------------------------------


def report_summary(service: ClaimsIntake, draft: Draft) -> str:
    return f"{service.loss_label(draft.loss_type)} on {spoken_date(draft.loss_date)}, {service.policy(draft.policy_number)['label']}"


def memory_values(service: ClaimsIntake, draft: Optional[Draft]) -> dict:
    """What the draft tools write to skill memory. Each value is one short field."""
    if draft is None:
        return {key: "" for key in MEMORY_KEYS}
    mat = draft.material or {"required": [], "required_attachment_state_known": False}
    return {
        "claim_draft_id": draft.draft_id,
        "claim_draft_tag": draft.tag,
        "claim_report_summary": report_summary(service, draft),
        "claim_loss_summary": draft.loss_summary,
        "claim_material_received": received_line(mat),
        "claim_material_followup": follow_up_line(mat),
        # Read by the engine gate on submit_claim_report (`requires` in skill.md):
        # the tool is not offered to the model until every required attachment
        # state is known.
        "claim_ready_to_submit": "yes" if mat["required_attachment_state_known"] else "",
    }


MEMORY_KEYS = ("claim_draft_id", "claim_draft_tag", "claim_report_summary", "claim_loss_summary",
               "claim_material_received", "claim_material_followup", "claim_ready_to_submit")


def _draft_view(service: ClaimsIntake, draft: Draft) -> dict:
    mat = draft.material
    return {
        "draft_id": draft.draft_id,
        "draft_version": draft.version,
        "draft_tag": draft.tag,
        "policy_number": draft.policy_number,
        "loss_type": service.loss_label(draft.loss_type),
        "loss_date": draft.loss_date.isoformat(),
        "loss_summary": draft.loss_summary,
        "loss_location": draft.loss_location,
        "material_received": material_received(mat),
        "follow_up_required": follow_up_required(mat),
        "still_scanning": [r["requirement"] for r in mat["required"] if r["state"] == "unknown"],
        "files": mat["files"],
        "required_attachment_state_known": mat["required_attachment_state_known"],
        "filed": False,
    }


def _refresh(service: ClaimsIntake, draft: Draft, conversation: Conversation) -> bool:
    """Recompute the draft's material; a change is a new draft version. Returns whether it changed."""
    fresh = material(service, draft, conversation)
    changed = draft.material is not None and fresh != draft.material
    if changed:
        draft.version += 1
    draft.material = fresh
    return changed


def _validate_fields(service: ClaimsIntake, line: str, loss_type: Any, loss_date: Any, loss_summary: Any) -> tuple[Optional[dict], dict]:
    """(blocked result or None, normalised fields)."""
    fields: dict[str, Any] = {}
    if loss_type is not None:
        key, candidates = resolve_loss_type(service, loss_type, line)
        if key is None:
            return {"status": "blocked", "reason": "loss_type_not_identified",
                    "loss_types_for_this_policy": [service.loss_label(k) for k in candidates],
                    "next_step": "Ask the customer what happened, naming these types. Do not pick one."}, fields
        fields["loss_type"] = key
    if loss_date is not None:
        parsed = parse_loss_date(loss_date, service.as_of.date())
        if parsed is None:
            return {"status": "blocked", "reason": "loss_date_not_understood", "loss_date_given": str(loss_date)[:40],
                    "next_step": "Ask the customer for the date of loss as a calendar date."}, fields
        if parsed > service.as_of.date():
            return {"status": "blocked", "reason": "loss_date_in_future", "loss_date_given": parsed.isoformat(),
                    "today": service.as_of.date().isoformat(),
                    "next_step": "A loss cannot be reported for a future date. Ask the customer to check the date."}, fields
        fields["loss_date"] = parsed
    if loss_summary is not None:
        summary = " ".join(str(loss_summary).split())
        if not summary:
            return {"status": "blocked", "reason": "loss_summary_missing",
                    "next_step": "Ask the customer what happened."}, fields
        if len(summary) > LOSS_SUMMARY_LIMIT:
            return {"status": "blocked", "reason": "loss_summary_too_long", "limit": LOSS_SUMMARY_LIMIT,
                    "length": len(summary),
                    "next_step": (f"Call again with a loss_summary of at most {LOSS_SUMMARY_LIMIT} characters in the "
                                  "customer's own words; put the rest in loss_details.")}, fields
        fields["loss_summary"] = summary
    return None, fields


def start_claim_draft(service: ClaimsIntake, customer_id: Optional[str], conversation_id: str, conversation: Conversation,
                      policy_number: Any, loss_type: Any, loss_date: Any, loss_summary: Any,
                      loss_details: Any = None, loss_location: Any = None) -> tuple[dict, Optional[Draft]]:
    """Open a draft report on one of the customer's own policies. A draft is not a claim."""
    if not customer_id:
        return {"status": "not_found", "reason": "no_signed_in_customer",
                "next_step": "Say the account could not be loaded and offer the claims intake team."}, None
    number = resolve_policy(service, customer_id, policy_number)
    if number is None:
        # Someone else's policy and a policy that does not exist get the same answer.
        return {"status": "not_found", "reason": "no_such_policy_on_account",
                "policy_number_given": str(policy_number or "")[:30],
                "policies_on_account": sorted(service.own_policies(customer_id)),
                "next_step": ("Say there is no policy with that number on this account and ask the customer to "
                              "check it. Never say whether it belongs to someone else.")}, None
    line = service.policy(number)["line"]
    blocked, fields = _validate_fields(service, line, loss_type, loss_date, loss_summary)
    if blocked:
        return {**blocked, "policy_number": number}, None
    missing = [k for k in ("loss_type", "loss_date", "loss_summary") if k not in fields]
    if missing:
        return {"status": "blocked", "reason": "report_incomplete", "missing": missing, "policy_number": number,
                "next_step": "Ask the customer for the missing details, then call start_claim_draft again."}, None
    draft_id = "HC-FD-" + _digest(conversation_id, number, len(service.drafts)).upper()[:5]
    draft = Draft(draft_id=draft_id, customer_id=customer_id, policy_number=number,
                  loss_type=fields["loss_type"], loss_date=fields["loss_date"], loss_summary=fields["loss_summary"],
                  loss_details=" ".join(str(loss_details or "").split())[:1000],
                  loss_location=" ".join(str(loss_location or "").split())[:120] or service.policy(number)["insured"])
    _refresh(service, draft, conversation)
    service.drafts[draft_id] = draft
    view = _draft_view(service, draft)
    return {"status": "drafted", **view, "next_step": _draft_next_step(view)}, draft


def _draft_next_step(view: dict) -> str:
    if not view["required_attachment_state_known"]:
        return ("A required file is still being scanned, so its state is unknown and the report cannot be submitted "
                "yet. Tell the customer which item is still scanning. Offer to check again after their next message, "
                "or to leave that file out (check_attachments with exclude) so the item is listed as still needed.")
    return ("This is a draft, not a filed claim. Tell the customer what was received and what is still needed, "
            "naming any failed upload. When they want to submit, call submit_claim_report with this draft_id; the "
            "engine reads the report back and asks them to confirm.")


def _own_draft(service: ClaimsIntake, customer_id: Optional[str], draft_id: Any) -> Optional[Draft]:
    draft = service.drafts.get(str(draft_id or "").strip().upper())
    return draft if draft is not None and customer_id and draft.customer_id == customer_id else None


def _no_draft(draft_id: Any) -> dict:
    return {"status": "not_found", "reason": "no_such_draft", "draft_id_given": str(draft_id or "")[:30],
            "next_step": "No draft exists under that id in this chat. Start one with start_claim_draft."}


def update_claim_draft(service: ClaimsIntake, customer_id: Optional[str], conversation: Conversation, draft_id: Any,
                       loss_date: Any = None, loss_type: Any = None, loss_summary: Any = None,
                       loss_details: Any = None, loss_location: Any = None) -> tuple[dict, Optional[Draft]]:
    """Change a draft that has not been submitted. Any change is a new version to confirm."""
    draft = _own_draft(service, customer_id, draft_id)
    if draft is None:
        return _no_draft(draft_id), None
    if draft.draft_id in service.submissions:
        return {"status": "blocked", "reason": "already_submitted", "draft_id": draft.draft_id,
                "next_step": ("This report was already submitted and cannot be changed here. Call "
                              "check_claim_submission with the draft_id, and route_claims_intake for a correction.")}, draft
    line = service.policy(draft.policy_number)["line"]
    blocked, fields = _validate_fields(service, line, loss_type, loss_date, loss_summary)
    if blocked:
        return {**blocked, "draft_id": draft.draft_id}, draft
    if loss_details is not None:
        fields["loss_details"] = " ".join(str(loss_details).split())[:1000]
    if loss_location is not None:
        fields["loss_location"] = " ".join(str(loss_location).split())[:120]
    changed = [k for k, v in fields.items() if getattr(draft, k) != v]
    for key in changed:
        setattr(draft, key, fields[key])
    material_changed = _refresh(service, draft, conversation)
    if changed and not material_changed:
        draft.version += 1
    view = _draft_view(service, draft)
    return {"status": "updated" if changed else "unchanged", "changed": changed, **view,
            "next_step": ("The draft changed, so the customer must confirm it again. Tell them what changed and "
                          "call submit_claim_report when they want to submit; the engine reads the new version back."
                          if changed else _draft_next_step(view))}, draft


def check_attachments(service: ClaimsIntake, customer_id: Optional[str], conversation: Conversation, draft_id: Any,
                      exclude: Optional[Iterable[str]] = None) -> tuple[dict, Optional[Draft]]:
    """Link the files the customer attached in this chat and read each one's state from the attachment service."""
    draft = _own_draft(service, customer_id, draft_id)
    if draft is None:
        return _no_draft(draft_id), None
    if draft.draft_id in service.submissions:
        return {"status": "blocked", "reason": "already_submitted", "draft_id": draft.draft_id,
                "next_step": "The report was already submitted. Call check_claim_submission with the draft_id."}, draft
    names = {n.lower() for n in attached_files(conversation)}
    for name in exclude or ():
        key = str(name or "").strip().lower()
        if key in names:
            draft.excluded.add(key)
    _refresh(service, draft, conversation)
    view = _draft_view(service, draft)
    return {"status": "checked", **view, "next_step": _draft_next_step(view)}, draft


# ----------------------------------------------------------------------------
# Submission and the receipt
# ----------------------------------------------------------------------------


def claim_reference(draft_id: str) -> str:
    return f"HC-CLI-{int(_digest(draft_id, 'claim'), 16) % 90000 + 10000:05d}"


def report_confirmed(service: ClaimsIntake, draft: Draft, memory: dict, conversation: Conversation,
                     fresh_material: dict) -> bool:
    """The engine read back this exact version and the customer answered it."""
    return (
        memory.get("claim_draft_id") == draft.draft_id
        and memory.get("claim_draft_tag") == draft.tag
        and fresh_material == draft.material
        and conversation.confirmation_question is not None
        and draft.tag in conversation.confirmation_question
        and conversation.confirmation_answered
    )


def submit_claim_report(service: ClaimsIntake, customer_id: Optional[str], memory: dict, conversation: Conversation,
                        draft_id: Any) -> dict:
    """Submit one confirmed draft to the claims system and prove it by reading the acknowledgment back."""
    wanted = str(draft_id or "").strip().upper()
    if wanted in service.submissions:
        # The same draft again: a replay of the stored result, never a second claim.
        return receipt(service, service.submissions[wanted], replay=True)
    draft = _own_draft(service, customer_id, wanted)
    if draft is None:
        return {"status": "blocked", "reason": "unconfirmed_report", "draft_id_given": wanted[:30], "effects": 0,
                "facts": {"report_confirmed": False},
                "next_step": "There is no draft with that id in this chat. Nothing was submitted."}
    fresh = material(service, draft, conversation)
    facts = {
        "report_confirmed": report_confirmed(service, draft, memory, conversation, fresh),
        "required_attachment_state_known": fresh["required_attachment_state_known"],
    }
    reason = evaluate(facts, "request")
    if reason:
        return {
            "status": "blocked", "reason": reason, "draft_id": draft.draft_id, "draft_tag": draft.tag,
            "facts": facts, "effects": 0, "filed": False,
            "still_scanning": [r["requirement"] for r in fresh["required"] if r["state"] == "unknown"],
            "next_step": (
                "Nothing was submitted. The engine has not read this version of the report back to the customer. "
                "Call check_attachments for the draft, then submit_claim_report again so the engine asks them."
                if reason == "unconfirmed_report" else
                "Nothing was submitted. A required file is still being scanned. Tell the customer, and offer to check "
                "again after their next message or to leave the file out so it is listed as still needed."
            ),
        }
    policy = service.policy(draft.policy_number)
    mode = policy["intake_service"]
    record = {
        "draft_id": draft.draft_id,
        "draft_tag": draft.tag,
        "customer_id": customer_id,
        "policy_number": draft.policy_number,
        "loss_type": draft.loss_type,
        "loss_date": draft.loss_date.isoformat(),
        "loss_summary": draft.loss_summary,
        "material": draft.material,
        "claim_intake_reference": claim_reference(draft.draft_id),
        # ack_lost: the claims system records it but its acknowledgment never
        # arrives; unavailable: nothing can be confirmed either way.
        "read_back": "ok" if mode == "ok" else "failed",
        "lookup": {"ok": "ok", "ack_lost": "ok", "unavailable": "unknown"}[mode],
        "facts": facts,
    }
    service.submissions[draft.draft_id] = record
    return receipt(service, record, replay=False)


def receipt(service: ClaimsIntake, record: dict, *, replay: bool, acknowledged: Optional[bool] = None) -> dict:
    ack = record["read_back"] == "ok" if acknowledged is None else acknowledged
    facts = dict(record["facts"], submission_acknowledged=ack)
    failure = evaluate(facts, "receipt")
    mat = record["material"]
    result: dict[str, Any] = {
        "status": "pending" if failure else "succeeded",
        "reason": failure or "verified_fixture_receipt",
        "draft_id": record["draft_id"],
        "claim_intake_reference": None if failure else record["claim_intake_reference"],
        "policy_number": record["policy_number"],
        "loss_type": service.loss_label(record["loss_type"]),
        "loss_date": record["loss_date"],
        "loss_summary": record["loss_summary"],
        "material_received": material_received(mat),
        "follow_up_required": follow_up_required(mat),
        "coverage_decision": None,
        "filed": not failure,
        "draft_status": "retained_pending" if failure else "submitted",
        "effects": 0 if replay else 1,
        "replay": replay,
        "facts": facts,
    }
    if failure:
        result["next_step"] = (
            "The claims system did not acknowledge the submission, so the claim is not filed. Say so, call "
            "check_claim_submission with this draft_id, and if it is still unknown call route_claims_intake. "
            "Do not submit again."
        )
    else:
        result["next_step"] = (
            "Give the claim-intake reference, the material received and what is still needed. Coverage has not "
            "been decided; a claims handler reviews the claim next."
            + (" This is the same claim as before; nothing was filed twice." if replay else "")
        )
    return result


def check_claim_submission(service: ClaimsIntake, customer_id: Optional[str], reference: Any) -> dict:
    """Look a submission up by draft id or claim-intake reference. Never submits anything."""
    text = str(reference or "").strip().upper()
    for draft_id, record in service.submissions.items():
        if text in (draft_id, record["claim_intake_reference"]) and record["customer_id"] == customer_id:
            if record["lookup"] != "ok":
                return {"status": "unknown", "reason": "claims_system_unavailable", "draft_id": draft_id,
                        "filed": False, "draft_status": "retained_pending",
                        "next_step": ("The claims system cannot say whether this report was filed. Call "
                                      "route_claims_intake with this draft_id and say the claim is not confirmed. "
                                      "Do not submit again.")}
            found = receipt(service, record, replay=True, acknowledged=True)
            found.update(status="acknowledged", reason="found_by_draft_id")
            found["next_step"] = ("The claims system has the submission; this is the same claim, not a new one. "
                                  "Give the claim-intake reference, the material received and what is still needed.")
            return found
    draft = _own_draft(service, customer_id, text)
    if draft is not None:
        return {"status": "not_submitted", "reason": "draft_only", "draft_id": draft.draft_id, "filed": False,
                "next_step": "This is a draft that has not been submitted. It is not a claim."}
    existing = service.data["existing_claims"].get(text)
    if existing and existing["customer_id"] == customer_id:
        return {"status": "filed", "reason": "existing_claim", "claim_intake_reference": text,
                "policy_number": existing["policy_number"], "loss_type": service.loss_label(existing["loss_type"]),
                "loss_date": existing["loss_date"], "filed_on": existing["filed_on"],
                "loss_summary": existing["loss_summary"], "material_received": existing["material_received"],
                "follow_up_required": existing["follow_up_required"], "stage": existing["stage"],
                "coverage_decision": None,
                "next_step": "Give the stage, what was received and what is still needed. Coverage is not decided."}
    return {"status": "not_found", "reason": "no_claim_for_reference", "reference": text[:40],
            "next_step": "No claim or draft is known under that reference on this account. Ask the customer to check it."}


def route_claims_intake(service: ClaimsIntake, customer_id: Optional[str], reference: Any, reason: Any) -> dict:
    """Hand a draft or claim to the claims intake owner. Decides nothing and files nothing."""
    text = str(reference or "").strip().upper()
    draft = _own_draft(service, customer_id, text)
    record = service.submissions.get(draft.draft_id) if draft else None
    existing = service.data["existing_claims"].get(text)
    if draft is None and not (existing and existing["customer_id"] == customer_id):
        return {"status": "refused", "reason": "not_this_customers_reference", "reference": text[:40],
                "next_step": "Route only a draft or claim on this customer's account."}
    return {
        "status": "routed",
        "desk_reference": f"HC-CIQ-{_digest(customer_id, text, 'desk').upper()[:6]}",
        "reference": text,
        "owner": OWNER,
        "draft_status": "retained_pending" if draft is not None else None,
        "submission_state": ("unconfirmed" if record else "not_submitted") if draft is not None else "filed",
        "reason": " ".join(str(reason or "").split())[:200],
        "filed": False if draft is not None else None,
        "coverage_decision": None,
        "next_step": ("Give the desk reference. Say the claims intake team replies within one business day, the "
                      "draft is kept, and the claim is not confirmed as filed."
                      if draft is not None else
                      "Give the desk reference and say the claims intake team replies within one business day."),
    }


# ----------------------------------------------------------------------------
# The receipt the tool sends itself (TOOL_SENDS_RECEIPT)
# ----------------------------------------------------------------------------


def _material_sentence(result: dict) -> str:
    received = ", ".join(r["requirement"] for r in result.get("material_received") or []) or "no files"
    follow = ", ".join(f"{f['requirement']} ({f['why']})" for f in result.get("follow_up_required") or [])
    return f"Received: {received}. Still needed: {follow or 'nothing'}."


def customer_receipt(tool: str, result: dict) -> Optional[str]:
    """The message a tool sends the customer for an outcome they must see, or None."""
    status = result.get("status")
    if tool == "submit_claim_report" and status == "succeeded":
        again = " It was already filed; nothing was filed twice." if result.get("replay") else ""
        return (f"Claim filed: {result['claim_intake_reference']}, for {result['loss_type']} on "
                f"{result['loss_date']} under policy {result['policy_number']}.{again} {_material_sentence(result)} "
                "Coverage has not been decided; a claims handler reviews the claim next.")
    if tool == "submit_claim_report" and status == "pending":
        return (f"Not filed yet: the claims system has not acknowledged draft {result['draft_id']}. The draft is "
                "kept and will not be submitted twice.")
    if tool == "check_claim_submission" and status == "acknowledged":
        return (f"Claim filed: {result['claim_intake_reference']}. The claims system has acknowledged draft "
                f"{result['draft_id']}; this is the same submission, not a new one. {_material_sentence(result)} "
                "Coverage has not been decided.")
    if tool == "route_claims_intake" and status == "routed" and result.get("draft_status") == "retained_pending":
        return (f"Draft {result['reference']} is kept as pending and has gone to the claims intake team under "
                f"{result['desk_reference']}. It is not confirmed as filed; the team replies within one business day.")
    return None
