#!/usr/bin/env python3
"""Reject statically declared cross-folder application dependencies in examples.

This is a source regression check, not a Python security sandbox. It checks
local package/lock sources, imports and statically resolvable source paths;
user-selected runtime inputs and temporary output locations are not package
sources. The only shared source-path exception is the devcontainer base image
Dockerfile, never a sibling application's code or a shared Python package.
"""
from __future__ import annotations

import ast
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {'zeointegrations'}
# The zeocore engine is allowed in examples generally, but the four banking examples
# must not use it.
BANK_EXAMPLES = {'jack-henry-symitar', 'jack-henry-silverlake', 'fiserv-premier-11.0.0-prm',
                 'fiserv-banking-hub-11.0.0.2026.4.1'}


def forbidden_for(project):
    return FORBIDDEN | ({'zeocore'} if Path(project).name in BANK_EXAMPLES else set())
PATH_KEYS = {'path', 'editable', 'directory', 'virtual'}
ALIASES = object()
EXCEPTIONS = 'scripts/example-runtime-exceptions.json'
KNOWN = {
    'mantle-voice-routed-skills': ('patterns/voice-vendor-router', '2026-11-13'),
    'mantle-voice-banking-dispute-claude': ('patterns/voice-vendor-router', '2026-11-13'),
    'mantle-voice-healthcare-refill-request-gpt-local': ('patterns/voice-vendor-router', '2026-11-14'),
}
AUTHORING = {'tests', 'case-build', 'controls'}
SUBPROCESS_COMMANDS = {'subprocess.'+method for method in ('run','Popen','call','check_call','check_output','getoutput','getstatusoutput')}
IO_METHODS = {'open', 'read_text', 'read_bytes', 'write_text', 'write_bytes', 'glob', 'rglob', 'iterdir', 'exists', 'is_file', 'is_dir'}


def inside(path, folder):
    return path == folder or folder in path.parents


def normalized(path):
    return Path(os.path.normpath(str(path))).resolve()


def name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return name(node.value) + '.' + node.attr
    return ''


def canonical(node, env):
    called = name(node)
    first, dot, rest = called.partition('.')
    return env.get(ALIASES, {}).get(first, first) + (dot + rest if dot else '')


def value(node, env, source, project):
    """Resolve common pathlib expressions without importing/executing source."""
    if isinstance(node, ast.Name):
        return source if node.id == '__file__' else env.get(node.id)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [value(item, env, source, project) for item in node.elts]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        operand = value(node.operand, env, source, project)
        return -operand if isinstance(operand, int) else None
    if isinstance(node, ast.JoinedStr):
        pieces = [value(part.value if isinstance(part, ast.FormattedValue) else part, env, source, project) for part in node.values]
        if all(isinstance(part, (str, Path)) for part in pieces):
            return ''.join(map(str, pieces))
    if isinstance(node, ast.BinOp):
        left, right = value(node.left, env, source, project), value(node.right, env, source, project)
        if isinstance(node.op, ast.Div) and isinstance(left, Path) and isinstance(right, str):
            return normalized(left / right)
        if isinstance(node.op, ast.Add) and isinstance(left, str) and isinstance(right, str):
            return left + right
    if isinstance(node, ast.Attribute):
        parent = value(node.value, env, source, project)
        if isinstance(parent, Path):
            if node.attr == 'parent':
                return parent.parent
            if node.attr == 'parents':
                return list(parent.parents)
    if isinstance(node, ast.Subscript):
        parent, index = value(node.value, env, source, project), value(node.slice, env, source, project)
        if isinstance(parent, list) and isinstance(index, int) and -len(parent) <= index < len(parent):
            return parent[index]
    if isinstance(node, ast.Call):
        called = canonical(node.func, env)
        args = [value(arg, env, source, project) for arg in node.args]
        if called in {'Path', 'pathlib.Path'} and args and isinstance(args[0], (str, Path)):
            return normalized(project / args[0])
        if called == 'str' and args:
            return args[0]  # preserve path identity for static analysis
        if called in {'Path.cwd', 'pathlib.Path.cwd'}:
            return project
        if called in {'os.path.join', 'os.path.abspath'} and args and all(isinstance(a, (str, Path)) for a in args):
            return normalized(project.joinpath(*args))
        if isinstance(node.func, ast.Attribute):
            parent = value(node.func.value, env, source, project)
            if isinstance(parent, Path):
                if node.func.attr in {'resolve', 'absolute'}:
                    return parent
                if node.func.attr == 'joinpath' and all(isinstance(a, str) for a in args):
                    return normalized(parent.joinpath(*args))
    return None


