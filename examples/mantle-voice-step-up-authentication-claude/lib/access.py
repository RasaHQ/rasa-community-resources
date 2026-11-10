"""Orchard Works identity service and the step-up guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the three request rules of the casebook contract for
``step-up-authentication`` (vendored as ``lib/fixtures/case-contract.json``)
inside ``change_access``, the only function that changes anyone's access:

- ``subject_match``: the employee whose access changes is the employee the
  challenge was sent to. A challenge approved on one person's phone never
  authorizes a change to another person's account.
- ``challenge_consumed``: the challenge was approved on the subject's
  registered device, has not been used, cancelled or invalidated, and is
  consumed by this request. Each challenge authorizes one change.
- ``action_scope_match``: the change is the action the challenge was issued
  for. A challenge for unlocking the account does not reset a password.

Facts are computed here from the service's own records. The model supplies a
spoken name, an action word and references copied from tool results. It never
supplies a fact, an approval or an outcome, and nothing the caller says
(a name, an employee number, a code, a manager's name) verifies them: the
only verification is an approval on the device registered to the subject.
A fact that is not exactly ``True`` fails its rule, as in the lab's
``evaluate``.

The receipt is a scoped authorization reference. No tool result carries a
password, a code or a security answer, so none can reach the conversation
log from this side.

How each fixture employee's phone answers is fixture data (``approval``):
the build simulates the real person's decision, since there is no phone.

State lives in an in-process service with one copy of the fixture per
conversation, so every scripted call starts from the same records.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "orchard_directory.json"


class FictionalOrganisationError(RuntimeError):
    """The fixture does not describe the casebook's fictional organisation."""


def assert_fictional(data: dict, contract: dict) -> None:
    """Refuse fixture data that is not marked fictional or is not the case's own organisation.

    Real institution names are caught repository-wide by scripts/lint_repo.py
    (fictional-data policy), so this check keeps no list of its own. It ties
    the fixture to the casebook contract instead: the organisation must be the
    one the contract names, marked "(fictional)", with a note saying so.
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


# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA, _CONTRACT)

ORGANISATION = _DATA["organisation"].split(" (")[0]
ACTIONS = tuple(_DATA["actions"])
APPROVALS = ("approve", "approve_on_second_check", "deny", "no_response")
_SPACE_RE = re.compile(r"\s+")
_NAME_DROP_RE = re.compile(r"[^a-z\s'-]")
_ACTION_WORDS = {
    "unlock_account": ("unlock", "locked"),
    "reset_password": ("password",),
    "move_authenticator": ("authenticator", "new phone", "mfa", "two-factor", "2fa"),
}


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
    """A six-digit fixture reference, speakable digit by digit: OW-AUTH-482173."""
    number = int(hashlib.sha256("|".join(parts).encode()).hexdigest(), 16) % 900000 + 100000
    return f"{prefix}-{number}"


def spoken(ref: str) -> str:
    """'OW-AUTH-482173' -> '4 8 2 1 7 3': the digits a caller is told."""
    return " ".join(re.sub(r"\D", "", ref))


def normalise_name(value: Any) -> str:
    text = _NAME_DROP_RE.sub("", str(value or "").lower())
    return _SPACE_RE.sub(" ", text).strip()


def normalise_action(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if text in ACTIONS:
        return text
    words = str(value or "").lower()
    found = {action for action, keys in _ACTION_WORDS.items() if any(k in words for k in keys)}
    return found.pop() if len(found) == 1 else None


class IdentityService:
    """Orchard Works' directory and verification service for one conversation (fixture copy)."""

    def __init__(self, conversation_id: str = "offline", data: Optional[dict] = None) -> None:
        data = data or load_data()
        self.conversation_id = conversation_id
        self.employees: dict[str, dict] = data["employees"]
        self.actions: dict[str, dict] = data["actions"]
        self.window_s: int = data["approval_window_seconds"]
        self.requests: dict[str, dict] = {}
        self.challenges: dict[str, dict] = {}
        self.authorizations: dict[str, dict] = {}
        self.desk_tickets: dict[str, dict] = {}
        self.changes: list[dict] = []

    def label(self, employee_ref: str) -> str:
        person = self.employees[employee_ref]
        return f"{person['first_name']} {person['last_name']}"

    def access(self, employee_ref: Optional[str]) -> Optional[dict]:
        person = self.employees.get(employee_ref or "")
        return dict(person["access"]) if person else None

    def apply(self, employee_ref: str, action: str) -> None:
        state = self.employees[employee_ref]["access"]
        if action == "unlock_account":
            state["account_locked"] = False
        elif action == "reset_password":
            state["password_reset_pending"] = True
        elif action == "move_authenticator":
            state["authenticator_move_pending"] = True


