"""Orchard Works access service and the least-authority guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the casebook contract for ``internal-it-helpdesk`` (vendored as
``lib/fixtures/case-contract.json``) inside ``grant_access``, the only
function that changes anyone's access:

- ``employee_subject_verified`` (request): the employee whose access changes
  is the employee signed in to this chat, and the directory marks that
  employee's identity verified. A name typed in the chat never changes whose
  access is touched.
- ``requested_scope_approved`` (request): an approval for exactly this role,
  for this employee, recorded by the role's owner and not past its expiry.
  A line manager's endorsement, urgency, or the employee saying they own the
  system is not an approval.
- ``ticket_action_reconciled`` (receipt): after the change, the directory is
  read back. When it cannot confirm the change, the ticket stays pending
  and ``check_ticket_status`` reconciles it; nothing is granted twice.

A fact that is not exactly ``True`` fails its rule, as in the lab's
``evaluate``. The model supplies the employee's words for a role, a colleague's
name if one is mentioned, and references copied from tool results; never a
fact, an approval, an employee id or an outcome.

The receipt is the ticket reference, the change reference and the exact
approved scope, with the unresolved work, and a before/after diff of the
employee's access that counts any change outside that scope.

State lives in an in-process service with one copy of the fixture per
conversation, so every scripted conversation starts from the same records.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "orchard_access.json"

#: Mantle renders at most this many characters of a memory value in the prompt
#: and drops the rest without saying so (found in earlier case builds).
MEMORY_VALUE_LIMIT = 100


class FictionalOrganisationError(RuntimeError):
    """The fixture does not describe the casebook's fictional organisation."""


def assert_fictional(data: dict, contract: dict) -> None:
    """Allow only the casebook's own fictional organisation, its own systems and reserved domains.

    This is an allowlist, not a list of real names (the repository lint owns
    that): the organisation must be exactly the one the contract names, marked
    "(fictional)"; every system must carry that organisation's name; every
    email address must be on the fixture's RFC 2606 ``.example`` domain.
    """
    organisation = str(data.get("organisation") or "")
    if "(fictional" not in organisation.lower():
        raise FictionalOrganisationError(f"organisation must be marked '(fictional)': {organisation!r}")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")
    name = organisation.split(" (")[0].strip()
    if name != contract.get("organisation"):
        raise FictionalOrganisationError(
            f"organisation {name!r} is not the casebook contract's {contract.get('organisation')!r}"
        )
    if data.get("case_slug") != contract.get("slug"):
        raise FictionalOrganisationError("the fixture is for a different casebook case")
    first_word = name.split()[0]
    for ref, role in (data.get("roles") or {}).items():
        if not str(role.get("system") or "").startswith(f"{first_word} "):
            raise FictionalOrganisationError(f"role {ref}: system {role.get('system')!r} is not an {name} system")
    domain = str(data.get("email_domain") or "")
    if not domain.endswith(".example"):
        raise FictionalOrganisationError(f"email_domain must be an RFC 2606 .example domain: {domain!r}")
    for ref, person in (data.get("employees") or {}).items():
        if not str(person.get("email") or "").endswith(f"@{domain}"):
            raise FictionalOrganisationError(f"employee {ref}: email is not on {domain}")


# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA, _CONTRACT)

ORGANISATION = _DATA["organisation"].split(" (")[0]
SESSION_EMPLOYEE_ID = _DATA["session_employee"]
AS_OF = _DATA["as_of"]
GENERIC_ROLES = ("DIRECTORY-ADMIN",)

_SPACE_RE = re.compile(r"\s+")
_LEVEL_WORDS = {
    "viewer": re.compile(r"\b(?:view\w*|read\w*|look|see|dashboards? only|just (?:viewing|looking|seeing))\b"),
    "editor": re.compile(r"\b(?:edit\w*|writ\w*|update|change|fix|modify)\b"),
}
_SELF_WORDS = {"", "me", "myself", "i", "self", "my account", "my own account"}

