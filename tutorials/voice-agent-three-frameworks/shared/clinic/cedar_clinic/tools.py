"""Framework-neutral tool functions: the one API all three agents call.

Each function takes the conversation id first, then any state the framework
holds for the conversation, then the arguments the model supplied. Each one
calls the domain code in ``cedar_clinic.refills`` and appends an audit entry
(``cedar_clinic.audit``) with all three, so the spec can read what happened
from the clinic's side.

State the framework supplies, never the model:

- ``patient_id``: the id ``verify_patient`` returned. It is in the result so
  the framework can keep it; ``for_model`` removes it before the model sees
  the result.
- ``selected_record_id``: the ``record_id`` the latest ``select_medication``
  returned.

``record_confirmation`` is not a model tool. A framework calls it from its
confirmation step with the caller's answer to ``confirmation_question``.

``TOOL_SPECS`` holds the model-facing name, description and parameters of
each tool, so the three agents offer the model the same words.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional

from cedar_clinic import refills
from cedar_clinic.audit import AUDIT, AuditLog

#: Result keys the model never sees.
PRIVATE_KEYS = frozenset({"patient_id"})

confirmation_question = refills.confirmation_question
DECLINED_TEXT = refills.DECLINED_TEXT


def for_model(result: dict) -> dict:
    """The result without the fields only the framework keeps."""
    return {k: v for k, v in result.items() if k not in PRIVATE_KEYS}


def _audit(log: Optional[AuditLog]) -> AuditLog:
    return log or AUDIT


def _service(conversation_id: str) -> refills.ClinicService:
    return refills.service_for(conversation_id)


def _errors_audited(fn: Callable) -> Callable:
    """A call that raises is audited as an error (``is_error: true``) and re-raised."""

    @functools.wraps(fn)
    def wrapper(conversation_id: str, *args: Any, audit: Optional[AuditLog] = None, **kwargs: Any) -> dict:
        try:
            return fn(conversation_id, *args, audit=audit, **kwargs)
        except Exception as exc:
            _audit(audit).record(conversation_id, "tool", fn.__name__, args={"positional": list(map(str, args)),
                                 **{k: str(v) for k, v in kwargs.items()}},
                                 result={"status": "error", "error": f"{type(exc).__name__}: {exc}"},
                                 is_error=True)
            raise

    return wrapper


@_errors_audited
def verify_patient(conversation_id: str, full_name: str, date_of_birth: str, *,
                   audit: Optional[AuditLog] = None) -> dict:
    result = refills.verify_patient(_service(conversation_id), full_name, date_of_birth)
    _audit(audit).record(conversation_id, "tool", "verify_patient",
                         args={"full_name": full_name, "date_of_birth": date_of_birth}, result=result)
    return result


@_errors_audited
def select_medication(conversation_id: str, patient_id: Optional[str], medication_name: str, *,
                      audit: Optional[AuditLog] = None) -> dict:
    result = refills.select_medication(_service(conversation_id), patient_id or None, medication_name)
    _audit(audit).record(conversation_id, "tool", "select_medication",
                         args={"medication_name": medication_name},
                         state={"patient_id": patient_id or None}, result=result)
    return result


@_errors_audited
def send_refill_request(conversation_id: str, patient_id: Optional[str], selected_record_id: Optional[str],
                        record_id: str, patient_note: str = "", *, audit: Optional[AuditLog] = None) -> dict:
    result = refills.send_refill_request(
        _service(conversation_id), patient_id or None, selected_record_id or None, record_id, patient_note,
        conversation_id=conversation_id,
    )
    _audit(audit).record(conversation_id, "tool", "send_refill_request",
                         args={"record_id": record_id, "patient_note": patient_note},
                         state={"patient_id": patient_id or None, "selected_record_id": selected_record_id or None},
                         result=result)
    return result


@_errors_audited
def check_request_status(conversation_id: str, patient_id: Optional[str], submission_key: str, *,
                         audit: Optional[AuditLog] = None) -> dict:
    result = refills.check_request_status(_service(conversation_id), patient_id or None, submission_key)
    _audit(audit).record(conversation_id, "tool", "check_request_status",
                         args={"submission_key": submission_key},
                         state={"patient_id": patient_id or None}, result=result)
    return result


@_errors_audited
def route_clinical_question(conversation_id: str, patient_id: Optional[str], question: str,
                            record_id: Optional[str] = None, *, audit: Optional[AuditLog] = None) -> dict:
    result = refills.route_clinical_question(
        _service(conversation_id), patient_id or None, question, record_id or None, conversation_id,
    )
    _audit(audit).record(conversation_id, "tool", "route_clinical_question",
                         args={"question": question, "record_id": record_id or ""},
                         state={"patient_id": patient_id or None}, result=result)
    return result


@_errors_audited
def record_confirmation(conversation_id: str, record_id: str, confirmed: bool, *, mechanism: str,
                        question: Optional[str] = None, answer: Optional[str] = None,
                        audit: Optional[AuditLog] = None) -> dict:
    """The caller's answer to the read-back question, as the framework obtained it.

    ``mechanism`` names how (for example "rasa requires_confirmation"), and
    ``answer`` is the caller's words when the framework has them. Both go to
    the audit log for the spec's confirmation check.
    """
    result = refills.record_confirmation(_service(conversation_id), record_id, confirmed)
    _audit(audit).record(conversation_id, "confirmation", "record_confirmation",
                         args={"record_id": record_id, "confirmed": confirmed},
                         state={"mechanism": mechanism, "question": question, "answer": answer},
                         result=result)
    return result


# ----------------------------------------------------------------------------
# What the model is told about each tool. Same words in all three agents.
# ----------------------------------------------------------------------------

TOOL_SPECS: dict[str, dict[str, Any]] = {
    "verify_patient": {
        "description": (
            "Verify the caller as a Cedar Clinic patient from their full name and date of "
            "birth, before any medication is looked up or requested. Pass the date as YYYY-MM-DD."
        ),
        "parameters": {
            "full_name": {"type": "string", "description": "The caller's first and last name as they said it."},
            "date_of_birth": {"type": "string", "description": "Date of birth as YYYY-MM-DD, for example 1970-05-21."},
        },
        "required": ["full_name", "date_of_birth"],
    },
    "select_medication": {
        "description": (
            "Find the one medication on the verified patient's record that the caller wants a "
            "refill request for, from the name they said. Returns a record_id, or blocked when "
            "the name matches nothing, several entries, an inactive entry or a controlled medicine."
        ),
        "parameters": {
            "medication_name": {
                "type": "string",
                "description": "The medicine as the caller named it, for example lisinopril or my blue inhaler.",
            },
        },
        "required": ["medication_name"],
    },
    "send_refill_request": {
        "description": (
            "Send a refill request for the one medication returned by select_medication to the "
            "Cedar Clinic prescribing team for review. The medication is read back and the caller "
            "is asked to confirm first. Returns a request reference and the review status. "
            "It never approves, renews or changes a prescription, and takes no dose."
        ),
        "parameters": {
            "record_id": {"type": "string", "description": "The record_id from select_medication, for example CC-RX-2041."},
            "patient_note": {
                "type": "string",
                "description": (
                    "Anything the caller wants the prescribing team to know, in their words, one sentence. "
                    "May be empty."
                ),
            },
        },
        "required": ["record_id"],
    },
    "check_request_status": {
        "description": (
            "Look up a refill request by its original submission_key after send_refill_request "
            "came back pending. Never sends anything."
        ),
        "parameters": {
            "submission_key": {
                "type": "string",
                "description": "The submission_key from send_refill_request, for example CC-SUB-1A2B3C4D.",
            },
        },
        "required": ["submission_key"],
    },
    "route_clinical_question": {
        "description": (
            "Pass a clinical question to the Cedar Clinic prescribing team: a different dose, a new "
            "medicine, a medicine that is no longer active, side effects. Returns a question reference. "
            "It never changes the prescription record and never gives advice."
        ),
        "parameters": {
            "question": {
                "type": "string",
                "description": "The caller's question in one sentence, for example wants to take 20 mg instead of 10 mg.",
            },
            "record_id": {
                "type": "string",
                "description": "The record_id it is about, if select_medication returned one. May be empty.",
            },
        },
        "required": ["question"],
    },
}


def json_schema(name: str) -> dict:
    """OpenAI-style function schema for one tool."""
    spec = TOOL_SPECS[name]
    return {
        "name": name,
        "description": spec["description"],
        "parameters": {
            "type": "object",
            "properties": spec["parameters"],
            "required": list(spec["required"]),
            "additionalProperties": False,
        },
    }
