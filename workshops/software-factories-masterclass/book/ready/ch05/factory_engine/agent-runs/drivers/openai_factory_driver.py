"""One managed Agents session over confined scratch-file tools, then the existing factory.

The model never receives a shell, a network tool, a protected suite or verifier records.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import threading

FACTORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FACTORY))
from factory_console import redact
from scratch import visible_task


def open_only(function):
    def guarded(self, arguments):
        with self.lock:
            if self.fd is None:
                return {'ok': False, 'error': 'scratch_tools_closed'}
            return function(self, arguments)
    return guarded


class ConfinedFiles:
    """Every component opened relative to an anchored directory FD, with no symlinks."""
    def __init__(self, workspace, task, event=None, task_filename=None):
        path = Path(workspace)
        if path.is_symlink() or not path.is_dir():
            raise ValueError('scratch_directory_required')
        self.root = path.resolve()
        self.lock = threading.RLock()
        self.fd = None
        self.allowed = tuple(task['allowed_paths'])
        for prefix in self.allowed:
            parts = self.parts(prefix.rstrip('/'))
            if parts[0] != 'product':
                self.close()
                raise ValueError('only_product_changes_allowed')
        task_id = task['id']
        if not isinstance(task_id, str) or not task_id or '/' in task_id or '\\' in task_id or task_id in ('.', '..'):
            self.close()
            raise ValueError('invalid_task_id')
        task_filename = task_filename or task_id + '.json'
        if len(self.parts(task_filename)) != 1:
            raise ValueError('invalid_task_filename')
        self.fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.visible = {'AGENTS.md', 'CLAUDE.md', 'validate.py', 'tasks/' + task_filename}
        self.event = event or (lambda **_values: None)
        self.bytes_written = 0

    @staticmethod
    def parts(name):
        if not isinstance(name, str) or not name or len(name) > 512 or '\\' in name or '\x00' in name:
            raise ValueError('invalid_relative_path')
        path = PurePosixPath(name)
        if path.is_absolute() or any(p in ('', '.', '..') or p.startswith('.') for p in name.split('/')):
            raise ValueError('invalid_relative_path')
        return path.parts

    def close(self):
        with self.lock:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None

    def parent_fd(self, parts, *, create=False):
        descriptor = os.dup(self.fd)
        try:
            for component in parts[:-1]:
                if create:
                    try:
                        os.mkdir(component, mode=0o700, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def permitted(self, name):
        return any(name == prefix or (prefix.endswith('/') and name.startswith(prefix)) for prefix in self.allowed)

    @open_only
    def read_file(self, arguments):
        try:
            name = arguments['path']
            parts = self.parts(name)
            if name not in self.visible and (parts[0] != 'product' or any(p in ('acceptance', 'protected') for p in parts)):
                raise ValueError('read_outside_visible_scratch')
            if any(p == '.env' or p.endswith(('.pem', '.key')) for p in parts):
                raise ValueError('credential_path_refused')
            parent = self.parent_fd(parts)
            try:
                descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            finally:
                os.close(parent)
            with os.fdopen(descriptor, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('regular_file_required')
                data = stream.read(65537)
            if len(data) > 65536:
                raise ValueError('file_limit')
            text = data.decode('utf-8')
            # Parent credentials must not be disclosed even if a prepared file
            # accidentally contains one. Normal templates contain placeholders.
            text = redact(text)
            self.event(stage='builder', status='RUNNING', action='read_file', path=name, bytes=len(data),
                       result_sha256=hashlib.sha256(text.encode()).hexdigest())
            return {'ok': True, 'text': text}
        except (OSError, ValueError, KeyError, TypeError, UnicodeError):
            self.event(stage='builder', status='FAIL', action='read_file')
            return {'ok': False, 'error': 'scratch_read_refused'}

    @open_only
    def write_file(self, arguments):
        try:
            name, text = arguments['path'], arguments['text']
            parts = self.parts(name)
            if not self.permitted(name) or parts[0] != 'product' or any(p in ('acceptance', 'protected') for p in parts):
                raise ValueError('write_outside_task')
            if not isinstance(text, str) or '\x00' in text:
                raise ValueError('text_required')
            data = text.encode('utf-8')
            if len(data) > 65536 or self.bytes_written + len(data) > 512 * 1024:
                raise ValueError('write_limit')
            # Refuse any known host credential rather than writing it to scratch.
            if redact(text) != text:
                raise ValueError('credential_content_refused')
            parent = self.parent_fd(parts, create=True)
            try:
                descriptor = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                                     0o600, dir_fd=parent)
            finally:
                os.close(parent)
            with os.fdopen(descriptor, 'wb') as output:
                info = os.fstat(output.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('regular_unlinked_file_required')
                output.truncate(0)
                output.write(data)
            self.bytes_written += len(data)
            self.event(stage='builder', status='RUNNING', action='write_file', path=name, bytes=len(data),
                       result_sha256=hashlib.sha256(data).hexdigest())
            return {'ok': True, 'bytes': len(data)}
        except (OSError, ValueError, KeyError, TypeError, UnicodeError):
            self.event(stage='builder', status='FAIL', action='write_file')
            return {'ok': False, 'error': 'scratch_write_refused'}

    @open_only
    def list_files(self, _arguments):
        found = []
        # fwalk follows no symbolic directory; final reads/writes independently
        # revalidate every component via the anchored FD.
        for directory, folders, files, descriptor in os.fwalk('.', dir_fd=self.fd, follow_symlinks=False):
            folders[:] = sorted(name for name in folders if not name.startswith('.')
                                and name not in ('acceptance', 'protected', '__pycache__')
                                and stat.S_ISDIR(os.stat(name, dir_fd=descriptor, follow_symlinks=False).st_mode))
            for filename in sorted(files):
                name = (Path(directory) / filename).as_posix()
                info = os.stat(filename, dir_fd=descriptor, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or filename.startswith('.'):
                    continue
                if name in self.visible or name.startswith('product/'):
                    found.append(name)
                    if len(found) >= 256:
                        self.event(stage='builder', status='RUNNING', action='list_files')
                        return {'ok': True, 'files': found, 'truncated': True}
        self.event(stage='builder', status='RUNNING', action='list_files')
        return {'ok': True, 'files': found, 'truncated': False}


def module(name):
    spec = importlib.util.spec_from_file_location('factory_host_' + name, FACTORY / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def event_writer(run_directory):
    path = Path(run_directory) / 'events.jsonl'
    count = 0
    def event(**values):
        nonlocal count
        count += 1
        if count > 500:
            raise ValueError('event_limit')
        # No arguments, file contents, model prose, headers or SDK exceptions.
        with path.open('a') as output:
            output.write(redact(json.dumps(values, separators=(',', ':'))) + '\n')
    return event


def runtime_bindings():
    from zeo_core.integrations.agents import run_native, function_tool
    return run_native, function_tool


def native_builder(client, *, task, workspace, event, model, invoke=None, tool_factory=None, spend_limit_cents=None, estimated_cents_per_call=None, task_filename=None):
    if invoke is None or tool_factory is None:
        run_native, function_tool = runtime_bindings()
        invoke = run_native if invoke is None else invoke
        tool_factory = function_tool if tool_factory is None else tool_factory
    # Architect04:32: the service rejects spend_control. This is only a
    # caller-supplied estimate check; the provider project budget is the money cap.
    if (spend_limit_cents is None) != (estimated_cents_per_call is None):
        raise ValueError('local_spend_limit_and_estimate_required_together')
    if spend_limit_cents is not None:
        if (type(spend_limit_cents) is not int or not 1 <= spend_limit_cents <= 200
                or type(estimated_cents_per_call) is not int or not 1 <= estimated_cents_per_call <= 200):
            raise ValueError('invalid_local_spend_estimate')
        if 30 * estimated_cents_per_call > spend_limit_cents:
            raise ValueError('local_spend_estimate_over_limit')
    files = ConfinedFiles(workspace, task, event, task_filename=task_filename)
    try:
        schemas = {
            'list_files': {'type': 'object', 'properties': {}, 'additionalProperties': False},
            'read_file': {'type': 'object', 'properties': {'path': {'type': 'string'}},
                          'required': ['path'], 'additionalProperties': False},
            'write_file': {'type': 'object', 'properties': {'path': {'type': 'string'}, 'text': {'type': 'string'}},
                           'required': ['path', 'text'], 'additionalProperties': False},
        }
        tools = [tool_factory(name, 'Access only the prepared builder scratch copy within the task scope.', schema)
                 for name, schema in schemas.items()]
        visible = visible_task(task)
        event(stage='builder', status='RUNNING', action='session_started', max_calls=30,
              deadline_seconds=120, timeout_seconds=20, provider_session_cap=False,
              local_estimate_limit_cents=spend_limit_cents, estimated_cents_per_call=estimated_cents_per_call)
        result = invoke(client, agent={'model': model, 'tools': tools,
                        'instructions': 'Read AGENTS.md and the visible task. Change only allowed paths. '
                        'Use only these file tools. No shell, network or protected suite is available. '
                        'The existing independent factory will verify the result; do not claim ACCEPT.'},
                        environment={'type': 'none'}, text=json.dumps(visible),
                        handlers={name: getattr(files, name) for name in schemas},
                        max_calls=30, max_events=10000, deadline_seconds=120, timeout=20)
        event(stage='builder', status='PASS' if result.ok else 'FAIL', action='session_finished')
        return result
    finally:
        files.close()


def validate_scratch(workspace, task, task_filename=None):
    """Accept the existing preparer's visible workspace, never a repo checkout."""
    root = Path(workspace)
    if root.is_symlink() or not root.is_dir() or not (root / '.scratch.json').is_file():
        raise ValueError('prepared_scratch_manifest_required')
    visible = visible_task(task)
    task_name = task['id']
    ConfinedFiles.parts(task_name)
    if '/' in task_name:
        raise ValueError('invalid_task_id')
    total = 0
    count = 0
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if (path.is_symlink() or any(part in ('acceptance', 'protected', '.git', '.env') for part in relative.parts)
                or (relative.as_posix() != '.scratch.json' and any(part.startswith('.') for part in relative.parts))):
            raise ValueError('protected_or_linked_scratch_entry')
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('regular_unlinked_scratch_files_required')
        if relative.parts[0] not in ('product', 'tasks') and relative.as_posix() not in ('.scratch.json', 'AGENTS.md', 'CLAUDE.md', 'validate.py'):
            raise ValueError('unexpected_scratch_file')
        count += 1
        total += info.st_size
        if count > 512 or total > 5 * 1024 * 1024:
            raise ValueError('scratch_size_limit')
    if json.loads((root / 'tasks' / (task_filename or task_name + '.json')).read_text()) != visible:
        raise ValueError('visible_task_must_match')


