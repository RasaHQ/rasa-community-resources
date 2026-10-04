"""Reject private result artifacts in changes to the public tutorial repository."""
import argparse
import json
import re
import subprocess
from pathlib import PurePosixPath


def path_problem(path):
    parts = PurePosixPath(path).parts
    if 'results' in parts or 'internal' in parts or 'raw' in parts:
        return 'result or internal artifact'
    name = parts[-1]
    if name.startswith('.env') and name != '.env.example':
        return 'credential file'
    if name in {'spend-ledger.json', 'llm-calls.jsonl', 'engine-report-cohorts.json', 'EXPANSION-PLAN.md'}:
        return 'internal measurement artifact'
    if name.endswith(('.bundle', '.log')):
        return 'history archive or captured log'
    return None


def measured_fields(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'cost_usd', 'rendered_at'} and item is not None:
                return True
            if measured_fields(item):
                return True
    elif isinstance(value, list):
        return any(measured_fields(item) for item in value)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--target', default='HEAD', help='Git revision, or INDEX')
    args = parser.parse_args()
    def git(*argv):
        return subprocess.check_output(['git', *argv])
    changes = git('diff', '--name-only', '--diff-filter=ACMRT', '-z', args.base,
                  *(['--cached'] if args.target == 'INDEX' else [args.target])).decode().split('\0')
    issues = []
    for path in filter(None, changes):
        reason = path_problem(path)
        if reason:
            issues.append(f'{path}: {reason}')
        if not path.endswith(('.md', '.json', '.yml', '.yaml')):
            continue
        data = git('show', f'{"" if args.target == "INDEX" else args.target}:{path}').decode()
        if re.search(r'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}', data):
            issues.append(f'{path}: possible secret value')
        if path.endswith('caller-audio/manifest.json') and measured_fields(json.loads(data)):
            issues.append(f'{path}: captured billing or run metadata')
        if path == 'catalog/case-builds.json':
            old = json.loads(git('show', f'{args.base}:{path}'))
            current = json.loads(data)
            def rows(x):
                if isinstance(x, list):
                    yield from x
                elif isinstance(x, dict):
                    for value in x.values():
                        if isinstance(value, list):
                            yield from value
            prior = {json.dumps(row, sort_keys=True) for row in rows(old)}
            for row in rows(current):
                if json.dumps(row, sort_keys=True) not in prior and isinstance(row, dict):
                    if any(row.get(k) is not None for k in ['result', 'spendUsd', 'recordedAt']) or row.get('findings'):
                        issues.append(f'{path}: changed catalogue row contains measurements or findings')
    if issues:
        print('\n'.join(issues))
        raise SystemExit(1)
    print('Public tutorial delta: no result artifacts or populated measurement fields.')


if __name__ == '__main__':
    main()