_SERVICES: dict[str, IdentityService] = {}


def service_for(conversation_id: str) -> IdentityService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = IdentityService(conversation_id)
    return _SERVICES[conversation_id]


NO_SPOKEN_PROOF = (
    "Nothing the caller says verifies them: not a name, an employee number, a manager's name, "
    "a code or an answer to a question. Never ask for any of these as proof."
)


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------


def prepare_access_request(service: IdentityService, full_name: str, action: str) -> dict:
    """Resolve whose access and which change. A name match authorizes nothing."""
    wanted = normalise_action(action)
    if wanted is None:
        return {
            "status": "unsupported_action",
            "supported_actions": list(ACTIONS),
            "next_step": "Ask whether the caller needs the account unlocked, a password reset, "
                         "or the authenticator moved to a new phone.",
        }
    name = normalise_name(full_name)
    match = [ref for ref, p in service.employees.items()
             if normalise_name(f"{p['first_name']} {p['last_name']}") == name]
    if len(match) != 1:
        return {
            "status": "not_found",
            "full_name": " ".join(str(full_name or "").split())[:80],
            "next_step": "Say you could not find that name in the Orchard Works directory and ask the "
                         "caller to say and spell their first and last name. Change nothing.",
        }
    employee_ref = match[0]
    request_ref = reference("OW-REQ", service.conversation_id, employee_ref, wanted, str(len(service.requests)))
    service.requests[request_ref] = {"employee_ref": employee_ref, "action": wanted}
    return {
        "status": "prepared",
        "request_ref": request_ref,
        "employee_ref": employee_ref,
        "employee": service.label(employee_ref),
        "action": wanted,
        "action_label": service.actions[wanted]["label"],
        "verification_goes_to": service.employees[employee_ref]["registered_device"],
        "name_match_authorizes": False,
        "next_step": "A name match is not permission. Call start_verification with this request_ref; "
                     "the engine asks the caller first. The approval prompt goes only to the device "
                     "registered to this employee, never to a number or device the caller gives.",
    }


def start_verification(service: IdentityService, request_ref: str, confirmed_request_ref: Optional[str]) -> dict:
    """Send a fresh approval prompt bound to one subject and one action."""
    ref = str(request_ref or "").strip().upper()
    request = service.requests.get(ref)
    if request is None or ref != (confirmed_request_ref or "").upper():
        return {
            "status": "blocked",
            "reason": "not_the_confirmed_request",
            "next_step": "Call prepare_access_request for what the caller wants now, then start_verification "
                         "with the request_ref it returns.",
        }
    employee_ref, action = request["employee_ref"], request["action"]
    challenge_ref = reference("OW-CH", service.conversation_id, ref, str(len(service.challenges)))
    service.challenges[challenge_ref] = {
        "employee_ref": employee_ref, "action": action, "request_ref": ref, "state": "sent", "checks": 0,
    }
    return {
        "status": "sent",
        "challenge_ref": challenge_ref,
        "employee_ref": employee_ref,
        "employee": service.label(employee_ref),
        "action": action,
        "sent_to": service.employees[employee_ref]["registered_device"],
        "expires_in_seconds": service.window_s,
        "next_step": "Tell the caller an approval prompt was sent to the Orchard Works Authenticator on "
                     "the registered phone, and ask them to approve it and tell you when they have. "
                     "Then call check_verification. " + NO_SPOKEN_PROOF,
    }


