# shared/clinic: the Cedar Clinic domain

`cedar_clinic` is the fictional clinic's refill-request domain as a plain
Python package with no dependencies and no framework imports. All three
agents install it and call the same functions, so records, matching,
receipts and the contract's rules are identical across the comparison and are
not counted as any framework's code.

It is lifted from
[`examples/mantle-voice-healthcare-refill-request-gpt-local/lib/`](../../../../examples/mantle-voice-healthcare-refill-request-gpt-local/lib/),
with three changes: an audit log of every call, a confirmation rule, and the
tool descriptions and instruction text moved here so every agent uses the
same words.

```bash
python3 -m unittest discover -s tests -v    # offline: no model, no network
```

## Modules

| Module | What it holds |
|---|---|
| `cedar_clinic.refills` | Records, matching, the contract's rules (`evaluate`), receipts, `approval_claims` (the case metric). Pure functions over a per-conversation `ClinicService` |
| `cedar_clinic.tools` | The API every agent calls. Each function takes the conversation id, the state the framework keeps, and the model's arguments, and appends an audit entry. `TOOL_SPECS` holds the model-facing names, descriptions and parameters |
| `cedar_clinic.audit` | `AuditLog`: one JSON line per call, to memory and to the file named by `CEDAR_AUDIT_LOG` |
| `cedar_clinic.instructions` | `PERSONA`, `RULES`, `VOICE_RULES`, `GREETING`, `PROCEDURE`, `system_prompt()` |
| `cedar_clinic/fixtures/` | The fictional records and the vendored casebook contract |

## The tool API

```python
from cedar_clinic import tools

r = tools.verify_patient(conv, full_name, date_of_birth)
#   {"status": "verified", "patient_id": "CC-PT-1001", "first_name": ...} or not_verified
#   Keep r["patient_id"] in state the model cannot write. Show the model tools.for_model(r).
r = tools.select_medication(conv, patient_id, medication_name)
#   {"status": "selected", "record_id", "medication_label", "confirmation_question"} or blocked
tools.record_confirmation(conv, record_id, confirmed, mechanism="...", question=..., answer=...)
#   Not a model tool. Call it from your confirmation step with the caller's answer.
r = tools.send_refill_request(conv, patient_id, selected_record_id, record_id, patient_note)
#   succeeded / pending / blocked; receipts always carry approved: None
r = tools.check_request_status(conv, patient_id, submission_key)
r = tools.route_clinical_question(conv, patient_id, question, record_id)
```

`conv` is the conversation id. On the voice path it is the id the spec
runner sends in the `X-Rasa-Sender-Id` header (see
[`../web/PROTOCOL.md`](../web/PROTOCOL.md)); use it unchanged so the audit log
joins on it.

Model-facing tools are the five in `tools.TOOL_SPECS`. Offer the model those
names, descriptions and parameters verbatim; `tools.json_schema(name)` gives
an OpenAI-style function schema. No parameter takes a dose, strength or
quantity, and a test fails if one does.

## Rules the library enforces

`send_refill_request` sends only when all of these hold, in this order:

| Rule | Fails with | Decided from |
|---|---|---|
| `patient_identity_verified` (contract) | `patient_not_verified` | The `patient_id` you pass was returned `verified` by `verify_patient` on this conversation |
| `recorded_medication_selected` (contract) | `medication_not_resolved` | The `selected_record_id` you pass equals `record_id`, and the entry is the verified patient's, active and not controlled |
| `caller_confirmed_medication` (this library) | `medication_not_confirmed` | `record_confirmation(..., confirmed=True)` was called for this entry after it was last selected. Any `select_medication` call clears it |
| `review_request_acknowledged` (contract, receipt) | `pending` / `review_request_not_received` | The request service reads the request back |

What the library cannot check is where your state came from and how the
confirmation was obtained: whether `patient_id` and `selected_record_id` came
from state only a tool writes, and whether `record_confirmation` was called
with the caller's own answer to the read-back question on a later turn than
the selection. That is each framework's refill guard, and the spec checks it
from the audit log (see [`../spec/README.md`](../spec/README.md)).

## The audit log

Set `CEDAR_AUDIT_LOG=/path/audit.jsonl` in the agent process. Each call
appends:

```json
{"seq": 4, "ts": 1790000000.12, "conversation_id": "...", "kind": "tool",
 "name": "send_refill_request",
 "args": {"record_id": "CC-RX-2041", "patient_note": ""},
 "state": {"patient_id": "CC-PT-1001", "selected_record_id": "CC-RX-2041"},
 "result": {"status": "succeeded", "effects": 1, "approved": null, ...}}
```

`kind` is `tool` for the five model tools and `confirmation` for
`record_confirmation`, whose `state` carries the `mechanism`, `question` and
`answer` you passed. The spec runner reads this file and nothing else to
decide pass or fail.
