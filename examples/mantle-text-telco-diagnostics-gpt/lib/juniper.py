"""Juniper Mobile network service and the recovery-step guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three request-phase rules of the casebook contract for
``telco-diagnostics`` (vendored as ``lib/fixtures/case-contract.json``), in the
lab's order:

- ``area_outage_checked``: this conversation checked the service's area for an
  outage and got a known answer. A check that came back ``unknown`` (the outage
  feed is down) does not count, so device changes stop until the status is
  known.
- ``recovery_step_scoped``: the step is exactly one catalogued operation
  (``reboot`` or ``factory_reset``) on the one device of one of the caller's
  own services. "Reset" alone is ambiguous and fails. A destructive operation
  also needs the customer's own words to name it: the model cannot turn
  "reset it" or "do whatever it takes" into a factory reset.
- ``disruption_confirmed``: the engine showed the customer this selection's
  disruption boundary word for word, and the customer replied after it.

The lab's lesson adds one precondition the contract has no field for: when the
known status is an active outage, no device step runs at all
(``area_outage_active``). A reboot cannot bring back a signal the network is
not sending.

Facts are computed here from trusted data: the per-conversation network state,
the session's customer id and the conversation transcript the engine holds.
The model supplies a service id, an operation name and a selection reference
copied from a tool result. It never supplies a fact, a customer id or an
outcome. A fact that is not exactly ``True`` fails its rule, as in the lab's
``evaluate``.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "juniper.json"

DEMO_CUSTOMER_ID = "JM-CUST-5520"

# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))

# The casebook's question for an ambiguous request, word for word.
SCOPE_QUESTION = _CONTRACT["question"]

_ID_RE = re.compile(r"[^A-Z0-9-]")
_SENTENCE_RE = re.compile(r"(?<=[.!?;])\s+|\n+")

# Operation names the model may pass, mapped to the catalogue. Anything else,
# including a bare "reset", "hard reset" or "full reset", is ambiguous.
_OPERATION_ALIASES = {
    "reboot": "reboot",
    "restart": "reboot",
    "power cycle": "reboot",
    "factory reset": "factory_reset",
    "factory_reset": "factory_reset",
    "reset to factory settings": "factory_reset",
}

# The customer's own words naming a destructive reset, and words that negate
# a match earlier in the same sentence ("don't factory reset it").
DESTRUCTIVE_WORDS_PATTERN = (
    r"\bfactory\b|\bwip(?:e|ing)\b|\beras(?:e|ing)\b"
    r"|\b(?:default|original) settings\b"
)
DESTRUCTIVE_WORDS_RE = re.compile(DESTRUCTIVE_WORDS_PATTERN, re.IGNORECASE)
NEGATION_RE = re.compile(r"\b(?:not|never|no|without|dont)\b|n't\b", re.IGNORECASE)


def load_contract() -> dict:
    return json.loads(json.dumps(_CONTRACT))


def load_data() -> dict:
    return json.loads(json.dumps(_DATA))


def request_rules(contract: Optional[dict] = None) -> list[dict]:
    contract = contract or _CONTRACT
    return [rule for rule in contract["rules"] if rule["phase"] == "request"]


def evaluate(facts: dict, contract: Optional[dict] = None) -> Optional[str]:
    """First failing rule's reason, or None. Exactly ``True`` passes, as in the lab."""
    for rule in request_rules(contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


def normalise_id(value: Any) -> str:
    """Upper-case, spaces to hyphens, drop anything else: ' jm fb 204988 ' -> JM-FB-204988."""
    return _ID_RE.sub("", re.sub(r"\s+", "-", str(value or "").strip().upper()))


def normalise_operation(value: Any) -> Optional[str]:
    text = re.sub(r"[\s_-]+", " ", str(value or "").strip().lower())
    return _OPERATION_ALIASES.get(text) or _OPERATION_ALIASES.get(text.replace(" ", "_"))


def customer_named_destructive(user_texts: Iterable[str]) -> bool:
    """True when a customer message names a factory reset without negating it."""
    for text in user_texts:
        for sentence in _SENTENCE_RE.split(text or ""):
            for match in DESTRUCTIVE_WORDS_RE.finditer(sentence):
                if not NEGATION_RE.search(sentence[: match.start()].replace("\u2019", "'")):
                    return True
    return False


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8].upper()


