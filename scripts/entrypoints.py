#!/usr/bin/env python3
"""Repository entrypoints: inspect safely, select one project and protect pushes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import urllib.request
from collections.abc import Mapping, Sequence

ROOT = Path(__file__).resolve().parent.parent


class EntrypointError(ValueError):
    """A fixed, public error message safe to print without configuration values."""


def capture(args: Sequence[str], cwd: Path, timeout: int = 8) -> str:
    """Capture bounded metadata only; never print command output or exceptions."""
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                                timeout=timeout,
                                env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
        return result.stdout.strip() if result.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def host_mode(kernel: str, model: str) -> str:
    if kernel == 'Linux':
        return 'full'
    if kernel == 'Darwin' and model == 'Mac mini':
        return 'source'
    if kernel == 'Darwin' and model:
        return 'full'
    return 'refuse'


def current_mode(root: Path) -> str:
    kernel = capture(['uname', '-s'], root)
    model = ''
    if kernel == 'Darwin':
        profile = capture(['/usr/sbin/system_profiler', '-timeout', '5',
                           '-detailLevel', 'mini', 'SPHardwareDataType'], root)
        match = re.search(r'^\s*Model Name:\s*(.+?)\s*$', profile, re.MULTILINE)
        model = match.group(1) if match else ''
    return host_mode(kernel, model)


def require_build_host(root: Path) -> None:
    if current_mode(root) != 'full':
        raise EntrypointError('Use a build host; no install, test, build or provider operation started.')
    pin = json.loads((root / 'scripts/maintenance-toolchain.json').read_text())['python']
    wanted = tuple(map(int, pin.split('.')))
    if sys.version_info[:len(wanted)] != wanted:
        raise EntrypointError('Select the pinned Python from maintenance-toolchain.json with PYTHON before running this target.')


def selected_project(root: Path, env: Mapping[str, str]) -> tuple[Path, str]:
    raw, owner = env.get('PROJECT', ''), env.get('EXPERIMENT', '')
    if not raw or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}', owner):
        raise EntrypointError('Set PROJECT=<relative resource path> EXPERIMENT=<short identifier>.')
    rel = Path(raw)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0] not in {
            'examples', 'tutorials', 'patterns', 'community', 'heroes', 'workshops', 'starter-pack'}:
        raise EntrypointError('PROJECT must be a resource inside this checkout; traversal is refused.')
    project = root / rel
    if any(p.is_symlink() for p in [project, *project.parents]):
        raise EntrypointError('Select a real project path without symlink ancestors.')
    if not project.resolve().is_relative_to(root.resolve()):
        raise EntrypointError('PROJECT escapes the checkout.')
    if not all((project / name).is_file() and not (project / name).is_symlink()
               for name in ('pyproject.toml', 'uv.lock', 'Makefile')):
        raise EntrypointError('PROJECT needs its tracked pyproject.toml, uv.lock and Makefile.')
    return project, owner


def install_hooks(root: Path) -> None:
    # A worktree-local setting avoids breaking sibling worktrees at older revisions.
    if capture(['git', 'config', '--local', '--get', 'core.worktree'], root) or capture(['git', 'config', '--local', '--get', 'core.bare'], root) == 'true':
        raise EntrypointError('Custom or bare Git layout needs a reviewed worktree configuration migration.')
    for command in [
            ['git', 'config', '--local', 'extensions.worktreeConfig', 'true'],
            ['git', 'config', '--worktree', 'core.hooksPath', '.githooks']]:
        subprocess.run(command, cwd=root, check=True)
    print('Installed tracked pre-push protection in this worktree; main/master pushes are refused.')


def hook_current(root: Path) -> bool:
    configured = capture(['git', 'config', '--get', 'core.hooksPath'], root)
    location = Path(configured) if configured else Path('.git/hooks')
    location = location if location.is_absolute() else root / location
    if location.resolve() != (root / '.githooks').resolve():
        return False
    hook = root / '.githooks/pre-push'
    if not hook.is_file() or not os.access(hook, os.X_OK):
        return False
    # Report dirty/mismatched protection as unhealthy, even if the filename exists.
    for name in ('.githooks/pre-push', 'scripts/entrypoints.py'):
        actual = capture(['git', 'hash-object', name], root)
        expected = capture(['git', 'rev-parse', 'HEAD:' + name], root)
        if not actual or actual != expected:
            return False
    return True


def doctor(root: Path, offline: bool, env: Mapping[str, str]) -> int:
    failures = 0

    def check(ok: bool, label: str, fix: str) -> None:
        nonlocal failures
        failures += not ok
        print(('PASS ' if ok else 'FIX  ') + label + ('' if ok else ' — ' + fix))

    def version(name: str, minimum: str, exact: bool = False) -> None:
        raw = capture([name, '--version'], root)
        match = re.search(r'\d+\.\d+(?:\.\d+)?', raw)
        found = tuple(map(int, match.group().split('.'))) if match else ()
        wanted = tuple(map(int, minimum.split('.')))
        ok = found[:len(wanted)] == wanted if exact else found >= wanted
        check(ok, name + ' ' + (match.group() if match else 'unavailable'),
              'install ' + name + (' ' if exact else ' >= ') + minimum)

    print('Inspection only: no .env reads, installs, application imports or provider calls.')
    pins = json.loads((root / 'scripts/maintenance-toolchain.json').read_text())
    wanted = tuple(map(int, pins['python'].split('.')))
    check(sys.version_info[:len(wanted)] == wanted,
          'Python ' + '.'.join(map(str, sys.version_info[:3])),
          'select Python ' + pins['python'] + ' with PYTHON=python3.12')
    version('git', pins['gitMinimum'])
    version('make', pins['makeMinimum'])
    if pins['uv']:
        version('uv', pins['uv'], exact=True)
    else:
        check(False, 'uv version is not pinned', 'restore maintenance-toolchain.json')
    check(hook_current(root), 'tracked direct-main push hook installed and matches HEAD', 'run make hooks after committing source')
    check((root / 'RASA_PRO_VERSION').is_file(), 'Rasa version pin present', 'restore RASA_PRO_VERSION')
    print('INFO No external volume or background service is required for offline verification.')
    print('INFO Resource services and paid provider access are separate; inspect the selected README.')
    names = {'RASA_LICENSE', 'OPENAI_API_KEY', 'DEEPGRAM_API_KEY'}
    if env.get('PROJECT'):
        try:
            # Doctor does not need an experiment owner and never creates its environment.
            project, _ = selected_project(root, {**env, 'EXPERIMENT': env.get('EXPERIMENT') or 'inspection'})
            data = tomllib.loads((project / 'pyproject.toml').read_text())
            declared = data.get('tool', {}).get('rasa-catalog', {}).get('required-secrets', [])
            if not isinstance(declared, list) or not all(isinstance(n, str) and
                    re.fullmatch(r'[A-Z_][A-Z_0-9]*', n) for n in declared):
                raise EntrypointError('Invalid required-secrets metadata.')
            names.update(declared)
            print('PASS Selected project has setup inputs and a Makefile.')
            print('INFO Selected Python requirement: ' + str(data.get('project', {}).get('requires-python', 'not declared')))
            check((project / '.venv/pyvenv.cfg').is_file(), 'selected environment exists', 'run make setup with PROJECT and EXPERIMENT')
        except (ValueError, OSError):
            check(False, 'selected project inputs', 'choose a tracked resource with pyproject.toml, uv.lock and Makefile')
    for name in sorted(names):
        print('INFO ' + name + ': ' + ('set' if env.get(name) else 'unset') + ' (optional for offline verification)')
    if offline:
        print('SKIP Public HTTPS checks disabled; connectivity is unverified.')
    else:
        for host in ('pypi.org', 'github.com'):
            ok = False
            try:
                request = urllib.request.Request('https://' + host + '/', method='HEAD')
                with urllib.request.urlopen(request, timeout=3) as response:
                    ok = response.status < 400
            except Exception:
                pass  # Exceptions may contain private proxy URLs; never print them.
            check(ok, 'public HTTPS ' + host, 'check DNS, TLS and outbound access')
    print(str(failures) + ' prerequisite(s) need attention; no files or services changed.')
    return int(failures != 0)


def allowed_work_ref(ref: str) -> bool:
    return (ref.startswith('refs/heads/') and ref not in {
        'refs/heads/main', 'refs/heads/master', 'refs/heads/release'} and
        not ref.startswith('refs/heads/release/'))


def push(root: Path, updates: str) -> int:
    rows = []
    for line in updates.splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4 or not all(re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', fields[i]) for i in (1, 3)):
            raise EntrypointError('Malformed push update; refused before verification.')
        if fields[2] in {'refs/heads/main', 'refs/heads/master'}:
            raise EntrypointError('Direct main/master pushes are refused; push a work branch and open a PR.')
        rows.append(fields)
    if not rows:
        return 0
    # Every destination has been checked before host inspection or any gate.
    mode = current_mode(root)
    if mode == 'refuse':
        raise EntrypointError('Host identity is unavailable; no application gate started.')
    if mode == 'source':
        current = capture(['git', 'symbolic-ref', '--quiet', 'HEAD'], root)
        for local_ref, oid, remote_ref, _ in rows:
            if local_ref == 'HEAD':
                local_ref = current
            if not allowed_work_ref(local_ref) or not allowed_work_ref(remote_ref) or set(oid) == {'0'}:
                raise EntrypointError('Source-only pushes require non-protected work branches; no tags or deletions.')
        print('Source-only Mac mini push: application gates NOT_RUN; Linux verification and review required.')
        return 0
    return subprocess.run(['make', '--no-print-directory', 'verify'], cwd=root).returncode


def operate(root: Path, action: str, env: Mapping[str, str]) -> int:
    require_build_host(root)
    project, owner = selected_project(root, env)
    if action == 'setup':
        subprocess.run([sys.executable, '-B', 'scripts/workspace.py', 'start', str(project), '--owner', owner], cwd=root, check=True)
        install_hooks(root)
    elif action == 'clean':
        if env.get('INACTIVE') != '1':
            raise EntrypointError('Set INACTIVE=1 only after the experiment and its jobs stop.')
        subprocess.run([sys.executable, '-B', 'scripts/workspace.py', 'retire', str(project), '--owner', owner, '--inactive'], cwd=root, check=True)
    else:
        if (project / '.venv').is_symlink():
            raise EntrypointError('Symlinked environments are refused; preserve and audit first.')
        marker = project / '.venv/.rasa-workspace.json'
        record = json.loads(marker.read_text())
        expected = {n: hashlib.sha256((project / n).read_bytes()).hexdigest() for n in ('pyproject.toml', 'uv.lock')}
        if record.get('owner') != owner or record.get('project') != str(project) or record.get('inputs') != expected:
            raise EntrypointError('Managed environment ownership or locked inputs differ; audit before running.')
        return subprocess.run(['make', '--no-print-directory', '-C', str(project), 'run'],
                              cwd=root, env={**env, 'UV_PROJECT_ENVIRONMENT': str(project / '.venv')}).returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'hooks', 'require-build-host', 'pre-push', 'setup', 'run', 'clean'])
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'doctor':
            return doctor(ROOT, args.offline, os.environ)
        if args.command == 'hooks':
            install_hooks(ROOT)
        elif args.command == 'require-build-host':
            require_build_host(ROOT)
        elif args.command == 'pre-push':
            return push(ROOT, sys.stdin.read())
        else:
            return operate(ROOT, args.command, os.environ)
    except EntrypointError as error:
        print('FIX ' + str(error), file=sys.stderr)
        return 1
    except (ValueError, OSError, subprocess.SubprocessError):
        # Do not print arbitrary exception contents: paths or child output may be private.
        print('FIX Entrypoint refused. Check the documented host, selection, ownership and prerequisites.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
