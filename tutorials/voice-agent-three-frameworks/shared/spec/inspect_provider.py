"""Print a compact view of recorded provider inputs, never a new measurement."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('framework', choices=['crewai', 'livekit'])
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
folder = root / 'results' / args.framework / 'offline-contract-20261003'
drift = json.loads((folder / 'provider-drift.json').read_text())
checked = json.loads((folder / 'provider-contract.json').read_text())
from cedar_clinic import tools as clinic
observed = drift['observed_provider_request']['tools']
summary = {
    'framework': args.framework,
    'condition': 'localhost fake provider; no model spend',
    'change': drift['source_change'],
    'observed_tool_names': [tool['name'] for tool in observed],
    'observed_send_required': next(tool['parameters']['required'] for tool in observed if tool['name'] == 'send_refill_request'),
    'guarded_send_required': clinic.json_schema('send_refill_request')['parameters']['required'],
    'guarded_tool_schemas_match': checked['tool_schemas_match'],
}
print(json.dumps(summary, indent=2))