class NetworkService:
    """Juniper Mobile's network and device services for one conversation (fixture copy)."""

    def __init__(self, data: Optional[dict] = None) -> None:
        self.data = data or load_data()
        self.outage_checks: dict[str, str] = {}  # service id -> outage | clear | unknown
        self.selection: Optional[dict] = None
        self.executed: dict[str, dict] = {}  # selection ref -> receipt
        self.command_log: list[dict] = []  # every command sent to a device
        self.devices: dict[str, dict] = {
            sid: {"rebooted": False, "settings_intact": True}
            for sid in self.data["services"]
        }

    def owned(self, customer_id: Optional[str], service_id: Any) -> Optional[dict]:
        record = self.data["services"].get(normalise_id(service_id))
        if record is None or not customer_id or record["customer_id"] != customer_id:
            return None
        return record


_SERVICES: dict[str, NetworkService] = {}


def service_for(conversation_id: str) -> NetworkService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = NetworkService()
    return _SERVICES[conversation_id]


def customer_profile(customer_id: str = DEMO_CUSTOMER_ID, data: Optional[dict] = None) -> dict:
    data = data or _DATA
    person = data["customers"][customer_id]
    services = [
        {"service_id": sid, "label": s["label"], "address": s["address"]}
        for sid, s in sorted(data["services"].items())
        if s["customer_id"] == customer_id
    ]
    return {
        "customer_id": customer_id,
        "first_name": person["first_name"],
        "last_name": person["last_name"],
        "services": services,
    }


# Mantle cuts every memory value it renders into the prompt at this length
# (rasa/mantle/prompts/memory_lines.py, MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5)
# and appends "... [truncated]". Every value this project writes stays under it.
PROMPT_MEMORY_VALUE_LIMIT = 100
MAX_SERVICES = 3


def service_memory_lines(profile: dict) -> dict[str, str]:
    """``service_1`` .. ``service_3`` memory values, each short enough to reach the model whole."""
    services = profile["services"]
    if len(services) > MAX_SERVICES:
        raise ValueError(f"memory.yml declares {MAX_SERVICES} service fields; the profile has {len(services)}")
    lines = {}
    for i, s in enumerate(services, start=1):
        line = f"{s['label']} at {s['address']} ({s['service_id']})"
        if len(line) > PROMPT_MEMORY_VALUE_LIMIT:
            raise ValueError(f"service line longer than the prompt limit: {line!r}")
        lines[f"service_{i}"] = line
    return lines


def _not_on_account(service_id: Any) -> dict:
    # Someone else's service and a number that does not exist get the same
    # payload, so the answer never confirms a line exists for another customer.
    return {
        "status": "blocked",
        "reason": "service_not_on_account",
        "service_id": normalise_id(service_id),
        "device_changes": 0,
        "next_step": (
            "Say you cannot find that service on this customer's account and ask "
            "them to check it. Do not say whether it exists for anyone else."
        ),
    }


# ----------------------------------------------------------------------------
# Read-only tools
# ----------------------------------------------------------------------------


def check_area_outage(net: NetworkService, customer_id: Optional[str], service_id: Any) -> dict:
    """Read the area-outage status for one of the caller's services. Changes nothing."""
    record = net.owned(customer_id, service_id)
    if record is None:
        return _not_on_account(service_id)
    sid = normalise_id(service_id)
    area = net.data["areas"][record["area"]]
    base = {
        "service_id": sid,
        "service_label": record["label"],
        "area": area["name"],
        "device_changes": 0,
    }
    if area["feed"] != "ok":
        net.outage_checks[sid] = "unknown"
        return {
            "status": "unknown",
            **base,
            "last_known": area.get("last_known"),
            "next_step": (
                "The outage feed for this area is unavailable, so the outage status "
                "is unknown. Say so and give the last known observation time. Do not "
                "reboot or reset anything and do not suggest a stronger reset. Offer "
                "to check the status again later or request_technician_visit."
            ),
        }
    outage = area["outage"]
    if outage:
        net.outage_checks[sid] = "outage"
        return {
            "status": "outage",
            **base,
            "observed_at": area["observed_at"],
            **outage,
            "next_step": (
                "Tell the customer about the outage, its cause and the estimated "
                "restore time. A reboot or reset cannot help while the network "
                "sends no signal, so do not offer one."
            ),
        }
    net.outage_checks[sid] = "clear"
    return {
        "status": "clear",
        **base,
        "observed_at": area["observed_at"],
        "next_step": "No area outage. Offer run_line_diagnostics before any device step.",
    }


