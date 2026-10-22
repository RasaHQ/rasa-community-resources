"""Offline policy builder, real protected gate, measurements and a controlled recovery fault.
sow: software-factories-masterclass-SOW-02
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

import judge
import measure
import recover
import scripted_builder

ROOT = Path(__file__).resolve().parent
TASK = ROOT / 'tasks/c-recovery-attempts.json'


def build(name):
    attempt = ROOT / 'attempts' / name
    code = scripted_builder.main(TASK, attempt)
    if code:
        return code
    output = ROOT / ('examples' if name == 'see' else 'runs') / name
    output.parent.mkdir(exist_ok=True)
    code = judge.main(TASK, attempt, output)
    if code == 0:
        (output / 'meta.json').write_text(json.dumps({'agent':'SCRIPTED data-only teaching builder',
            'human_interventions':0, 'provider_calls':0, 'note':'Cost and time were not measured; do not invent them.'},indent=2)+'\n')
    return code


def measurements():
    attempt = ROOT / 'attempts/baseline'
    if attempt.exists() or (ROOT / 'runs/baseline').exists():
        print('Measurement examples already exist; keep their evidence.')
        return 2
    shutil.copytree(ROOT / 'product', attempt / 'product')
    code = judge.main(TASK, attempt, ROOT / 'runs/baseline')
    if code != 1:
        print('The baseline should fail the reader\'s changed request; no comparison claimed.')
        return 2
    print('CONTROLLED teaching cases, not independent model trials or a model ranking.')
    return measure.report(ROOT / 'runs', controlled=True)


def recovery():
    candidate = ROOT / 'attempts/mine'
    if not (ROOT / 'runs/mine/decision.json').exists():
        print('Build your accepted attempt first.')
        return 2
    from factory_engine.factory import digest_tree
    gate = json.loads((ROOT / 'runs/mine/decision.json').read_text())
    if gate['decision'] != 'ACCEPT' or gate['candidate_digest'] != digest_tree(candidate):
        print('The configuration differs from the checked proposal; build a fresh attempt.')
        return 2
    policy = json.loads((candidate / 'product/recovery.json').read_text())
    attempts = policy['max_attempts']
    if type(attempts) is not int or attempts not in (1,2,3) or policy['retry_rejected'] is not False:
        return 2
    print('CONTROLLED fault: first attempt crashes before starting a gate. Later attempts use the real protected gate.')
    actual = recover.attempt
    calls = []
    def first_crash(*args):
        calls.append(True)
        if len(calls) == 1:
            return 'CRASHED', 'injected teaching failure; no gate or provider was run'
        return actual(*args)
    # Injection changes only the recovery fault; no ACCEPT result is scripted.
    recover.attempt = first_crash
    try:
        code = recover.main(TASK, candidate, ROOT / 'ledger.json', max_attempts=attempts)
    finally:
        recover.attempt = actual
    print('Recovery attempts executed in this invocation:', len(calls))
    return code


def check():
    try:
        task = json.loads(TASK.read_text())
        decision = json.loads((ROOT / 'runs/mine/decision.json').read_text())
        if type(task['target_attempts']) is not int or task['target_attempts'] not in (1,3) or decision['decision'] != 'ACCEPT':
            raise ValueError()
        from factory_engine.factory import digest_tree
        if (decision['candidate_digest'] != digest_tree(ROOT / 'attempts/mine')
            or decision['baseline_digest'] != digest_tree(ROOT / 'product')
            or decision['acceptance_sha256'] != recover.hashlib.sha256((ROOT / 'acceptance/c_recovery_policy.py').read_bytes()).hexdigest()
            or decision['environment_sha256'] != recover.hashlib.sha256((ROOT / 'environment.json').read_bytes()).hexdigest()):
            raise ValueError()
        entries = json.loads((ROOT / 'ledger.json').read_text())
        expected = 'ESCALATE' if task['target_attempts'] == 1 else 'ACCEPT'
        relevant = [entry for entry in entries.values() if entry['context']['task_sha256'] == recover.hashlib.sha256(TASK.read_bytes()).hexdigest()]
        if (len(relevant) != 1 or relevant[0]['final'] != expected
            or relevant[0]['context']['candidate_sha256'] != decision['candidate_digest']
            or relevant[0]['context']['verifier_sha256'] != recover.hashlib.sha256((ROOT / 'factory_engine/factory.py').read_bytes()).hexdigest()
            or relevant[0]['context']['baseline_sha256'] != decision['baseline_digest']
            or relevant[0]['context']['suite_sha256'] != decision['acceptance_sha256']
            or relevant[0]['context']['profile_sha256'] != decision['environment_sha256']):
            raise ValueError()
        events = relevant[0]['attempts']
        if len(events) != (1 if expected == 'ESCALATE' else 2) or events[0]['outcome'] != 'CRASHED':
            raise ValueError()
        baseline = json.loads((ROOT / 'runs/baseline/decision.json').read_text())
        if (baseline['decision'] != 'REJECT' or baseline['baseline_digest'] != decision['baseline_digest']
            or baseline['acceptance_sha256'] != decision['acceptance_sha256']):
            raise ValueError()
    except (OSError, ValueError, KeyError, TypeError):
        print('NOT DONE: choose your request, build, measure and recover first.')
        return 1
    print('ch08 OK: protected proposal ACCEPT, actual baseline REJECT, bounded recovery ' + expected)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('see','build','measure','recover','check'))
    action = parser.parse_args().action
    return {'see':lambda:build('see'),'build':lambda:build('mine'),
            'measure':measurements,'recover':recovery,'check':check}[action]()


if __name__ == '__main__':
    raise SystemExit(main())