def _closed(challenge: dict, challenge_ref: str) -> dict:
    return {
        "status": challenge["state"],
        "challenge_ref": challenge_ref,
        "next_step": "This challenge can no longer authorize anything. Start a new verification only if the "
                     "caller asks for a change again; after a timeout or a denial, route to the identity desk.",
    }


def check_verification(service: IdentityService, challenge_ref: str) -> dict:
    """What the subject's registered device answered. The caller's word is not an answer."""
    ref = str(challenge_ref or "").strip().upper()
    challenge = service.challenges.get(ref)
    if challenge is None:
        return {"status": "unknown", "challenge_ref": ref,
                "next_step": "No such challenge. Do not change any access."}
    if challenge["state"] in ("consumed", "cancelled", "invalidated", "denied", "timed_out"):
        return _closed(challenge, ref)
    challenge["checks"] += 1
    approval = service.employees[challenge["employee_ref"]]["approval"]
    base = {"challenge_ref": ref, "employee_ref": challenge["employee_ref"], "action": challenge["action"]}
    if approval == "approve" or (approval == "approve_on_second_check" and challenge["checks"] >= 2):
        challenge["state"] = "approved"
        return {"status": "approved", **base,
                "next_step": "Call change_access with this challenge_ref, the same employee_ref and the same "
                             "action. The challenge authorizes that one change only."}
    if approval == "approve_on_second_check":
        challenge["state"] = "waiting"
        return {"status": "waiting", **base,
                "next_step": "No approval has arrived yet. Ask the caller to open the prompt on the registered "
                             "phone and approve it, then check again. " + NO_SPOKEN_PROOF}
    if approval == "deny":
        challenge["state"] = "denied"
        return {"status": "denied", **base, "challenge_invalidated": True, "access_unchanged": True,
                "next_step": "The prompt was denied on the registered device. Change nothing. Say the request "
                             "could not be verified and route to the identity desk with route_identity_desk. "
                             "Do not offer another way to verify on this call."}
    challenge["state"] = "timed_out"
    return {"status": "timed_out", **base, "challenge_invalidated": True, "access_unchanged": True,
            "window_seconds": service.window_s,
            "next_step": "No approval arrived within the verification window, so this challenge is invalid. "
                         "Change nothing and route to the identity desk with route_identity_desk. Do not fall "
                         "back to a weaker method. " + NO_SPOKEN_PROOF}