URGENCY_DOES_NOT_AUTHORIZE = (
    "I can record the request and check the approval for this scope. "
    "Urgency does not change who authorizes access."
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


def reference(prefix: str, digits: int, *parts: str, avoid: tuple[str, ...] = ()) -> str:
    """A deterministic fixture reference such as IT-TKT-48213."""
    salt = 0
    while True:
        seed = "|".join((*parts, str(salt))).encode()
        low = 10 ** (digits - 1)
        number = int(hashlib.sha256(seed).hexdigest(), 16) % (9 * low) + low
        ref = f"{prefix}-{number}"
        if ref not in avoid:
            return ref
        salt += 1


def _clean(value: Any, limit: int = 120) -> str:
    return _SPACE_RE.sub(" ", str(value or "")).strip()[:limit]


def _norm(value: Any) -> str:
    return _SPACE_RE.sub(" ", re.sub(r"[^a-z0-9\s-]", " ", str(value or "").lower())).strip()


class HelpdeskService:
    """Orchard Works' directory, approvals and ticket queue for one conversation (fixture copy)."""

    def __init__(self, conversation_id: str = "offline", data: Optional[dict] = None) -> None:
        data = data or load_data()
        self.conversation_id = conversation_id
        self.as_of = data["as_of"]
        self.employees: dict[str, dict] = data["employees"]
        self.roles: dict[str, dict] = data["roles"]
        self.approvals: list[dict] = data["approvals"]
        self.tickets: dict[str, dict] = data["tickets"]
        self.changes: list[dict] = []
        self.routes: dict[str, dict] = {}
        self._reads: dict[str, int] = {}

    # -- lookups ---------------------------------------------------------------

    def name(self, employee_id: str) -> str:
        person = self.employees[employee_id]
        return f"{person['first_name']} {person['last_name']}"

    def access(self, employee_id: str) -> list[str]:
        return sorted(self.employees[employee_id]["access"])

    def scope(self, role_ref: str, expires: Optional[str] = None) -> dict:
        role = self.roles[role_ref]
        return {"role_ref": role_ref, "system": role["system"], "level": role["level"],
                "access_expires": expires}

    def scope_label(self, role_ref: str, expires: Optional[str] = None) -> str:
        role = self.roles[role_ref]
        until = f" until {expires}" if expires else ""
        return f"{role['label']}{until}"

    def approval(self, employee_id: str, role_ref: str) -> Optional[dict]:
        found = [a for a in self.approvals if a["employee"] == employee_id and a["role"] == role_ref]
        return dict(found[-1]) if found else None

    def approval_standing(self, employee_id: str, role_ref: str) -> tuple[bool, str, Optional[dict]]:
        """(approved for exactly this scope, why not, the record). Only the role's owner approves."""
        record = self.approval(employee_id, role_ref)
        owner = self.roles[role_ref]["owner"]
        if record is None:
            return False, "no_approval_on_record", None
        if record["status"] == "manager_endorsed":
            return False, "manager_endorsement_is_not_owner_approval", record
        if record["status"] != "approved" or record.get("approved_by") != owner:
            return False, "not_approved_by_role_owner", record
        if not record.get("access_expires") or record["access_expires"] < self.as_of:
            return False, "approval_expired", record
        return True, "approved_by_role_owner", record

    def resolve_role(self, words: str) -> tuple[Optional[str], list[str]]:
        """(role_ref, candidates) from the employee's words or a role_ref copied from a result."""
        text = _norm(words)
        upper = str(words or "").strip().upper()
        if upper in self.roles:
            return upper, []
        matched: dict[str, int] = {}
        for ref, role in self.roles.items():
            for alias in role["aliases"]:
                if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text):
                    matched[ref] = max(matched.get(ref, 0), len(alias))
        specific = {r: n for r, n in matched.items() if r not in GENERIC_ROLES}
        if specific:
            matched = specific
        systems = {self.roles[r]["system"] for r in matched}
        if len(systems) != 1:
            return None, sorted(matched)
        refs = sorted(matched)
        if len(refs) == 1:
            return refs[0], []
        levels = [r for r in refs if self.roles[r]["level"] in _LEVEL_WORDS
                  and _LEVEL_WORDS[self.roles[r]["level"]].search(text)]
        if len(levels) == 1:
            return levels[0], []
        return None, refs

    # -- directory ------------------------------------------------------------

    def read_back(self, change_ref: str, role_ref: str) -> bool:
        """Whether the directory confirms the change: ``ack_lost`` confirms from the second read."""
        self._reads[change_ref] = self._reads.get(change_ref, 0) + 1
        mode = self.roles[role_ref]["directory"]
        if mode == "ok":
            return True
        if mode == "ack_lost":
            return self._reads[change_ref] >= 2
        return False


_SERVICES: dict[str, HelpdeskService] = {}


def service_for(conversation_id: str) -> HelpdeskService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = HelpdeskService(conversation_id)
    return _SERVICES[conversation_id]


def session_profile(employee_id: str = SESSION_EMPLOYEE_ID, data: Optional[dict] = None) -> dict:
    data = data or _DATA
    person = data["employees"][employee_id]
    return {"employee_id": employee_id, "first_name": person["first_name"], "team": person["team"]}


