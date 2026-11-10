"""Credential-free native completion/failure comparison; scripted model replies."""

import json
from claim_crew.native_fixture import create_fixture
from claim_crew.acceptance import inspect_result

for unavailable in (False, True):
    result = create_fixture("vehicle", unavailable=unavailable).kickoff()
    print(
        json.dumps(
            {
                "source_unavailable": unavailable,
                "final_output_present": bool(result.raw),
                "tasks": [t.name for t in result.tasks_output],
                "recorded_tool_failures": len(result.tool_failures),
                "handoff_status": inspect_result(result, "vehicle")["status"],
            },
            sort_keys=True,
        )
    )
