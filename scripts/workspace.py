#!/usr/bin/env python3
"""Create source-only worktrees and selected, isolated tutorial environments."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

MARKER = '.rasa-workspace.json'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def tree_hash(root):
    """Include installed files and symlink targets; never follow symlinks."""
    digest = hashlib.sha256()
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs.sort()
        for name in sorted(files + [n for n in dirs if (Path(directory) / n).is_symlink()]):
            path = Path(directory) / name
            rel = path.relative_to(root)
            if str(rel) == MARKER:
                continue
            if name.endswith('.pyc') and '__pycache__' in rel.parts:
                source = path.parent.parent / (name.split('.')[0] + '.py')
                if source.is_file():
                    continue
            digest.update(str(rel).encode() + b'\0')
            if path.is_symlink():
                digest.update(b'link\0' + os.readlink(path).encode())
            else:
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
            digest.update(b'\0')
    return digest.hexdigest()


def inputs(project):
    return {name: hashlib.sha256((project / name).read_bytes()).hexdigest()
            for name in ('pyproject.toml', 'uv.lock')}


def environment(project, action, owner, inactive=False):
    project = project.absolute()
    if project.is_symlink() or any(p.is_symlink() for p in project.parents):
        raise SystemExit('Use the real project directory, without symlink ancestors.')
    env = project / '.venv'
    if env.is_symlink():
        raise SystemExit('Refusing a symlinked environment.')
    if action == 'start':
        inputs(project)
        if env.exists():
            raise SystemExit('Environment already exists; retain its isolation or audit it before retirement.')
        install_env = {**os.environ, 'UV_PROJECT_ENVIRONMENT': str(env)}
        run('uv', 'sync', '--locked', '--project', str(project), env=install_env)
        record = {'owner': owner, 'project': str(project), 'inputs': inputs(project),
                  'tree_sha256': tree_hash(env)}
        (env / MARKER).write_text(json.dumps(record, indent=2) + '\n')
        print(f'Created only {env}; retire it when this experiment is complete.')
    else:
        record = json.loads((env / MARKER).read_text())
        if record['owner'] != owner or record['project'] != str(project):
            raise SystemExit('Environment belongs to another experiment or was copied; audit it first.')
        if record['inputs'] != inputs(project) or record['tree_sha256'] != tree_hash(env):
            raise SystemExit('Environment or rebuild inputs changed; preserve and audit those changes first.')
        if not inactive:
            raise SystemExit('Confirm this experiment and its jobs are inactive with --inactive.')
        # Preserve ownership and rebuild hashes outside the directory being retired.
        (project / '.rasa-environment-retired.json').write_text(json.dumps(record, indent=2) + '\n')
        shutil.rmtree(env)
        print(f'Retired {env}; rebuild with uv sync --locked --project {project}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('worktree')
    create.add_argument('path')
    create.add_argument('branch')
    create.add_argument('--base', default='HEAD')
    snapshot = commands.add_parser('snapshot', help='Committed source archive, not a dirty-work backup')
    snapshot.add_argument('output')
    for action in ('start', 'retire'):
        command = commands.add_parser(action)
        command.add_argument('project', type=Path)
        command.add_argument('--owner', required=True, help='Experiment identifier')
        if action == 'retire':
            command.add_argument('--inactive', action='store_true', help='Owner confirms no jobs use this environment')
    args = parser.parse_args()
    if args.command == 'worktree':
        run('git', 'worktree', 'add', '-b', args.branch, args.path, args.base)
    elif args.command == 'snapshot':
        output = Path(args.output).absolute()
        with output.open('xb') as stream:
            run('git', 'archive', '--format=tar', 'HEAD', stdout=stream)
        print(f'Committed source saved to {output}; unfinished work needs bundles, diffs and unique files.')
    else:
        environment(args.project, args.command, args.owner, getattr(args, 'inactive', False))