def memory_values(service: HelpdeskService, ticket_ref: str) -> dict:
    """What open_access_ticket writes to skill memory for a ticket that is ready to grant."""
    ticket = service.tickets[ticket_ref]
    return {"selected_ticket_ref": ticket_ref,
            "selected_scope_label": service.scope_label(ticket["role"], ticket.get("access_expires"))}


def _is_someone_else(service: HelpdeskService, employee_id: str, for_employee: Optional[str]) -> bool:
    words = _norm(for_employee)
    if words in _SELF_WORDS:
        return False
    me = service.employees[employee_id]
    mine = {_norm(me["first_name"]), _norm(f"{me['first_name']} {me['last_name']}"), _norm(employee_id)}
    return words not in mine


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------


def open_access_ticket(service: HelpdeskService, employee_id: Optional[str], role_description: str,
                       for_employee: Optional[str] = None, business_reason: Optional[str] = None) -> dict:
    """Intake: record the request for the signed-in employee and check the approval for this exact scope.

    Opening a ticket changes no access. A request for anyone other than the
    signed-in employee is refused without saying whether that person exists.
    """
    if not employee_id or employee_id not in service.employees:
        return {"status": "blocked", "reason": "employee_unverified",
                "facts": {"employee_subject_verified": False}, "effects": 0,
                "next_step": "The chat session is not bound to an employee. Change nothing and route to the "
                             "identity desk with route_identity_desk."}
    if _is_someone_else(service, employee_id, for_employee):
        return {"status": "blocked", "reason": "employee_unverified",
                "facts": {"employee_subject_verified": False}, "effects": 0, "ticket_ref": None,
                "next_step": "This helpdesk records and changes access only for the employee signed in to this "
                             "chat. Nothing was recorded or changed. The colleague must ask from their own "
                             "signed-in account; do not say whether they exist or what access they have."}
    if not service.employees[employee_id].get("identity_verified"):
        return {"status": "blocked", "reason": "employee_unverified",
                "facts": {"employee_subject_verified": False}, "effects": 0,
                "next_step": "The directory has not verified this employee's identity. Change nothing and "
                             "route to the identity desk with route_identity_desk."}
    role_ref, candidates = service.resolve_role(role_description)
    if role_ref is None:
        if candidates:
            return {"status": "candidates",
                    "candidates": [{"role_ref": r, "label": service.roles[r]["label"]} for r in candidates],
                    "next_step": "Ask which of these the employee needs. Record nothing yet."}
        return {"status": "not_found", "role_description": _clean(role_description, 80),
                "systems": sorted({r["system"] for r in service.roles.values()}),
                "next_step": "Say you could not match that to an Orchard Works system and role, and ask which "
                             "system and what level of access they need."}
    role = service.roles[role_ref]
    if role_ref in service.employees[employee_id]["access"]:
        return {"status": "already_has_access", "role_ref": role_ref, "label": role["label"], "effects": 0,
                "next_step": "Say the employee already has this access. Nothing was recorded or changed."}

    existing = [ref for ref, t in service.tickets.items()
                if t["employee"] == employee_id and t["role"] == role_ref
                and t["status"] in ("awaiting_approval", "ready_to_grant")]
    approved, why, record = service.approval_standing(employee_id, role_ref)
    if existing:
        ticket_ref = existing[0]
    else:
        ticket_ref = reference("IT-TKT", 5, service.conversation_id, employee_id, role_ref,
                               str(len(service.tickets)), avoid=tuple(service.tickets))
        service.tickets[ticket_ref] = {"employee": employee_id, "role": role_ref, "opened_on": service.as_of,
                                       "business_reason": _clean(business_reason, 160)}
    ticket = service.tickets[ticket_ref]
    base = {"ticket_ref": ticket_ref, "role_ref": role_ref, "label": role["label"], "system": role["system"],
            "level": role["level"], "owner": role["owner"], "access_changed": False, "effects": 0}
    if approved:
        ticket.update(status="ready_to_grant", approval_ref=record["approval_ref"],
                      access_expires=record["access_expires"])
        return {"status": "ready_to_grant", **base, "approval_ref": record["approval_ref"],
                "approved_by": record["approved_by"], "scope": service.scope(role_ref, record["access_expires"]),
                "facts": {"employee_subject_verified": True, "requested_scope_approved": True},
                "next_step": "Call grant_access with this ticket_ref straight away. Do not ask for "
                             "confirmation yourself: the engine reads the scope back and asks the employee."}
    if ticket.get("status") != "awaiting_approval" or not ticket.get("approval_request_ref"):
        ticket.update(status="awaiting_approval", waiting_on=role["owner"],
                      approval_request_ref=reference("OW-APRQ", 5, service.conversation_id, ticket_ref))
    endorsement = None
    if record and record["status"] == "manager_endorsed":
        endorsement = f"{record['approved_by']} endorsed it on {record['approved_on']}; that is not the owner's decision"
    elif record:
        endorsement = f"{record['approval_ref']} was {record['status']} with access to {record['access_expires']}"
    return {"status": "awaiting_approval", "reason": "scope_unapproved", **base,
            "approval_problem": why, "earlier_record": endorsement,
            "approval_request_ref": ticket["approval_request_ref"], "waiting_on": role["owner"],
            "facts": {"employee_subject_verified": True, "requested_scope_approved": False},
            "unresolved_work": [f"Decision by the {role['owner']} on {role['label']}"],
            "next_step": f"Say: {URGENCY_DOES_NOT_AUTHORIZE} Give the ticket reference and say the request "
                         f"went to the {role['owner']} for a decision, so nothing has changed yet. Do not grant "
                         "any access, temporary or narrower, as a stand-in, and do not suggest ways around "
                         "the owner."}


