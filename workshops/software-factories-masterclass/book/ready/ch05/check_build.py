"""Check the reader's task, native outcome and exact exported factory attempt.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'factory_engine'))
import factory


def main():
    if len(sys.argv) != 2:
        print('Use: python check_build.py attempts/mine')
        return 2
    attempt = Path(sys.argv[1])
    if len(attempt.parts) != 2 or attempt.parts[0] != 'attempts' or attempt.parts[1].startswith('.'):
        return 2
    try:
        task = json.loads((ROOT / 'tasks/b-limit-currencies.json').read_text())
        if type(task['limit']) is not int or task['limit'] not in (1, 3):
            raise ValueError('Choose a new limit of 1 or 3, different from the initial example.')
        evidence = ROOT / 'runs' / attempt.name
        native = json.loads((evidence / 'run/native.json').read_text())
        gate = json.loads((evidence / 'run/verification/decision.json').read_text())
        visible = json.loads((evidence / 'scratch/tasks/b-limit-currencies.json').read_text())
        if native['status'] != 'completed' or gate['decision'] != 'ACCEPT' or visible['limit'] != task['limit']:
            raise ValueError('The current task needs a completed builder and protected ACCEPT.')
        if gate['candidate_digest'] != factory.digest_tree(ROOT / attempt):
            raise ValueError('Exported files differ from the checked attempt.')
    except (OSError, ValueError, KeyError):
        print('NOT DONE: choose your limit, build a fresh attempt and keep the checked files unchanged.')
        return 1
    print('ch05 OK: completed builder, protected ACCEPT and exact exported attempt; limit=' + str(task['limit']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