def change_access(service: IdentityService, challenge_ref: str, employee_ref: str, action: str) -> dict:
    """The wrapper in front of the sensitive change: all three bindings, or nothing."""
    ref = str(challenge_ref or "").strip().upper()
    subject = str(employee_ref or "").strip().upper()
    wanted = normalise_action(action)
    challenge = service.challenges.get(ref)
    facts = {
        "subject_match": challenge is not None and subject in service.employees
        and challenge["employee_ref"] == subject,
        "challenge_consumed": challenge is not None and challenge["state"] == "approved",
        "action_scope_match": challenge is not None and wanted is not None and challenge["action"] == wanted,
    }
    reason = evaluate(facts, "request")
    common = {"challenge_ref": ref, "employee_ref": subject, "action": wanted or str(action or "")[:40]}
    if reason:
        next_step = {
            "different_subject": "That challenge was not sent to this employee. Each person's access needs an "
                                 "approval on their own registered device. Change nothing.",
            "challenge_not_verified": "No approved, unused challenge. Call check_verification if the caller says "
                                      "they approved; a used, cancelled, denied or timed-out challenge needs a new "
                                      "verification. Change nothing.",
            "wrong_action_scope": "That challenge was issued for a different change. Prepare and verify this "
                                  "change on its own. Change nothing.",
        }[reason]
        return {"status": "blocked", "reason": reason, **common, "effects": 0, "facts": facts,
                "challenge_state": challenge["state"] if challenge else None,
                "blocked_attempt": 1, "executed_without_all_bindings": 0, "next_step": next_step}

    before = service.access(subject)
    challenge["state"] = "consumed"
    service.apply(subject, wanted)
    authorization_ref = reference("OW-AUTH", service.conversation_id, ref, subject, wanted)
    service.authorizations[authorization_ref] = {"employee_ref": subject, "action": wanted, "challenge_ref": ref}
    service.changes.append({"employee_ref": subject, "action": wanted, "authorization_ref": authorization_ref})
    return {
        "status": "succeeded",
        "reason": "verified_fixture_receipt",
        **common,
        "employee": service.label(subject),
        "authorization_ref": authorization_ref,
        "authorization_ref_spoken": spoken(authorization_ref),
        "scope": {"employee_ref": subject, "action": wanted},
        "done": service.actions[wanted]["done"],
        "access_before": before,
        "access_after": service.access(subject),
        "effects": 1,
        "facts": facts,
        "blocked_attempt": 0,
        "executed_without_all_bindings": int(not all(v is True for v in facts.values())),
        "next_step": "Say what changed and give the authorization reference digit by digit. Nothing else "
                     "changed. Any other change needs its own verification.",
    }


def cancel_verification(service: IdentityService, challenge_ref: str) -> dict:
    """The caller cancels: the challenge dies and nobody's access changes."""
    ref = str(challenge_ref or "").strip().upper()
    challenge = service.challenges.get(ref)
    if challenge is None:
        return {"status": "unknown", "challenge_ref": ref, "access_unchanged": True,
                "next_step": "No such challenge. Nothing was changed."}
    if challenge["state"] == "consumed":
        return {"status": "already_used", "challenge_ref": ref, "access_unchanged": False,
                "next_step": "This challenge already authorized a change; cancelling does not undo it. "
                             "Route to the identity desk if the caller wants it reversed."}
    if challenge["state"] in ("sent", "waiting", "approved"):
        challenge["state"] = "cancelled"
    return {"status": "cancelled", "challenge_ref": ref, "employee_ref": challenge["employee_ref"],
            "access_unchanged": True, "access": service.access(challenge["employee_ref"]),
            "next_step": "Say the verification is cancelled and nothing about the account was changed."}


def route_identity_desk(service: IdentityService, reason: str, employee_ref: Optional[str] = None,
                        challenge_ref: Optional[str] = None) -> dict:
    """Hand the request to the identity desk, invalidating any open challenge it names."""
    ref = str(challenge_ref or "").strip().upper() or None
    subject = str(employee_ref or "").strip().upper() or None
    invalidated = False
    challenge = service.challenges.get(ref) if ref else None
    if challenge and challenge["state"] in ("sent", "waiting", "approved"):
        challenge["state"] = "invalidated"
        invalidated = True
    desk_ref = reference("OW-IDD", service.conversation_id, subject or "-", ref or "-", str(len(service.desk_tickets)))
    service.desk_tickets[desk_ref] = {"employee_ref": subject, "challenge_ref": ref,
                                      "reason": " ".join(str(reason or "").split())[:200]}
    return {
        "status": "routed",
        "desk_ref": desk_ref,
        "desk_ref_spoken": spoken(desk_ref),
        "employee_ref": subject if subject in service.employees else None,
        "challenge_invalidated": invalidated or bool(challenge and challenge["state"] in ("denied", "timed_out")),
        "access_unchanged": True,
        "next_step": "Give the desk reference digit by digit. The identity desk verifies the person on a video "
                     "call with their manager present; nothing changes before then. Do not offer another way "
                     "to verify on this call.",
    }