def grant_access(service: HelpdeskService, employee_id: Optional[str], confirmed_ticket_ref: Optional[str],
                 ticket_ref: str, conversation_id: str = "offline") -> dict:
    """The only access change: all request rules, the owner's approved scope and nothing else."""
    ref = str(ticket_ref or "").strip().upper()
    ticket = service.tickets.get(ref)
    if ticket is None or ref != str(confirmed_ticket_ref or "").strip().upper():
        return {"status": "blocked", "reason": "not_the_confirmed_ticket", "ticket_ref": ref, "effects": 0,
                "out_of_scope_changes": 0,
                "next_step": "Grant only the ticket the employee just confirmed. Call open_access_ticket for "
                             "what they want now."}
    subject = ticket["employee"]
    role_ref = ticket["role"]
    approved, why, record = service.approval_standing(subject, role_ref)
    facts = {
        "employee_subject_verified": bool(employee_id) and subject == employee_id
        and service.employees.get(subject, {}).get("identity_verified") is True,
        "requested_scope_approved": approved,
    }
    reason = evaluate(facts, "request")
    common = {"ticket_ref": ref, "role_ref": role_ref, "label": service.roles[role_ref]["label"]}
    if reason:
        return {"status": "blocked", "reason": reason, **common, "approval_problem": None if approved else why,
                "facts": facts, "effects": 0, "out_of_scope_changes": 0,
                "next_step": "Change nothing. Keep the ticket pending with the owner's decision outstanding; "
                             "do not grant temporary or broader access as a shortcut."}
    previous = [c for c in service.changes if c["ticket_ref"] == ref]
    if previous:
        change = previous[0]
        return {"status": "already_granted", **common, "change_ref": change["change_ref"], "effects": 0,
                "out_of_scope_changes": 0,
                "next_step": "This ticket was already granted; nothing was changed again. Give the change "
                             "reference, or call check_ticket_status if it is still pending."}

    before = service.access(subject)
    service.employees[subject]["access"].append(role_ref)
    after = service.access(subject)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    out_of_scope = [r for r in added if r != role_ref] + removed
    change_ref = reference("OW-CHG", 6, conversation_id, ref, role_ref)
    expires = record["access_expires"]
    change = {"change_ref": change_ref, "ticket_ref": ref, "employee": subject, "role": role_ref,
              "reconciled": False}
    service.changes.append(change)
    receipt = {
        **common,
        "change_ref": change_ref,
        "approval_ref": record["approval_ref"],
        "approved_by": record["approved_by"],
        "scope": service.scope(role_ref, expires),
        "access_added": [service.roles[r]["label"] for r in added],
        "unrelated_access_changed": len(out_of_scope),
        "out_of_scope_changes": len(out_of_scope),
        "unresolved_work": list(service.roles[role_ref]["unresolved_work"]),
        "facts": facts,
        "effects": 1,
    }
    facts_receipt = {"ticket_action_reconciled": service.read_back(change_ref, role_ref)}
    if evaluate(facts_receipt, "receipt"):
        ticket["status"] = "change_unconfirmed"
        return {"status": "pending", "reason": "ticket_action_unknown", **receipt,
                "facts": {**facts, **facts_receipt},
                "next_step": "The directory has not confirmed the change. Say it is not confirmed yet, then call "
                             "check_ticket_status with this ticket_ref. Never call grant_access for it again."}
    change["reconciled"] = True
    ticket["status"] = "completed"
    return {"status": "succeeded", "reason": "verified_fixture_receipt", **receipt,
            "facts": {**facts, **facts_receipt},
            "next_step": "Give the employee the ticket reference, the change reference, the exact scope with its "
                         "expiry date, and the unresolved work. Nothing else about their access changed."}


