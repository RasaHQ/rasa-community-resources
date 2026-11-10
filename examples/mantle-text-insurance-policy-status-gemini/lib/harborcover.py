"""HarborCover status service and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three request-phase rules of the casebook contract for
``insurance-policy-status`` (vendored as ``lib/fixtures/case-contract.json``):

- ``policy_subject_matched``: the record belongs to the caller on this session.
- ``status_timestamp_current``: the status service observed the record within
  the freshness window, measured on the fixture clock.
- ``decision_type_labeled``: the record says whether it is a policy status, a
  claim's progress or a coverage decision.

Facts are computed here from trusted data and the session's customer id. The
model supplies only a policy or claim number; it never supplies a fact, a
customer id or a coverage outcome. A fact that is not exactly ``True`` fails
its rule, as in the lab's ``evaluate``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "harborcover.json"

DEMO_CUSTOMER_ID = "HC-CUST-2041"

# Wording that promises or implies cover for a loss. Used by the output guard
# in hooks.py. The harness counts the same pattern in bot turns as the case
# metric; tests/test_guard.py keeps the two copies identical.
COVERAGE_PROMISE_PATTERN = (
    r"\b(?:you(?:'re| are)|you'?ll be|it(?:'s| is| will be| would be)|"
    r"this (?:is|will be|would be|should be)|that(?:'s| is| will be| would be| should be)|"
    r"(?:the|your|this) (?:loss|damage|claim|leak|flood|repair) (?:is|will be|would be|should be))"
    r" (?:fully |definitely |probably |likely )?covered\b"
    r"|\bwe(?:'ll| will) (?:pay|cover)\b"
    r"|\bcovered under your (?:policy|plan)\b"
)
COVERAGE_PROMISE_RE = re.compile(COVERAGE_PROMISE_PATTERN, re.IGNORECASE)
# A match is not a promise when the same sentence hedges or negates it before
# the match: "only the claims service can decide whether this loss is covered".
COVERAGE_HEDGE_PATTERN = r"\b(?:not|cannot|unable|whether|if|until|only|no)\b|n't\b"
COVERAGE_HEDGE_RE = re.compile(COVERAGE_HEDGE_PATTERN, re.IGNORECASE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def coverage_promises(text: str) -> list[str]:
    """Phrases in *text* that promise or imply cover, sentence by sentence."""
    found = []
    for sentence in _SENTENCE_RE.split(text or ""):
        for match in COVERAGE_PROMISE_RE.finditer(sentence):
            if not COVERAGE_HEDGE_RE.search(sentence[: match.start()]):
                found.append(match.group(0))
    return found

_ID_RE = re.compile(r"[^A-Z0-9-]")

NOT_A_COVERAGE_DECISION = (
    "A policy state or a claim stage is not a coverage decision. Only the "
    "HarborCover claims service decides whether a particular loss is covered."
)


# Read once, at import. Mantle imports tool modules from a temporary snapshot
# of lib/ and removes it after loading, so a file read at dispatch time fails
# with FileNotFoundError (observed on the pinned engine).
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))


def load_contract() -> dict:
    return json.loads(json.dumps(_CONTRACT))


def load_data() -> dict:
    return json.loads(json.dumps(_DATA))


def request_rules(contract: Optional[dict] = None) -> list[dict]:
    contract = contract or load_contract()
    return [rule for rule in contract["rules"] if rule["phase"] == "request"]


def evaluate(facts: dict, contract: Optional[dict] = None) -> Optional[str]:
    """Return the first failing rule's reason, or None when every rule holds.

    Same semantics as the casebook lab: a fact must be exactly ``True``.
    ``"true"``, ``1``, ``None`` and a missing key all fail.
    """
    for rule in request_rules(contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


def normalise_id(value: Any) -> str:
    """Upper-case, spaces to hyphens, drop anything else: ' clm 24 0871 ' -> CLM-24-0871."""
    return _ID_RE.sub("", re.sub(r"\s+", "-", str(value or "").strip().upper()))


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8].upper()


def status_reference(data: dict, customer_id: str, record_id: str, observed_at: str) -> str:
    """A dated reference for one status answer (the case's receipt)."""
    day = _parse(data["as_of"]).strftime("%Y%m%d")
    return f"HC-ST-{day}-{_digest(customer_id, record_id, observed_at)}"


def facts_for(record: Optional[dict], customer_id: str, data: dict) -> dict:
    """Compute the three contract facts from trusted data only."""
    if record is None or record.get("customer_id") != customer_id:
        # Unknown and someone else's record fail the same rule with the same
        # payload, so the answer never confirms that a number exists for
        # another customer, nor how fresh its status is.
        return {"policy_subject_matched": False}
    as_of = _parse(data["as_of"])
    window = timedelta(hours=data["freshness_hours"])
    observed = record.get("observed_at")
    return {
        "policy_subject_matched": True,
        "status_timestamp_current": bool(observed) and as_of - _parse(observed) <= window,
        "decision_type_labeled": record.get("decision_type")
        in ("policy_status", "claim_progress", "coverage_decision"),
    }


def _blocked(reason: str, **extra: Any) -> dict:
    next_step = {
        "wrong_policy_subject": (
            "Say you cannot find that number on this caller's account and ask "
            "them to check it. Do not say whether it exists for anyone else."
        ),
        "stale_claim_status": (
            "Say the current status is unavailable. Give the last known stage "
            "with its timestamp, say it may have changed, and offer "
            "request_case_team_callback. Do not guess progress."
        ),
        "status_as_coverage": (
            "The record has no labeled decision type. Do not describe it as "
            "approved, settled, paid or covered. Offer request_case_team_callback."
        ),
    }[reason]
    return {"status": "blocked", "reason": reason, **extra, "next_step": next_step}


def policy_status(customer_id: str, policy_number: str, data: Optional[dict] = None) -> dict:
    data = data or load_data()
    number = normalise_id(policy_number)
    record = data["policies"].get(number)
    facts = facts_for(record, customer_id, data)
    reason = evaluate(facts)
    if reason == "wrong_policy_subject":
        return _blocked(reason, policy_number=number, facts=facts)
    if reason == "stale_claim_status":
        return _blocked(
            reason,
            policy_number=number,
            facts=facts,
            last_known={"state": record["state"], "observed_at": record.get("observed_at")},
        )
    if reason:
        return _blocked(reason, policy_number=number, facts=facts)
    answer = {
        "status": "answered",
        "decision_type": "policy_status",
        "policy_number": number,
        "product": record["product"],
        "state": record["state"],
        "effective_from": record["effective_from"],
        "effective_to": record["effective_to"],
        "observed_at": record["observed_at"],
        "status_reference": status_reference(data, customer_id, number, record["observed_at"]),
        "coverage_decision": None,
        "not_a_coverage_decision": NOT_A_COVERAGE_DECISION,
        "facts": facts,
        "next_step": (
            "Report the state, dates, observation time and reference. If the "
            "caller asks whether a particular loss is covered, offer "
            "open_coverage_question instead of answering from the state."
        ),
    }
    if record.get("lapse_reason"):
        answer["lapse_reason"] = record["lapse_reason"]
    return answer


def claim_status(customer_id: str, claim_number: str, data: Optional[dict] = None) -> dict:
    data = data or load_data()
    number = normalise_id(claim_number)
    record = data["claims"].get(number)
    facts = facts_for(record, customer_id, data)
    reason = evaluate(facts)
    if reason == "wrong_policy_subject":
        return _blocked(reason, claim_number=number, facts=facts)
    if reason == "stale_claim_status":
        return _blocked(
            reason,
            claim_number=number,
            facts=facts,
            last_known={
                "stage": record["stage"],
                "stage_recorded_at": record["stage_recorded_at"],
                "observed_at": record.get("observed_at"),
            },
        )
    if reason:
        return _blocked(reason, claim_number=number, facts=facts)
    answer = {
        "status": "answered",
        "decision_type": record["decision_type"],
        "claim_number": number,
        "policy_number": record["policy_number"],
        "loss": record["loss"],
        "stage": record["stage"],
        "stage_recorded_at": record["stage_recorded_at"],
        "observed_at": record["observed_at"],
        "status_reference": status_reference(data, customer_id, number, record["observed_at"]),
        "next_review_step": record["next_review_step"],
        "coverage_decision": record.get("coverage_decision"),
        "facts": facts,
    }
    if record["decision_type"] == "coverage_decision":
        answer["scope_note"] = (
            f"This decision applies to {number} only. It does not decide any "
            "other loss, even on the same policy."
        )
    else:
        answer["not_a_coverage_decision"] = NOT_A_COVERAGE_DECISION
    return answer


def coverage_question(
    customer_id: str,
    policy_number: str,
    loss_description: str,
    data: Optional[dict] = None,
) -> dict:
    """Route a question about a particular loss to the claims service.

    Never returns an outcome. Only the subject rule applies: the policy must
    belong to the caller. Freshness and decision labels govern status answers,
    and this tool gives none.
    """
    data = data or load_data()
    number = normalise_id(policy_number)
    record = data["policies"].get(number)
    facts = facts_for(record, customer_id, data)
    if facts.get("policy_subject_matched") is not True:
        return _blocked("wrong_policy_subject", policy_number=number, facts=facts)
    loss = " ".join(str(loss_description or "").split())[:300]
    return {
        "status": "routed",
        "decision": None,
        "reference": f"HC-CQ-{_digest(customer_id, number, loss.lower())}",
        "policy_number": number,
        "policy_state": record["state"],
        "loss_description": loss,
        "decision_owner": "HarborCover claims service",
        "next_review_step": (
            "A claims handler reviews the question and replies within two "
            "business days. No decision has been made."
        ),
    }


def case_team_callback(
    customer_id: str,
    claim_number: str,
    data: Optional[dict] = None,
) -> dict:
    """Recovery route when a status cannot be answered from current data."""
    data = data or load_data()
    number = normalise_id(claim_number)
    record = data["claims"].get(number)
    facts = facts_for(record, customer_id, data)
    if facts.get("policy_subject_matched") is not True:
        return _blocked("wrong_policy_subject", claim_number=number, facts=facts)
    return {
        "status": "routed",
        "reference": f"HC-CT-{_digest(customer_id, number, 'case-team')}",
        "claim_number": number,
        "route": "claims case team callback",
        "last_known": {
            "stage": record["stage"],
            "stage_recorded_at": record["stage_recorded_at"],
            "observed_at": record.get("observed_at"),
        },
        "next_review_step": "The case team calls back within one business day.",
    }


def caller_profile(customer_id: str = DEMO_CUSTOMER_ID, data: Optional[dict] = None) -> dict:
    data = data or load_data()
    person = data["customers"][customer_id]
    policies = sorted(
        number for number, p in data["policies"].items() if p["customer_id"] == customer_id
    )
    claims = sorted(
        number for number, c in data["claims"].items() if c["customer_id"] == customer_id
    )
    return {
        "customer_id": customer_id,
        "first_name": person["first_name"],
        "last_name": person["last_name"],
        "policy_numbers": policies,
        "claim_numbers": claims,
    }
