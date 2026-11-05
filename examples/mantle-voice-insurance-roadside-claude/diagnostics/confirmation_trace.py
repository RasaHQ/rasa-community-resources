"""Offline causal guard trace over the existing fictional roadside example.
No Rasa runtime, model, network, real provider or account action.
"""
import argparse
import ast
import dataclasses
import hashlib
import inspect
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parent.parent)
parser.add_argument('--tests', choices=['full', 'drop_location', 'drop_service', 'drop_tag'],
                    help='Run the guard suite with one in-process diagnostic mutation; failing tests exit1.')
args = parser.parse_args()
project = args.project.resolve()
sys.path.insert(0, str(project))
from lib import roadside as hc

class UserUttered:
    def __init__(self, text): self.text = text

class BotUttered:
    def __init__(self, text):
        self.text = text
        self.metadata = {hc.UTTER_ACTION_KEY: hc.CONFIRM_UTTER}

def confirmation(service, draft, answered=True):
    template = (project / 'skills/roadside_dispatch/responses.yml').read_text()
    question = ' '.join(template.split('- text: >', 1)[1].split())
    for key, value in hc.memory_values(service, draft).items():
        question = question.replace('{' + key + '}', value)
    events = [BotUttered(question)]
    if answered: events.append(UserUttered('Yes.'))
    return hc.conversation_from_events(events)

original_guard = hc._location_confirmed
original_source = inspect.getsource(original_guard)
mutations = {'full': None, 'drop_location': 1, 'drop_service': 2, 'drop_tag': 0}

def guard_for(name):
    if name == 'full': return original_guard
    tree = ast.parse(original_source)
    result = next(n for n in ast.walk(tree) if isinstance(n, ast.Return))
    assert isinstance(result.value, ast.BoolOp) and len(result.value.values) == 4
    expected = ['pending_draft_ref', 'location', 'service', 'confirmation_answered']
    assert all(word in ast.unparse(term) for word, term in zip(expected, result.value.values))
    del result.value.values[mutations[name]]
    ast.fix_missing_locations(tree)
    scope = dict(hc.__dict__)
    exec(compile(tree, '<single-clause guard mutation>', 'exec'), scope)
    return scope['_location_confirmed']

if args.tests:
    import unittest
    hc._location_confirmed = guard_for(args.tests)
    suite = unittest.defaultTestLoader.discover(str(project / 'tests'), pattern='test_guard.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    hc._location_confirmed = original_guard
    sys.exit(0 if result.wasSuccessful() else 1)

histories = {
    'location_then_bad_service': {'location': 'exit 16', 'service_needed': 'not-a-service'},
    'location_then_bad_vehicle': {'location': 'exit 16', 'vehicle_ref': 'not-a-vehicle'},
    'service_then_bad_vehicle': {'service_needed': 'jump_start', 'vehicle_ref': 'not-a-vehicle'},
    'unchanged_confirmed': {},
    'unchanged_unanswered': {},
    'unchanged_wrong_tag': {},
}
rows=[]
for mutation in mutations:
    hc._location_confirmed = guard_for(mutation)
    for name, changes in histories.items():
        service = hc.RoadsideService('guard-trace-' + name)
        result, draft = hc.start_dispatch_draft(service, 'HC-AU-517306', 'VEH-5173-1', 'tow', 'exit 14')
        assert draft is not None, result
        before = dataclasses.asdict(draft)
        memory = hc.memory_values(service, draft)
        conversation = confirmation(service, draft, name != 'unchanged_unanswered')
        if name == 'unchanged_wrong_tag': memory['pending_draft_ref'] = 'different-draft v1'
        update = None
        if changes:
            update, returned = hc.update_dispatch_draft(service, draft.draft_id, **changes)
            assert returned is None  # Actual wrapper skips _write_draft on this branch.
        after = dataclasses.asdict(draft)
        labels = service.labels(draft)
        question = conversation.confirmation_question or ''
        checks = {'tag_matches': memory['pending_draft_ref'] == draft.tag,
                  'location_in_question': labels['location'] in question,
                  'service_in_question': labels['service'] in question,
                  'answered': conversation.confirmation_answered}
        dispatch = hc.request_dispatch(service, draft.draft_id, memory, conversation)
        rows.append({'mutation':mutation, 'history':name, 'update_status':None if update is None else update['status'],
                     'before':before, 'after':after, 'draft_unchanged':before == after, 'checks':checks,
                     'result_status':dispatch['status'], 'reason':dispatch.get('reason'),
                     'dispatch_count':len(service.dispatches), 'dispatch_records':service.dispatches})
hc._location_confirmed = original_guard
print(json.dumps({'project':str(project),'library_sha256':hashlib.sha256((project/'lib/roadside.py').read_bytes()).hexdigest(),
                  'scope':'Offline existing-example direct library calls and explicitly single-clause diagnostic mutants; no native framework/model/live provider evidence.',
                  'guard_source':original_source,'rows':rows},indent=2,sort_keys=True))
