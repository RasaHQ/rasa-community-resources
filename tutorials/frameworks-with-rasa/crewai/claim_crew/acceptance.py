"""Inspect actual CrewOutput task records before exposing a checklist."""

from __future__ import annotations
from crewai.crews.crew_output import CrewOutput
from pydantic import BaseModel, ConfigDict, ValidationError


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_type: str
    source_id: str
    revision: str
    required_documents: list[str]


class Checklist(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_type: str
    documents: list[str]


PUBLIC_SOURCES = {
    "vehicle": SourceRecord(
        claim_type="vehicle",
        source_id="HC-V-101",
        revision="2026-10-11",
        required_documents=["Incident details", "Repair estimate"],
    ),
    "travel": SourceRecord(
        claim_type="travel",
        source_id="HC-T-201",
        revision="2026-10-11",
        required_documents=["Booking receipt", "Cancellation notice"],
    ),
}


def inspect_result(result: CrewOutput, claim_type: str) -> dict:
    incomplete = {"status": "incomplete", "reason": "research_not_complete"}
    if claim_type not in PUBLIC_SOURCES or result.has_tool_failures:
        return incomplete
    tasks = {task.name: task for task in result.tasks_output}
    if len(result.tasks_output) != 2 or set(tasks) != {"source", "checklist"}:
        return incomplete
    try:
        source = SourceRecord.model_validate(tasks["source"].json_dict)
        checklist = Checklist.model_validate(tasks["checklist"].json_dict)
    except ValidationError:
        return incomplete
    expected = PUBLIC_SOURCES[claim_type]
    if (
        source != expected
        or checklist.claim_type != claim_type
        or checklist.documents != expected.required_documents
    ):
        return incomplete
    return {
        "status": "ready",
        "source": source.model_dump(),
        "checklist": checklist.model_dump(),
    }