def path_problem(path, project, root, exception=None):
    path = normalized(path if isinstance(path, Path) else project / path)
    if inside(path, project):
        return False
    if exception == 'patterns/voice-vendor-router' and inside(path, root / exception):
        return False
    return path != root / '.devcontainer/resource-base/Dockerfile'


def manifest_findings(raw, project, root, source=None, exception=None):
    findings = []
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError:
        return ['invalid TOML prevents dependency inspection']

    def walk(item):
        if isinstance(item, dict):
            for key, val in item.items():
                if key in PATH_KEYS and isinstance(val, str) and path_problem((source.parent if source else project) / val, project, root, exception):
                    findings.append('local package source leaves its example folder')
                walk(val)
        elif isinstance(item, list):
            for val in item:
                walk(val)
        elif isinstance(item, str):
            distribution = re.split(r'[<>=!~\[;@ ]', item, maxsplit=1)[0]
            if re.sub(r'[-_.]', '', distribution).lower() in forbidden_for(project) | {'bankingdemoshared'}:
                findings.append('forbidden shared application distribution')
            if 'file:' in item:
                url = urlsplit(item.split('@', 1)[-1].strip())
                if url.scheme == 'file' and (url.netloc not in {'', 'localhost'} or path_problem((source.parent if source else project) / unquote(url.path), project, root, exception)):
                    findings.append('file dependency leaves its example folder')
    walk(data)
    return findings


def static_environment(tree, source, project):
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in {'pathlib', 'importlib', 'sys', 'subprocess'}:
            for alias in node.names:
                aliases[alias.asname or alias.name] = node.module + '.' + alias.name
    env = {ALIASES: aliases}
    for _ in range(4):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                resolved = value(node.value, env, source, project)
                if resolved is not None:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            env[target.id] = resolved
    return env


def python_findings(raw, source, project, root, exception=None, authoring=False):
    try:
        tree = ast.parse(raw)
    except SyntaxError:
        return [(1, 'invalid Python prevents dependency inspection')]
    problems = []
    env = static_environment(tree, source, project)
    for node in ast.walk(tree):
        imports = []
        if isinstance(node, ast.Import):
            imports = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imports = [node.module or '']
            if node.level and not inside(source.parent.joinpath(*(['..'] * (node.level - 1))).resolve(), project):
                problems.append((node.lineno, 'relative import leaves its example folder'))
        elif isinstance(node, ast.Call) and canonical(node.func, env) in {'__import__', 'importlib.import_module'} and node.args:
            resolved = value(node.args[0], env, source, project)
            if isinstance(resolved, str):
                imports = [resolved]
        for module in imports:
            module_root = re.sub(r'[-_]', '', module.split('.')[0]).lower()
            if module_root in forbidden_for(project):
                problems.append((node.lineno, 'forbidden zeointegrations/zeocore import'))
            if module.split('.')[0] in {'examples', 'patterns', 'tutorials', 'scripts'}:
                local = project.joinpath(*module.split('.'))
                if not local.is_dir() and not local.with_suffix('.py').is_file():
                    problems.append((node.lineno, 'repository import is not local to this example'))
        if authoring or not isinstance(node, ast.Call):
            continue
        called = canonical(node.func, env)
        candidates = []
        if called in {'sys.path.insert', 'sys.path.append'} and node.args:
            candidates = [value(node.args[-1], env, source, project)]
            if candidates[0] is None:
                problems.append((node.lineno, 'cannot prove import search path is local'))
        elif called == 'sys.path.extend' and node.args:
            resolved = value(node.args[0], env, source, project)
            candidates = resolved if isinstance(resolved, list) else [None]
            if None in candidates:
                problems.append((node.lineno, 'cannot prove import search paths are local'))
        elif called in {'open', 'io.open'} and node.args:
            candidates = [value(node.args[0], env, source, project)]
        elif isinstance(node.func, ast.Attribute) and node.func.attr in IO_METHODS:
            candidates = [value(node.func.value, env, source, project)]
        elif called in SUBPROCESS_COMMANDS:
            for keyword in node.keywords:
                if keyword.arg == 'cwd':
                    candidates.append(value(keyword.value, env, source, project))
            command = node.args[0] if node.args else next((keyword.value for keyword in node.keywords if keyword.arg in {'args','cmd'}), None)
            args = value(command, env, source, project) if command is not None else None
            uses_shell = any(keyword.arg == 'shell' and value(keyword.value, env, source, project) is not False for keyword in node.keywords)
            if isinstance(args,str) or isinstance(command,ast.JoinedStr) or uses_shell or called in {'subprocess.getoutput','subprocess.getstatusoutput'}:
                problems.append((node.lineno, 'use a list-form command'))
                continue
            if isinstance(args, list):
                for index, arg in enumerate(args):
                    # System executables are installed tools, not sibling
                    # application source. Script arguments remain checked.
                    system = index == 0 and isinstance(arg, str) and Path(arg).parent.as_posix() in {'/usr/bin', '/bin', '/usr/local/bin'}
                    if isinstance(arg, (Path, str)) and not system:
                        candidates.append(arg)
        for candidate in candidates:
            if isinstance(candidate, Path) and path_problem(candidate, project, root, exception):
                problems.append((node.lineno, 'source/import path leaves its example folder'))
            elif isinstance(candidate, str) and ('/' in candidate or candidate.startswith('.')) and path_problem(candidate, project, root, exception):
                problems.append((node.lineno, 'source/import path leaves its example folder'))
    return problems