def execute(task_path, workspace, run_directory, *, client, model, invoke=None, tool_factory=None,
            pack_root=None, environment_path=None, spend_limit_cents=None, estimated_cents_per_call=None, expected_cost_cents=None, mode='LIVE_NATIVE'):
    pack_root = Path(pack_root).resolve() if pack_root is not None else FACTORY
    task = json.loads(Path(task_path).read_text())
    validate_scratch(workspace, task, Path(task_path).name)
    directory = Path(run_directory)
    if directory.exists():
        raise ValueError('fresh_run_directory_required')
    scratch = Path(workspace).resolve()
    if scratch == directory.resolve() or directory.resolve().is_relative_to(scratch):
        raise ValueError('records_must_be_outside_builder_scratch')
    directory.mkdir(parents=True, mode=0o700)
    (directory / 'task').mkdir()
    task_snapshot = directory / 'task' / Path(task_path).name
    task_snapshot.write_text(json.dumps(task, indent=2) + '\n')
    task_snapshot.chmod(0o400)
    event = event_writer(directory)
    visible = visible_task(task)
    record = {'schema': 'mantle-factory-console-v1', 'state': 'BUILDER_RUNNING', 'mode': mode, 'task': visible,
              'bounds': {'provider_session_cap': False, 'max_calls': 30, 'deadline_seconds': 120,
                         'timeout_seconds': 20, 'expected_cost_cents': expected_cost_cents},
              'prepared': ['Prepared scratch product', 'Task allowed-path contract',
                           'Existing collect.py and factory.py', 'Independent protected suite outside builder scratch'],
              'task_sha256': hashlib.sha256(Path(task_path).read_bytes()).hexdigest()}
    def save(state):
        record['state'] = state
        (directory / 'console.json').write_text(redact(json.dumps(record, indent=2)) + '\n')
    save('BUILDER_RUNNING')
    try:
        factory = module('factory')
        profile_path = environment_path or FACTORY / 'environment.json'
        if factory.sandbox_unavailable(profile_path):
            event(stage='verification', status='NOT_READY', action='requires_macos_sandbox')
            save('NOT_READY')
            print('could not run: this check needs macOS (sandbox-exec). The attempt was not judged.')
            return 2
        installed, problems = factory.prepare(profile_path)
        if problems:
            event(stage='verification', status='NOT_READY', action='environment_not_ready')
            save('NOT_READY')
            return 3
        turn = native_builder(client, task=task, workspace=workspace, event=event, model=model,
                       invoke=invoke, tool_factory=tool_factory, spend_limit_cents=spend_limit_cents,
                       estimated_cents_per_call=estimated_cents_per_call, task_filename=Path(task_path).name)
        native_status = getattr(turn, 'status', 'not_recorded')
        native_status = native_status if native_status in ('completed', 'failed', 'cancelled', 'incomplete') else 'not_recorded'
        native_error = getattr(turn, 'error_code', None)
        native_error = native_error if isinstance(native_error, str) and native_error.replace('_', '').isalnum() and len(native_error) < 100 else None
        (directory / 'native.json').write_text(json.dumps({'status': native_status, 'error_code': native_error,
            'ok': bool(turn.ok), 'tools_called': [name for name in getattr(turn, 'tools_called', ())
               if name in ('list_files', 'read_file', 'write_file')]}))
        if native_status != 'completed':
            event(stage='builder', status='FAIL', action='session_not_completed')
            save('BUILDER_INCOMPLETE')
            return 2
        event(stage='collect', status='RUNNING')
        collected = module('collect').main(workspace, directory / 'candidate', directory / 'review', pack_root=pack_root)
        if collected != 0:
            event(stage='collect', status='FAIL')
            save('NO_CANDIDATE')
            return 2
        event(stage='collect', status='PASS')
        event(stage='verification', status='RUNNING')
        # The protected gate and its exit codes remain owned by factory.py.
        code = module('factory').main(task_snapshot, directory / 'candidate', directory / 'verification',
                                      pack_root=pack_root, environment_path=environment_path, strict=True)
        event(stage='decision', status={0: 'ACCEPT', 1: 'REJECT', 2: 'ERROR', 3: 'NOT_READY', 4: 'ESCALATE'}.get(code, 'ERROR'))
        save({0: 'ACCEPT', 1: 'REJECT', 2: 'ERROR', 3: 'NOT_READY', 4: 'ESCALATE'}.get(code, 'ERROR'))
        return code
    except Exception as error:
        code = ('released_native_spend_guard_required' if isinstance(error, ValueError)
                and error.args == ('released_native_spend_guard_required',) else 'factory_driver_failed')
        event(stage='builder', status='FAIL', action='run_failed', error_code=code)
        save('NOT_READY' if code == 'released_native_spend_guard_required' else 'ERROR')
        return 3 if code == 'released_native_spend_guard_required' else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task')
    parser.add_argument('workspace', help='An already prepared scratch.py workspace; never the class checkout.')
    parser.add_argument('run_directory', help='New evidence directory outside the builder scratch.')
    parser.add_argument('--model', required=True)
    parser.add_argument('--pack-root', help='Owning factory pack root; use the A6 subdirectory for A6.')
    parser.add_argument('--environment', help='Verifier profile; A6 uses factory/environment-a6.json.')
    parser.add_argument('--spend-limit-cents', type=int, help='Optional LOCAL estimate limit, not a money cap (1 to 200 cents).')
    parser.add_argument('--estimated-cents-per-call', type=int, help='Caller estimate; max_calls times this must fit the local estimate limit.')
    parser.add_argument('--no-session-cap', action='store_true', required=True, help='Explicitly accept that no per-session provider money cap is sent.')
    parser.add_argument('--expected-cost-cents-min', type=int, required=True, help='Stated expected range, not a cap.')
    parser.add_argument('--expected-cost-cents-max', type=int, required=True, help='Stated expected range, not a cap.')
    args = parser.parse_args(argv)
    if not 0 <= args.expected_cost_cents_min <= args.expected_cost_cents_max:
        parser.error('Expected cost range must be ordered and nonnegative.')
    if not os.environ.get('OPENAI_API_KEY', '').strip():
        print('Set OPENAI_API_KEY in the driver process environment; no value is printed.')
        return 3
    try:
        from openai import OpenAI, DefaultHttpxClient
        # One attempt, default first-party API only; no ambient proxy/base URL.
        with OpenAI(api_key=os.environ['OPENAI_API_KEY'], base_url='https://api.openai.com/v1',
                    max_retries=0, http_client=DefaultHttpxClient(trust_env=False)) as client:
            code = execute(args.task, args.workspace, args.run_directory, client=client, model=args.model,
                           pack_root=args.pack_root, environment_path=args.environment, spend_limit_cents=args.spend_limit_cents,
                           estimated_cents_per_call=args.estimated_cents_per_call,
                           expected_cost_cents=[args.expected_cost_cents_min, args.expected_cost_cents_max])
        print('Factory run finished with exit code ' + str(code) + '; inspect the read-only run evidence.')
        return code
    except Exception:
        print('The factory builder could not run; check the prepared scratch and supported native worker environment.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
