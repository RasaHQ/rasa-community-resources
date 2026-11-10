"""Inspect direct-tool recording with fresh fixture agents and no model calls."""

import json
from network_specialist.local_runtime import create_specialist
for recording in (True, False):
    specialist = create_specialist()
    result = specialist.tool.inspect_network(
        area="north", question="My private fixture question",
        record_direct_tool_call=recording,
    )
    observation = json.loads(result["content"][0]["text"])
    print(json.dumps({"recording":recording,"source":observation["id"],"messages":len(specialist.messages)}))