def exception_findings(rows, previous=None, today=None):
    """Freeze the initial five identities; later diffs may only remove rows."""
    today = today or date.today()
    problems, seen = [], set()
    for row in rows:
        example = row.get('example')
        expected = KNOWN.get(example)
        if set(row) != {'example', 'violation', 'fix_by'} or expected is None:
            problems.append('unknown or malformed runtime exception')
            continue
        if example in seen:
            problems.append('duplicate runtime exception: ' + example)
        seen.add(example)
        if (row['violation'], row['fix_by']) != expected:
            problems.append('runtime exception changed or extended: ' + example)
        if row['fix_by'] < today.isoformat():
            problems.append('expired runtime exception: ' + example)
    if previous is not None:
        for row in rows:
            if row not in previous:
                problems.append('runtime exception added or changed instead of shrinking')
    return problems


def make_runtime_lines(raw):
    """Follow install/run targets, leaving central authoring targets alone.

    No Make code is executed. Static variables are expanded before inspection.
    Python files outside explicitly named authoring folders remain in scope.
    """
    variables, targets, current = {}, {}, []
    for line, text in enumerate(raw.splitlines(), 1):
        assignment = re.match(r'^([A-Za-z_][\w-]*)\s*[:?+]?=\s*(.*)', text)
        target = re.match(r'^([\w .-]+):\s*([^#]*)', text)
        if assignment:
            variables[assignment[1]] = assignment[2]
            current = []
        elif target:
            current = target[1].split()
            for key in current:
                targets.setdefault(key, {'deps': [], 'lines': []})['deps'].extend(target[2].split())
        elif text.startswith('\t'):
            for key in current:
                targets[key]['lines'].append((line, text))
    def expand(text):
        for _ in range(10):
            updated = re.sub(r'\$[({]([\w-]+)[)}]', lambda m: variables.get(m[1], m[0]), text)
            if updated == text:
                break
            text = updated
        return text
    pending = [key for key in targets if key in {'run', 'inspect', 'train', 'install', 'setup', 'env', 'serve', 'start'}]
    visited, lines = set(), []
    while pending:
        key = pending.pop()
        if key in visited or key not in targets:
            continue
        visited.add(key)
        pending.extend(targets[key]['deps'])
        for line, text in targets[key]['lines']:
            text = expand(text)
            pending.extend(re.findall(r'\$\(MAKE\)\s+([\w-]+)', text))
            lines.append((line, text))
    return lines


def runtime_files(root, files):
    """Follow static runtime imports/entrypoints through authoring folders.

    Relative imports use their real package base, including module-less forms
    such as ``from . import controls``. Importing a package also executes its
    parent initializers. Static importlib calls and Make/shell Python entrypoints
    receive the same closure treatment; genuine unreferenced parity tests stay
    authoring-only. This does not resolve arbitrary computed import names.
    """
    active = {f for f in files if not (set(Path(f).parts[2:-1]) & AUTHORING)}
    def promote(candidate):
        candidate = normalized(candidate)
        if not inside(candidate, root):
            return
        relative = candidate.relative_to(root).as_posix()
        if relative in files:
            active.add(relative)

    def module(base, parts):
        local = base
        for part in parts:
            local /= part
            promote(local / '__init__.py')
        if parts:
            promote(local.with_suffix('.py'))

    previous = None
    while previous != active:
        previous = active.copy()
        for relative in list(active):
            source = root / relative
            if not source.is_file():
                continue
            project = root / 'examples' / Path(relative).parts[1]
            if source.name == 'Makefile' or source.suffix == '.sh':
                lines = make_runtime_lines(source.read_text()) if source.name == 'Makefile' else enumerate(source.read_text().splitlines(), 1)
                for _, text in lines:
                    for match in re.finditer(r'(?:^|[\s\"\x27])([\w./-]+\.(?:py|sh))(?:$|[\s\"\x27;])', text):
                        promote(project / match[1])
                continue
            if source.suffix != '.py':
                continue
            try:
                tree = ast.parse(source.read_text())
            except SyntaxError:
                continue
            env = static_environment(tree, source, project)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    bases = (source.parent.joinpath(*(['..'] * (node.level - 1))),) if node.level else (project, source.parent)
                    parts = node.module.split('.') if node.module else []
                    for base in bases:
                        module(base, parts)
                        for alias in node.names:
                            if alias.name != '*':
                                module(base, parts + [alias.name])
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        for base in (project, source.parent):
                            module(base, alias.name.split('.'))
                elif isinstance(node, ast.Call):
                    called = canonical(node.func, env)
                    command = node.args[0] if node.args else next((keyword.value for keyword in node.keywords if keyword.arg in {'args','cmd'}), None)
                    resolved = value(command, env, source, project) if command is not None else None
                    if called in {'__import__', 'importlib.import_module'} and isinstance(resolved, str):
                        for base in (project, source.parent):
                            module(base, resolved.split('.'))
                    elif called in SUBPROCESS_COMMANDS:
                        if not isinstance(resolved, list) or any(keyword.arg == 'shell' and value(keyword.value, env, source, project) is not False for keyword in node.keywords):
                            continue  # String/shell commands are findings, never parsed.
                        for arg in resolved:
                            if isinstance(arg, (Path, str)):
                                promote(project / arg)
    return active


