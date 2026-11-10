"""Inspect only trusted Python projects; native loading executes their imports."""
from contextlib import redirect_stdout
import argparse
import json
import sys
from pathlib import Path
from inventory import inventory, check


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['snapshot', 'check'])
    parser.add_argument('project', type=Path)
    parser.add_argument('--expected', type=Path)
    parser.add_argument('--trusted-python', action='store_true',
                        help='Required: acknowledge that loading executes this trusted project’s Python imports.')
    args = parser.parse_args(argv)
    if not args.trusted_python:
        parser.error('--trusted-python is required; never load untrusted uploads')
    if args.command == 'check' and args.expected is None:
        parser.error('check requires --expected')
    if args.command == 'snapshot' and args.expected is not None:
        parser.error('snapshot does not accept --expected')
    try:
        if not args.project.is_dir():
            raise ValueError('Project directory does not exist')
        expected = json.loads(args.expected.read_text()) if args.expected else None
        with redirect_stdout(sys.stderr):
            actual = inventory(args.project)
        check(actual, actual)  # An unresolved binding must not become an accepted snapshot.
        if args.command == 'check':
            check(expected, actual)
            result = {'status': 'match', 'rows': len(actual['rows'])}
        else:
            result = actual
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'refused', 'reason': str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
