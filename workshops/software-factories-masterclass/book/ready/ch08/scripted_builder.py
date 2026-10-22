"""Labelled offline teaching builder; writes JSON, no model or network request."""
import json
from pathlib import Path
import sys


def main(task_path, output):
    task = json.loads(Path(task_path).read_text())
    n = task['target_attempts']
    if type(n) is not int or n not in (1, 2, 3):
        return 2
    output = Path(output)
    if output.exists():
        print('Choose a fresh attempt name; earlier work is preserved.')
        return 2
    (output / 'product').mkdir(parents=True)
    (output / 'product/recovery.json').write_text(json.dumps({'max_attempts':n, 'retry_rejected':False}, indent=2) + '\n')
    print('SCRIPTED teaching builder: wrote configuration; zero model calls.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(*sys.argv[1:3]))
