"""Print native policy/representation controls; no model provider is called."""

import json
from claim_crew.failure_signals import failure_matrix

for result in failure_matrix():
    print(json.dumps(result, sort_keys=True))
