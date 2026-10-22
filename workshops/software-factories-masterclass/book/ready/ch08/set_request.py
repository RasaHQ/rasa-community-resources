"""Change the public request, never the protected requirements."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('1', '3'):
        print('Choose 1 or 3 attempts: python set_request.py NUMBER')
        return 2
    task_path = ROOT / 'tasks/c-recovery-attempts.json'
    task = json.loads(task_path.read_text())
    task['target_attempts'] = int(sys.argv[1])
    task['request'] = ('Set max_attempts in product/recovery.json to ' + sys.argv[1] +
                       '. Keep retry_rejected false: a rejected change must not be retried. Change JSON configuration only.')
    task_path.write_text(json.dumps(task, indent=2) + '\n')
    print('Requested ' + sys.argv[1] + ' attempts; protected files unchanged.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
