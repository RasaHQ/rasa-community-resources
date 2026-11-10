"""Print the native caller/specialist history matrix with scripted replies."""
import json
from network_specialist.context_exercise import inspect_pair

for preserve_context in (False, True):
    for record_direct_tool_call in (False, True):
        print(json.dumps(inspect_pair(preserve_context, record_direct_tool_call)))