def inspect(root, files, exceptions=None):
    problems = []
    exceptions = exceptions or []
    allowed = {row['example']: row['violation'] for row in exceptions}
    runtime = runtime_files(root, files)
    for relative in files:
        parts = Path(relative).parts
        if len(parts) < 3 or parts[0] != 'examples':
            continue
        source = root / relative
        project = root / 'examples' / parts[1]
        exception = allowed.get(parts[1])
        if source.is_symlink():
            if path_problem(source.resolve(), project, root, exception):
                problems.append(f'{relative}: symlink leaves its example folder')
            continue
        if not source.is_file():
            continue
        if source.name in {'pyproject.toml', 'uv.lock'}:
            problems.extend(f'{relative}: {message}' for message in manifest_findings(source.read_text(), project, root, source, exception))
        elif source.suffix == '.py':
            problems.extend(f'{relative}:{line}: {message}' for line, message in python_findings(source.read_text(), source, project, root, exception, relative not in runtime))
        elif source.name == 'Makefile' or source.suffix == '.sh' and relative in runtime:
            lines = make_runtime_lines(source.read_text()) if source.name == 'Makefile' else enumerate(source.read_text().splitlines(), 1)
            for line, text in lines:
                for match in re.finditer(r'(?:^|[\s=\"\x27])((?:\.\./)+[^\s\"\x27;]*)', text):
                    if not text.lstrip().startswith('#') and path_problem(match[1], project, root, exception):
                        problems.append(f'{relative}:{line}: shell path leaves its example folder')
        elif source.suffix in {'.yml', '.yaml', '.json'} and relative in runtime:
            # Only path-valued runtime configuration, not arbitrary fixture text.
            for line, text in enumerate(source.read_text().splitlines(), 1):
                match = re.match(r'\s*[\"\x27]?[\w-]*(?:path|file|dir|directory)[\"\x27]?\s*:\s*[\"\x27]?(\.\./[^\s\"\x27,}]+)', text)
                if match and path_problem(match[1], project, root, exception):
                    problems.append(f'{relative}:{line}: configured runtime path leaves its example folder')
    return sorted(set(problems))


def previous_exceptions(root):
    event_file = os.environ.get('GITHUB_EVENT_PATH')
    if event_file:
        event = json.loads(Path(event_file).read_text())
        base = event.get('pull_request', {}).get('base', {}).get('sha') or event.get('before')
    else:
        base = 'HEAD'
    if not base or base == '0' * 40:
        base = 'HEAD'
    subprocess.run(['git', 'cat-file', '-e', base + '^{commit}'], cwd=root, check=True, stdout=subprocess.DEVNULL)
    present = subprocess.check_output(['git', 'ls-tree', '--name-only', base, '--', EXCEPTIONS], cwd=root).decode().strip()
    if not present:
        return None  # Initial installation is fenced by KNOWN, not open-ended.
    return json.loads(subprocess.check_output(['git', 'show', base + ':' + EXCEPTIONS], cwd=root))


def main():
    files = subprocess.check_output(['git', 'ls-files', '-z', '--', 'examples'], cwd=ROOT).decode().split('\0')
    rows = json.loads((ROOT / EXCEPTIONS).read_text())
    findings = exception_findings(rows, previous_exceptions(ROOT))
    findings += inspect(ROOT, [file for file in files if file], rows)
    for finding in findings:
        print('FAIL: ' + finding)
    if findings:
        return 1
    for row in rows:
        print('DEBT: {example}: {violation}; fix by {fix_by}'.format(**row))
    print('PASS: example runtime dependency guard; listed debt is not self-contained')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