def run_line_diagnostics(net: NetworkService, customer_id: Optional[str], service_id: Any) -> dict:
    """Read the line and device state. Read-only: sends no command to the device."""
    record = net.owned(customer_id, service_id)
    if record is None:
        return _not_on_account(service_id)
    sid = normalise_id(service_id)
    readings = record["after_reboot"] if net.devices[sid]["rebooted"] and record["after_reboot"] else record["diagnostics"]
    return {
        "status": "diagnosed",
        "service_id": sid,
        "service_label": record["label"],
        "device": record["device"],
        "readings": readings,
        "settings_intact": net.devices[sid]["settings_intact"],
        "reference": f"JM-DX-{_digest(sid, str(len(net.command_log)), json.dumps(readings, sort_keys=True))}",
        "disruption": "None. Diagnostics are read-only; nothing on the device changed.",
        "device_changes": 0,
        "area_outage_status": net.outage_checks.get(sid, "not_checked"),
    }


def request_technician_visit(
    net: NetworkService, customer_id: Optional[str], service_id: Any, reason: str
) -> dict:
    record = net.owned(customer_id, service_id)
    if record is None:
        return _not_on_account(service_id)
    sid = normalise_id(service_id)
    return {
        "status": "routed",
        "service_id": sid,
        "service_label": record["label"],
        "reference": f"JM-TEC-{_digest(customer_id or '', sid, 'technician')}",
        "route": "network field team",
        "reason": " ".join(str(reason or "").split())[:200],
        "first_available_visit": "2026-10-02, 08:00 to 12:00",
        "device_changes": 0,
        "next_step": "Give the reference and the visit window. Nothing on the device has changed.",
    }


# ----------------------------------------------------------------------------
# The guarded recovery step
# ----------------------------------------------------------------------------


def _outage_fact(net: NetworkService, sid: str) -> tuple[bool, Optional[str]]:
    status = net.outage_checks.get(sid)
    return status in ("outage", "clear"), status


def _blocked(reason: str, **extra: Any) -> dict:
    next_step = {
        "outage_not_checked": (
            "Call check_area_outage for this service first. If it has been checked "
            "and the status is unknown, stop: do not change the device and do not "
            "suggest a stronger reset. Offer to check the status again later or "
            "request_technician_visit."
        ),
        "area_outage_active": (
            "There is an active area outage. A reboot or reset cannot help and would "
            "only disrupt the customer. Give the outage details and estimated restore "
            "time; offer read-only diagnostics instead."
        ),
        "reset_scope_ambiguous": (
            "The step is not one clearly chosen operation. Ask the customer exactly: "
            f"\"{SCOPE_QUESTION}\" Then select only what they choose."
        ),
        "disruption_not_confirmed": (
            "The customer has not confirmed this step after seeing its disruption. "
            "Call run_recovery_step with the selection_ref from select_recovery_step "
            "so the engine asks them; never assume a yes."
        ),
    }[reason]
    return {"status": "blocked", "reason": reason, "device_changes": 0, **extra, "next_step": next_step}


def recovery_facts(
    net: NetworkService,
    customer_id: Optional[str],
    service_id: Any,
    operation: Any,
    user_texts: Iterable[str],
) -> tuple[dict, Optional[str]]:
    """The request facts before confirmation, and the known outage status."""
    sid = normalise_id(service_id)
    record = net.owned(customer_id, sid)
    checked, status = _outage_fact(net, sid)
    op = normalise_operation(operation)
    scoped = record is not None and op is not None
    if scoped and net.data["operations"][op]["destructive"]:
        scoped = customer_named_destructive(user_texts)
    return {"area_outage_checked": checked, "recovery_step_scoped": scoped}, status


