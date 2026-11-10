"""Keep the native crew in its own environment; validate the conversation DTO."""

import json
import os
from pathlib import Path
import subprocess

SOURCES = {
    "vehicle": {
        "claim_type": "vehicle",
        "source_id": "HC-V-101",
        "revision": "2026-10-11",
        "required_documents": ["Incident details", "Repair estimate"],
    },
    "travel": {
        "claim_type": "travel",
        "source_id": "HC-T-201",
        "revision": "2026-10-11",
        "required_documents": ["Booking receipt", "Cancellation notice"],
    },
}


def checked_response(record, claim_type):
    incomplete = {"status": "incomplete", "reason": "research_unavailable"}
    if (
        not isinstance(claim_type, str)
        or claim_type not in SOURCES
        or not isinstance(record, dict)
    ):
        return incomplete
    if record.get("status") == "incomplete":
        return {"status": "incomplete", "reason": "research_not_complete"}
    expected = SOURCES[claim_type]
    if set(record) != {"status", "source", "checklist"} or record["status"] != "ready":
        return incomplete
    if record["source"] != expected or record["checklist"] != {
        "claim_type": claim_type,
        "documents": expected["required_documents"],
    }:
        return incomplete
    return record


class CrewProcess:
    def __init__(self, python=None, fixture=False, unavailable=False):
        self.root = Path(__file__).resolve().parents[2] / "crewai"
        self.python = (
            python
            or os.getenv("CREW_WORKER_PYTHON")
            or str(self.root / ".venv/bin/python")
        )
        self.fixture = fixture
        self.unavailable = unavailable

    def checklist(self, claim_type, question):
        if (
            not isinstance(claim_type, str)
            or claim_type not in SOURCES
            or not isinstance(question, str)
            or not question.strip()
            or len(question) > 1000
        ):
            return {"status": "incomplete", "reason": "invalid_request"}
        command = [self.python, str(self.root / "worker.py")]
        if self.fixture:
            command.append("--fixture")
        if self.unavailable:
            command.append("--unavailable")
        env = dict(os.environ)
        for key in ("RASA_PRO_LICENSE", "RASA_LICENSE"):
            env.pop(key, None)
        env.update(CREWAI_TELEMETRY_DISABLED="true", OTEL_SDK_DISABLED="true")
        try:
            result = subprocess.run(
                command,
                input=json.dumps({"claim_type": claim_type, "question": question}),
                capture_output=True,
                text=True,
                timeout=25,
                env=env,
            )
            if result.returncode or len(result.stdout) > 65536:
                raise ValueError("worker output")
            return checked_response(json.loads(result.stdout), claim_type)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return {"status": "incomplete", "reason": "research_unavailable"}
