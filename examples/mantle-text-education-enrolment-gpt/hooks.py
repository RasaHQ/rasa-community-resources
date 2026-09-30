"""Output guard: no received form described as an admission or an aid award.

The tools already keep receipt and decision apart: lookup_application and
record_enquiry return ``decision: null`` unless the responsible team issued
one, and no tool takes a decision or a deadline. This hook is the second line,
for the words. It reads every model response before the applicant sees it and
sends it back when it:

- says aid, funding or a scholarship is awarded, approved, secured or
  confirmed, and no tool result in this conversation carries an aid or
  scholarship award (``lib.enrolment.AID_CLAIM_PATTERN``);
- says the applicant is admitted, and no tool result carries an admission
  offer (``ADMISSION_CLAIM_PATTERN``);
- grants or announces a deadline extension, which no tool can do
  (``EXTENSION_PATTERN``).

After two consecutive retries the text is replaced with a fixed answer built
from tool data. A negation or hedge earlier in the same sentence ("no aid
decision has been made", "until the office confirms it") voids a match; the
hedge list matches straight and typographic apostrophes, because GPT-5.5
writes "can’t" with U+2019.

Mantle hands ``modify_tool_result`` the tool's result as serialized JSON text,
not a dict (found in the HarborCover policy-status build), so it is parsed. A
confirmed gated tool reaches the hook as ``resolve_tool_confirmation`` (found
in the HarborCover quote build), so results are read by their fields, not by
tool name.

Each intervention is logged as ``pine.words_guard`` with the sender id, so the
case-build harness counts how often the model tried.
"""

from __future__ import annotations

import json
from collections import defaultdict

import structlog

from lib.enrolment import fallback_text, remember, unsupported_claims
from rasa.mantle.hooks import (
    ModelResponsePayload,
    RetryModel,
    ToolResultPayload,
    modify_model_response,
    modify_tool_result,
)

log = structlog.get_logger()

MAX_CONSECUTIVE_RETRIES = 2
# The `no-words-guard` variant in case-build/conversations.json sets this to False.
ENABLED = True

# Per conversation, in process memory: what the tools said about each
# application, and consecutive retries.
_records: dict[str, dict[str, dict]] = defaultdict(dict)
_retries: dict[str, int] = defaultdict(int)


def _as_dict(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def feedback(records: dict[str, dict], claims: list[str]) -> str:
    if not records:
        return (
            f"Your draft said {claims[0]!r}, but no application record has been read in this conversation. "
            "Rewrite it without saying anyone is admitted, that aid or a scholarship is awarded, approved or "
            "secured, or that a deadline has moved."
        )
    lines = "; ".join(f"{ref}: {v.get('stage_label') or 'no confirmed stage'}, {v.get('decision_line')}"
                      for ref, v in sorted(records.items()))
    return (
        f"Your draft said {claims[0]!r}, which the records do not support. Records: {lines}. Rewrite it: a "
        "received or submitted form is not a decision, and no deadline can be extended here. Give the stage and "
        "the decision line exactly as the records do."
    )


@modify_tool_result()
async def remember_records(payload: ToolResultPayload) -> ToolResultPayload:
    remember(_records[payload.sender_id], _as_dict(payload.value))
    return payload


@modify_model_response()
async def block_decision_claims(payload: ModelResponsePayload) -> ModelResponsePayload:
    if not ENABLED:
        return payload
    text = payload.text or ""
    records = _records.get(payload.sender_id, {})
    claims = unsupported_claims(text, records)
    if not claims:
        _retries.pop(payload.sender_id, None)
        return payload
    _retries[payload.sender_id] += 1
    attempt = _retries[payload.sender_id]
    if attempt > MAX_CONSECUTIVE_RETRIES:
        log.warning("pine.words_guard", sender_id=payload.sender_id, action="replaced",
                    records_on_file=len(records), matched=claims[0])
        _retries.pop(payload.sender_id, None)
        return payload.model_copy(update={"text": fallback_text(records)})
    log.warning("pine.words_guard", sender_id=payload.sender_id, action="retry", attempt=attempt,
                records_on_file=len(records), matched=claims[0])
    raise RetryModel(feedback(records, claims))