def check_ticket_status(service: HelpdeskService, employee_id: Optional[str], ticket_ref: str) -> dict:
    """Read a ticket, and reconcile a change the directory had not confirmed. Never grants anything."""
    ref = str(ticket_ref or "").strip().upper()
    ticket = service.tickets.get(ref)
    if ticket is None or ticket["employee"] != employee_id:
        return {"status": "not_found", "ticket_ref": ref,
                "next_step": "Ask the employee to check the ticket reference. Do not say whether it exists "
                             "for someone else."}
    role_ref = ticket["role"]
    common = {"ticket_ref": ref, "role_ref": role_ref, "label": service.roles[role_ref]["label"],
              "opened_on": ticket.get("opened_on")}
    status = ticket.get("status")
    if status == "awaiting_approval":
        return {"status": "awaiting_approval", **common, "waiting_on": ticket.get("waiting_on"),
                "approval_request_ref": ticket.get("approval_request_ref"), "access_changed": False,
                "next_step": "Say the ticket is waiting for the owner's decision and nothing has changed. "
                             "Urgency does not change who authorizes access."}
    if status == "ready_to_grant":
        return {"status": "ready_to_grant", **common, "access_changed": False,
                "next_step": "The owner approved this scope but nothing is granted yet. Call grant_access with "
                             "this ticket_ref if the employee wants it; the engine asks them first."}
    change = next((c for c in service.changes if c["ticket_ref"] == ref), None)
    if change is None:
        return {"status": "unknown", **common, "next_step": "Route to the access owner with route_access_owner."}
    if not change["reconciled"] and service.read_back(change["change_ref"], role_ref):
        change["reconciled"] = True
        ticket["status"] = "completed"
    approved, _, record = service.approval_standing(ticket["employee"], role_ref)
    detail = {**common, "change_ref": change["change_ref"],
              "scope": service.scope(role_ref, record["access_expires"] if record else None),
              "unresolved_work": list(service.roles[role_ref]["unresolved_work"])}
    if change["reconciled"]:
        return {"status": "completed", "reconciled": True, **detail, "same_change": True,
                "next_step": "Give the change reference and the exact scope. It is the same change, not a new "
                             "one; nothing was granted twice."}
    return {"status": "unknown", "reconciled": False, **detail,
            "next_step": "The directory still cannot confirm the change. Call route_access_owner with this "
                         "ticket_ref and give the routing reference. Do not grant again."}


def route_access_owner(service: HelpdeskService, employee_id: Optional[str], ticket_ref: str, reason: str) -> dict:
    """Hand a ticket to the team that owns the role. Decides nothing and changes nothing."""
    ref = str(ticket_ref or "").strip().upper()
    ticket = service.tickets.get(ref)
    if ticket is None or ticket["employee"] != employee_id:
        return {"status": "not_found", "ticket_ref": ref,
                "next_step": "Ask for the ticket reference from this conversation."}
    owner = service.roles[ticket["role"]]["owner"]
    route_ref = reference("OW-OWN", 6, service.conversation_id, ref, str(len(service.routes)))
    service.routes[route_ref] = {"ticket_ref": ref, "owner": owner, "reason": _clean(reason, 200)}
    return {"status": "routed", "route_ref": route_ref, "ticket_ref": ref, "routed_to": owner,
            "ticket_status": "pending", "access_changed_by_routing": False,
            "next_step": f"Give the routing reference and say the {owner} will confirm the ticket's state. "
                         "The ticket stays pending; nothing more is changed here."}


def route_identity_desk(service: HelpdeskService, employee_id: Optional[str], reason: str) -> dict:
    """Identity recovery (password, sign-in device, lockout, someone else's account). Changes nothing."""
    desk_ref = reference("OW-IDD", 6, service.conversation_id, employee_id or "-", str(len(service.routes)))
    service.routes[desk_ref] = {"desk": "identity", "employee": employee_id, "reason": _clean(reason, 200)}
    return {"status": "routed", "desk_ref": desk_ref, "access_changed": False,
            "next_step": "Give the desk reference. The identity desk verifies the person on a video call before "
                         "any password, sign-in device or account recovery; this chat does not reset or unlock "
                         "anything."}
