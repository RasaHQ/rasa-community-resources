"""Compare a deliberately flawed review with an engine-configuration review.

The model-only algorithm is a teaching counterexample, not Mantle behaviour.
An inventory contains settings, not evidence of user approval.
"""
import argparse
import json
from pathlib import Path


def compare(snapshot, skill, tool):
    if not isinstance(snapshot, dict) or snapshot.get('schema') != 1 or snapshot.get('unresolved') != []:
        raise ValueError('A resolved schema-1 inventory is required')
    if not isinstance(snapshot.get('rows'), list) or any(not isinstance(r, dict) for r in snapshot['rows']):
        raise ValueError('Inventory rows must be objects in a list')
    rows = [r for r in snapshot['rows']
            if r.get('skill') == skill and r.get('tool') == tool]
    if not rows:
        raise ValueError('No matching tool bindings')
    if any(not isinstance(r.get('target'), str) or not r['target'] for r in rows):
        raise ValueError('Each binding needs a target')
    if len({r['target'] for r in rows}) != len(rows):
        raise ValueError('Duplicate targets for the selected tool')
    results = []
    for row in rows:
        model = row.get('modelConfirmationSetting')
        engine = row.get('engineConfirmationSetting')
        if type(model) is not bool or type(engine) is not bool:
            raise ValueError('Both recorded lookup settings must be booleans')
        results.append({
            'target': row['target'],
            'modelOnlyReviewRequestsGateFix': not model,
            'engineConfigurationReviewRequestsGateFix': not engine,
            'modelOnlyFalseMissingGateReport': not model and engine,
            'userApprovalObserved': None,
        })
    return {'question': 'Is engine confirmation configured for this binding?',
            'skill': skill, 'tool': tool, 'targets': results,
            'modelOnlyFalseMissingGateReports': sum(
                r['modelOnlyFalseMissingGateReport'] for r in results)}


def main(argv=None):
    from contextlib import redirect_stdout
    import sys
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--project', type=Path)
    source.add_argument('--snapshot', type=Path)
    p.add_argument('--trusted-python', action='store_true')
    p.add_argument('--skill', required=True)
    p.add_argument('--tool', required=True)
    a = p.parse_args(argv)
    if a.project and not a.trusted_python:
        p.error('--trusted-python is required: loading executes project imports')
    if a.snapshot and a.trusted_python:
        p.error('--trusted-python applies only to --project')
    try:
        if a.project:
            from inventory import inventory, check
            with redirect_stdout(sys.stderr):
                actual = inventory(a.project)
            check(actual, actual)
        else:
            actual = json.loads(a.snapshot.read_text())
        result = compare(actual, a.skill, a.tool)
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(json.dumps({'status': 'refused', 'reason': str(error)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
