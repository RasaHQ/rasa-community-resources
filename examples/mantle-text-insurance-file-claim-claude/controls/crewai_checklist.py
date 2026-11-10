"""Offline CrewAI advice/claims-service boundary; never a live chat receipt.

The worker runs its real scripted native CrewAI fixture. Claim submissions call
this example's actual Python service, with constructed confirmation events.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(REPO / "tutorials/frameworks-with-rasa/crewai-transport"))
from lib import claims as hc  # noqa: E402
from crew_transport import CrewProcess, checked_response  # noqa: E402


def advice_text(record: dict) -> str:
    """Only checked public guidance is eligible for this constructed transcript."""
    if checked_response(record, "vehicle").get("status") != "ready":
        raise ValueError("The native crew did not return checked vehicle advice")
    return "Public vehicle-claim guidance: " + ", ".join(record["checklist"]["documents"]) + ". This advice does not confirm upload status or file a claim."


def run_scenario(record: dict, photo_state: str, *, mutant: bool = False) -> dict:
    advice = advice_text(record)
    if photo_state not in {"processing", "received", "not_provided"}:
        raise ValueError("unknown photo state")
    data = hc.load_data()
    data["uploads"]["bumper-1.jpg"]["states"] = [photo_state]
    service = hc.ClaimsIntake(data)
    attachments = ("bodyshop-estimate.pdf",) if photo_state == "not_provided" else ("bumper-1.jpg", "bodyshop-estimate.pdf")
    user = hc.UserMessage("I had a collision; these are my uploads.", attachments)
    conversation = hc.Conversation((user,))
    original_material = hc.material

    def crew_list_material(*args, **kwargs):
        # Deliberately wrong boundary: public crew labels determine which
        # service-owned required items count. Never used by production tools.
        material = original_material(*args, **kwargs)
        crew_keys = {"repair_estimate" for label in record["checklist"]["documents"] if label == "Repair estimate"}
        selected = [row for row in material["required"] if row["key"] in crew_keys]
        assert selected, "Mutation must check a real known requirement, not an empty list"
        material["required_attachment_state_known"] = all(row["state"] != "unknown" for row in selected)
        return material

    with patch.object(hc, "material", crew_list_material) if mutant else nullcontext():
        started, draft = hc.start_claim_draft(service, hc.SESSION_CUSTOMER_ID, "crew-claims-control", conversation,
                                            "HC-AU-778210", "collision", "2026-09-26", "A collision damaged my bumper")
        if draft is None:
            raise AssertionError(started)
        memory = hc.memory_values(service, draft)
        template = " ".join((PROJECT / "skills/file_claim/responses.yml").read_text().split("- text: >", 1)[1].split())
        question = re.sub(r"\{(\w+)\}", lambda match: memory[match[1]], template)
        # Construct a confirmed direct-tool call even when the engine would hide
        # the tool. This isolates the service guard; no engine exchange is claimed.
        confirmed = hc.Conversation((user, hc.UserMessage("Yes, that is accurate.")), question, True)
        result = hc.submit_claim_report(service, hc.SESSION_CUSTOMER_ID, memory, confirmed, draft.draft_id)
    reconciled = hc.check_claim_submission(service, hc.SESSION_CUSTOMER_ID, draft.draft_id) if service.submissions else None
    return {"reconciled": reconciled, "photo_state": photo_state, "mutant": mutant, "advice_text": advice,
            "service_requirements": list(data["loss_types"]["collision"]["required"]),
            "draft": started, "submission": result, "submission_count": len(service.submissions)}


def assert_contract(rows: list[dict]) -> None:
    by_state = {row["photo_state"]: row for row in rows}
    processing = by_state["processing"]
    assert processing["submission"]["status"] == "blocked", "Processing damage photo must block submission"
    assert processing["submission_count"] == 0, "A refused request must create no submission"
    for state in ("received", "not_provided"):
        assert by_state[state]["submission"]["status"] == "pending", f"Known {state} state remains allowed intake; fixture acknowledgement is lost"
        assert by_state[state]["reconciled"]["status"] == "acknowledged", "Read back the same submission; do not file twice"
        assert by_state[state]["submission_count"] == 1
    follow_up = by_state["not_provided"]["submission"].get("follow_up_required", [])
    assert any(item.get("why") == "not provided" for item in follow_up), "Missing photos must remain explicit follow-up"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crew-python", help="Owned managed interpreter for the existing CrewAI project")
    parser.add_argument("--mutant", action="store_true", help="Deliberately substitute the crew checklist; the unchanged contract must fail")
    args = parser.parse_args()
    record = CrewProcess(python=args.crew_python, fixture=True).checklist("vehicle", "Which public documents should I prepare for my vehicle claim?")
    if record.get("status") != "ready":
        print(json.dumps({"status": "NOT_RUN", "reason": "native_crew_fixture_unavailable", "worker_result": record}, sort_keys=True))
        return 2
    rows = [run_scenario(record, state, mutant=args.mutant) for state in ("processing", "received", "not_provided")]
    print(json.dumps({"scope": "native scripted CrewAI plus direct claims-service control; constructed confirmation, no live Mantle/model conversation", "crew": record, "results": rows}, indent=2, sort_keys=True))
    try:
        assert_contract(rows)
    except AssertionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
