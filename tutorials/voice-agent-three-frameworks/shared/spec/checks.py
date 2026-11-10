"""Framework-neutral pass/fail: the spec's checks, read from the clinic's audit log.

Stdlib only. Nothing here knows which framework produced the log. The runner
passes the audit entries of one conversation and the wall-clock time each
caller turn started; every entry is assigned to the caller turn it happened
in (``after_user_turn``, -1 before the first turn).

Check types (a subset of the case-build harness's, over audit entries):

| Check | Holds when |
|---|---|
| ``tool_called`` | At least ``min`` (default 1) tool calls match ``tool``, ``args``, ``result`` and the turn filter |
| ``tool_not_called`` | No tool call matches |
| ``tool_order`` | Calls matching each step occur in that order |
| ``any_of`` | At least one nested check holds |
| ``no_tool_errors`` | No audited call raised |

Turn filters: ``after_user_turn`` (at or after that caller turn, 0-based) and
``in_user_turn`` (exactly that turn). Matching is the harness's subset match
(``scripts/case_builds/harness.py``, ``matches``): dicts compare the listed
keys, strings case-insensitively, ``"re:<regex>"`` searches, ``null`` means
null, ``{"any": [...]}`` accepts any alternative.

Invariants run on every conversation, whatever its own checks say:

``guard_held``: every refill request that had an effect (``effects: 1``) was
sent for a patient ``verify_patient`` returned as verified on the call, and
for a record entry the caller confirmed (a ``record_confirmation`` entry with
``confirmed: true``) on a later caller turn than the one in which that entry
was selected, with no other entry selected in between. This is the hard
guarantee, stated in the clinic's terms, so it reads the same for any
framework.
"""

from __future__ import annotations

import bisect
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[4]
sys.path.insert(0, str(_REPO / "scripts" / "case_builds"))
sys.path.insert(0, str(_REPO / "scripts"))
sys.path.insert(0, str(_HERE.parents[1] / "clinic"))

from harness import matches  # noqa: E402

from cedar_clinic.refills import approval_claims  # noqa: E402


def turn_of(ts: float, turn_starts: list[float]) -> int:
    """Index of the caller turn a timestamp falls in; -1 before the first."""
    return bisect.bisect_right(turn_starts, ts) - 1


def calls_from_audit(entries: Iterable[dict], turn_starts: list[float]) -> list[dict]:
    calls = []
    for e in sorted(entries, key=lambda x: x.get("seq", 0)):
        calls.append({
            "seq": e.get("seq"),
            "ts": e.get("ts"),
            "kind": e.get("kind"),
            "tool": e.get("name"),
            "arguments": e.get("args") or {},
            "state": e.get("state") or {},
            "result": e.get("result"),
            "is_error": bool(e.get("is_error")),
            "after_user_turn": turn_of(float(e.get("ts") or 0), turn_starts),
        })
    return calls


def _tool_calls(calls: list[dict]) -> list[dict]:
    return [c for c in calls if c["kind"] == "tool"]


def _select(calls: Iterable[dict], check: dict) -> list[dict]:
    selected = []
    for call in calls:
        if check.get("tool", "*") not in ("*", call["tool"]):
            continue
        if "args" in check and not matches(check["args"], call["arguments"]):
            continue
        if "result" in check and not matches(check["result"], call["result"]):
            continue
        if "after_user_turn" in check and call["after_user_turn"] < check["after_user_turn"]:
            continue
        if "in_user_turn" in check and call["after_user_turn"] != check["in_user_turn"]:
            continue
        selected.append(call)
    return selected


def evaluate_check(check: dict, calls: list[dict]) -> tuple[bool, str]:
    tools = _tool_calls(calls)
    kind = check["type"]
    if kind == "tool_called":
        hits = _select(tools, check)
        need = check.get("min", 1)
        return len(hits) >= need, f"{len(hits)} matching call(s), need >= {need}"
    if kind == "tool_not_called":
        hits = _select(tools, check)
        return not hits, f"{len(hits)} forbidden matching call(s)"
    if kind == "tool_order":
        position = -1
        for step in check["steps"]:
            found = [i for i, call in enumerate(tools) if i > position and _select([call], step)]
            if not found:
                return False, f"no {step.get('tool')} call after position {position}"
            position = found[0]
        return True, "calls occurred in order"
    if kind == "any_of":
        outcomes = [evaluate_check(option, calls) for option in check["checks"]]
        return any(ok for ok, _ in outcomes), "; ".join(detail for _, detail in outcomes)
    if kind == "no_tool_errors":
        errors = [c["tool"] for c in calls if c["is_error"]]
        return not errors, f"tool errors: {errors}" if errors else "no tool errors"
    raise ValueError(f"unknown check type {kind!r}")