def select_recovery_step(
    net: NetworkService,
    customer_id: Optional[str],
    service_id: Any,
    operation: Any,
    user_texts: list[str],
) -> dict:
    """Resolve one recovery step on one device. Sends nothing to the device.

    Evaluated with ``disruption_confirmed`` still false, so a valid selection is
    exactly one that fails only on confirmation. The engine then asks.
    """
    sid = normalise_id(service_id)
    record = net.owned(customer_id, sid)
    if record is None:
        return _not_on_account(service_id)
    facts, status = recovery_facts(net, customer_id, sid, operation, user_texts)
    facts["disruption_confirmed"] = False
    reason = evaluate(facts)
    if reason == "outage_not_checked":
        return _blocked(reason, service_id=sid, facts=facts, area_outage_status=status or "not_checked")
    if status == "outage":
        return _blocked("area_outage_active", service_id=sid, facts=facts, area_outage_status=status)
    if reason == "reset_scope_ambiguous":
        return _blocked(reason, service_id=sid, facts=facts, operation_requested=str(operation or "")[:60])
    op = normalise_operation(operation)
    spec = net.data["operations"][op]
    ref = f"JM-SEL-{_digest(sid, op, str(len(user_texts)), str(len(net.command_log)))}"
    net.selection = {
        "selection_ref": ref,
        "service_id": sid,
        "operation": op,
        "disruption_boundary": spec["disruption"],
        "user_turns_at_selection": len(user_texts),
    }
    return {
        "status": "selected",
        "selection_ref": ref,
        "service_id": sid,
        "service_label": record["label"],
        "address": record["address"],
        "device": record["device"],
        "operation": op,
        "disruption_boundary": spec["disruption"],
        "device_changes": 0,
        "facts": facts,
        "next_step": (
            "Call run_recovery_step with this selection_ref straight away. The engine "
            "shows the customer the disruption boundary and asks them to confirm "
            "before anything is sent to the device."
        ),
    }


def boundary_confirmed(transcript: list[tuple[str, str]], selection: dict) -> bool:
    """The boundary text reached the customer after the selection, and they replied.

    *transcript* is the conversation's ``("user" | "bot", text)`` events in
    order, from the engine's tracker.
    """
    users_seen = 0
    shown = False
    for kind, text in transcript:
        if kind == "user":
            users_seen += 1
            if shown:
                return True
        elif kind == "bot" and users_seen >= selection["user_turns_at_selection"]:
            if selection["disruption_boundary"] in (text or ""):
                shown = True
    return False


def run_recovery_step(
    net: NetworkService,
    customer_id: Optional[str],
    selection_ref: Any,
    transcript: list[tuple[str, str]],
) -> dict:
    """Send the confirmed selection's command to the device, and only that command."""
    ref = str(selection_ref or "").strip().upper()
    if ref in net.executed:
        return {**net.executed[ref], "replay": True, "device_changes": 0}
    selection = net.selection
    if selection is None or selection["selection_ref"] != ref:
        # No step was selected and scoped under this reference.
        return _blocked("reset_scope_ambiguous", selection_ref=ref)
    sid = selection["service_id"]
    user_texts = [text for kind, text in transcript if kind == "user"]
    facts, status = recovery_facts(net, customer_id, sid, selection["operation"], user_texts)
    facts["disruption_confirmed"] = boundary_confirmed(transcript, selection)
    reason = evaluate(facts)
    if reason == "outage_not_checked":
        return _blocked(reason, selection_ref=ref, service_id=sid, facts=facts)
    if status == "outage":
        return _blocked("area_outage_active", selection_ref=ref, service_id=sid, facts=facts)
    if reason:
        return _blocked(reason, selection_ref=ref, service_id=sid, facts=facts)

    record = net.data["services"][sid]
    op = selection["operation"]
    spec = net.data["operations"][op]
    command = {"device": record["device"]["id"], "command": spec["command"], "selection_ref": ref}
    net.command_log.append(command)
    device = net.devices[sid]
    device["rebooted"] = True
    if spec["destructive"]:
        device["settings_intact"] = False
    receipt = {
        "status": "executed",
        "reason": "verified_fixture_receipt",
        "selection_ref": ref,
        "service_id": sid,
        "service_label": record["label"],
        "device": record["device"],
        "confirmed_operation": op,
        "command_sent": spec["command"],
        "disruption_boundary": spec["disruption"],
        "settings_kept": device["settings_intact"],
        "receipt": f"JM-RCV-{_digest(sid, ref, spec['command'])}",
        "device_changes": 1,
        "replay": False,
        "facts": facts,
        "next_step": (
            "Give the receipt and restate the disruption boundary. Offer to run "
            "run_line_diagnostics again in a few minutes. Do not start another step "
            "unless the customer chooses one."
        ),
    }
    receipt["commands_sent_this_conversation"] = [c["command"] for c in net.command_log]
    net.executed[ref] = receipt
    net.selection = None
    return receipt


def cancel_recovery_step(net: NetworkService) -> dict:
    """Drop the pending selection. Nothing was or will be sent to the device."""
    pending = net.selection
    net.selection = None
    return {
        "status": "cancelled",
        "cancelled_selection": pending["selection_ref"] if pending else None,
        "cancelled_operation": pending["operation"] if pending else None,
        "device_changes": 0,
        "next_step": (
            "Say nothing was sent to the device. Keep to read-only diagnostics "
            "unless the customer chooses a new step."
        ),
    }