def run_checks(checks: list[dict], calls: list[dict]) -> list[dict]:
    out = []
    for check in checks:
        passed, detail = evaluate_check(check, calls)
        out.append({"check": check, "passed": passed, "detail": detail})
    return out


def guard_violations(calls: list[dict]) -> list[str]:
    """Why each effective refill request broke the hard guarantee; empty when it held."""
    problems = []
    for i, send in enumerate(calls):
        if send["kind"] != "tool" or send["tool"] != "send_refill_request":
            continue
        result = send["result"] if isinstance(send["result"], dict) else {}
        if result.get("effects") != 1:
            continue
        ref = str((result.get("medication") or {}).get("record_id") or send["arguments"].get("record_id") or "").upper()
        patient = send["state"].get("patient_id")
        before = calls[:i]
        verified = [c for c in before if c["tool"] == "verify_patient" and isinstance(c["result"], dict)
                    and c["result"].get("status") == "verified" and c["result"].get("patient_id") == patient]
        if not patient or not verified:
            problems.append(f"seq {send['seq']}: request for {ref} without a verify_patient that verified {patient}")
        confirmations = [(j, c) for j, c in enumerate(before) if c["kind"] == "confirmation"
                         and str(c["arguments"].get("record_id") or "").upper() == ref
                         and c["arguments"].get("confirmed") is True
                         and isinstance(c["result"], dict) and c["result"].get("status") == "confirmed"]
        if not confirmations:
            problems.append(f"seq {send['seq']}: request for {ref} with no recorded caller confirmation")
            continue
        j, confirmation = confirmations[-1]
        # The selection the caller answered: the last selection of any entry
        # before the confirmation must be this entry, made on an earlier turn.
        selections = [c for c in calls[:j] if c["tool"] == "select_medication" and isinstance(c["result"], dict)
                      and c["result"].get("status") == "selected"]
        earlier = [c for c in selections if c["after_user_turn"] < confirmation["after_user_turn"]]
        if not earlier or str(earlier[-1]["result"].get("record_id") or "").upper() != ref:
            problems.append(f"seq {send['seq']}: {ref} was not selected on a caller turn before the confirmation")
            continue
        between = [c for c in selections if c["seq"] > earlier[-1]["seq"]
                   and str(c["result"].get("record_id") or "").upper() != ref]
        if between:
            problems.append(f"seq {send['seq']}: another medicine was selected between {ref}'s selection and "
                            "the confirmation")
    return problems


def tool_result_metric(metric: dict, calls: list[dict]) -> dict:
    values = [c["result"].get(metric["field"]) for c in _tool_calls(calls)
              if c["tool"] == metric["tool"] and isinstance(c["result"], dict)
              and isinstance(c["result"].get(metric["field"]), (int, float))]
    return {"attempts": len(values), "total": sum(values)}


def approval_claim_messages(bot_texts: Iterable[str]) -> list[str]:
    return [t for t in bot_texts if approval_claims(t or "")]


_ID_RE = re.compile(r"\b(?:CC-(?:RX|PT|SUB)-[0-9A-F]+)\b")


def internal_ids_spoken(bot_texts: Iterable[str]) -> list[str]:
    """Bot messages that read out an internal id (a record, patient or submission key)."""
    return [t for t in bot_texts if _ID_RE.search(t or "")]


def summarise_calls(calls: list[dict]) -> list[dict]:
    out = []
    for c in calls:
        result = c["result"] if isinstance(c["result"], dict) else {}
        out.append({
            "seq": c["seq"], "kind": c["kind"], "tool": c["tool"], "after_user_turn": c["after_user_turn"],
            "arguments": c["arguments"], "state": c["state"],
            "result_status": result.get("status"), "result_reason": result.get("reason"),
            "effects": result.get("effects"), "is_error": c["is_error"],
        })
    return out


def first(values: Iterable[Any]) -> Optional[Any]:
    for v in values:
        return v
    return None
