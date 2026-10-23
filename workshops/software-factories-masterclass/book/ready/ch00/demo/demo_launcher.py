"""Local class entrypoint; real Mantle inspector, explicitly scripted without keys.

sow: software-factories-masterclass-SOW-02
No installed engine files are changed. The keyless child supplies deterministic
LLM responses at the pinned engine's LLMClient factory; everything downstream is
actual engine orchestration, MCP, hooks and the Inspector channel.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys

if __name__ == '__main__':
    sys.modules.setdefault('demo_launcher', sys.modules[__name__])
import time
import threading
import tomllib
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener
from voice_config import VOICE_OFF_TEXT
from demo_host import validate_host, require_viewer_access

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / 'project'
WORKER = ROOT / 'worker'
VOICE_FAILED_TEXT = 'Voice could not connect; continuing with text.'
SCRIPTED_LABEL = 'SCRIPTED tool selection; real keyless sources, not model reasoning.'


class DemoError(Exception):
    """A fixed, user-facing message, never dependency or credential text."""


def python_at(directory):
    return directory / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def registry_lock(directory):
    """Refuse local wheels, editable sources and non-PyPI package endpoints."""
    try:
        lock = tomllib.loads((directory / 'uv.lock').read_text())
        project = tomllib.loads((directory / 'pyproject.toml').read_text())
    except (OSError, ValueError):
        raise DemoError('The environment lock is missing or invalid; use the complete class checkout.') from None
    for package in lock.get('package', []):
        source = package.get('source', {})
        if source == {'virtual': '.'}:
            continue
        if source != {'registry': 'https://pypi.org/simple'}:
            raise DemoError('This checkout needs a registry-only class lock; ask for the released class head.')
        artifacts = [*package.get('wheels', []), *([package['sdist']] if 'sdist' in package else [])]
        for artifact in artifacts:
            url = urlsplit(artifact.get('url', ''))
            if (url.scheme != 'https' or url.hostname != 'files.pythonhosted.org'
                    or url.username or url.password or not artifact.get('hash', '').startswith('sha256:')):
                raise DemoError('A locked package is not a hashed PyPI artifact; use the reviewed class lock.')
    core = [p for p in lock.get('package', []) if p['name'] == 'zeocore']
    requirements = project.get('project', {}).get('dependencies', [])
    if len(core) != 1 or 'zeocore==' + core[0]['version'] not in requirements:
        raise DemoError('The zeocore release pin and lock disagree; use the complete class checkout.')


PARTICIPANT_KEYS = frozenset(('RASA_LICENSE', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPGRAM_API_KEY'))


def check_dotenv_git(root, environment, *, require_ignored):
    git_env = {key: value for key, value in environment.items() if not key.startswith('GIT_')}
    git_env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    prefix = ['git', '-C', str(root)]
    def status(arguments):
        return subprocess.run(prefix + arguments, env=git_env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=10).returncode
    tracked = status(['ls-files', '--error-unmatch', '--', '.env'])
    if tracked == 0:
        raise DemoError('The example .env is tracked by Git; remove it from the index before running the demo.')
    if tracked != 1:
        raise DemoError('Git could not verify that the example .env is untracked; use a Git checkout and retry.')
    if require_ignored and status(['check-ignore', '--quiet', '--', '.env']) != 0:
        raise DemoError('The example .env must be ignored by Git before use; restore the example .gitignore and retry.')


def participant_environment(environment, root=None, project=None, worker=None):
    """Read only the guarded example-root file, without expanding or exporting."""
    root = ROOT if root is None else Path(root)
    project = PROJECT if project is None else Path(project)
    worker = WORKER if worker is None else Path(worker)
    env = dict(environment)
    try:
        for directory in (root, project, worker):
            for candidate in directory.glob('.env*'):
                if candidate.name == '.env.example':
                    continue
                if directory == root and candidate.name == '.env':
                    continue
                raise DemoError('Keep participant credentials only in the example-root .env or your shell; remove other runtime dotenv files.')
        path = root / '.env'
        check_dotenv_git(root, environment, require_ignored=path.exists() or path.is_symlink())
        if not path.exists() and not path.is_symlink():
            return env
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
            raise DemoError('Use a regular, non-symlink .env without group or world write access; run chmod 600 .env.')
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(descriptor, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_mode & 0o022
                    or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)):
                raise DemoError('The example .env changed or is unsafe; use a regular private file and retry.')
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise DemoError('The example .env is too large; keep it within 4 KiB and the four documented credential lines.')
        text = raw.decode('utf-8-sig')
        seen = set()
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            name, separator, value = line.partition('=')
            value = value.strip()
            if not separator or name not in PARTICIPANT_KEYS:
                raise DemoError('The example .env may contain only RASA_LICENSE, OPENAI_API_KEY, ANTHROPIC_API_KEY and DEEPGRAM_API_KEY assignments.')
            if name in seen or '\x00' in value:
                raise DemoError('Use one single-line assignment per credential in the example .env.')
            seen.add(name)
            if value.startswith(('"', "'")):
                if len(value) < 2 or value[-1] != value[0]:
                    raise DemoError('Use one single-line assignment per credential in the example .env.')
                value = value[1:-1]
            # Values are literal. No interpolation, escaping or shell evaluation.
            if not env.get(name, '').strip():
                env[name] = value
        return env
    except DemoError:
        raise
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise DemoError('The example .env could not be read safely; check the file and Git checkout, then retry.') from None


def child_environment(*, credentials=True):
    env = participant_environment(os.environ) if credentials else os.environ.copy()
    if not credentials:
        # Setup/build backends and offline controls never receive credentials,
        # whether they originated in the participant file or the caller shell.
        for name in PARTICIPANT_KEYS:
            env.pop(name, None)
    # The launcher alone reads the guarded file; engine/uv dotenv stays disabled.
    cache = ROOT / '.demo-cache'
    cache.mkdir(exist_ok=True)
    (cache / 'tmp').mkdir(exist_ok=True)
    for name in list(env):
        if name.startswith(('UV_', 'PIP_')):
            env.pop(name)
    env.update(UV_CACHE_DIR=str(cache / 'uv'), UV_NO_CONFIG='1', UV_NO_ENV_FILE='1',
               PYTHON_DOTENV_DISABLED='1',
               UV_PYTHON_DOWNLOADS='never', UV_INDEX_URL='https://pypi.org/simple',
               PYTHONPYCACHEPREFIX=str(cache / 'pycache'), XDG_CACHE_HOME=str(cache),
               MPLCONFIGDIR=str(cache / 'matplotlib'), LITELLM_MODE='PRODUCTION',
               RASA_TELEMETRY_ENABLED='false', DO_NOT_TRACK='1',
               XDG_CONFIG_HOME=str(cache / 'config'), XDG_DATA_HOME=str(cache / 'data'),
               HF_HOME=str(cache / 'huggingface'), TIKTOKEN_CACHE_DIR=str(cache / 'tiktoken'),
               TMPDIR=str(cache / 'tmp'), PYTHONNOUSERSITE='1', PYTHONUNBUFFERED='1')
    return env


class Children:
    """Own only processes started by this invocation, including their groups."""
    def __init__(self):
        self.processes = []
        self.log_threads = []

    def start(self, argv, *, cwd, env):
        diagnostics = env.get('BRIEFING_DIAGNOSTICS_DIR')
        process = subprocess.Popen(argv, cwd=cwd, env=env, start_new_session=True,
                                   stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE if diagnostics else subprocess.DEVNULL,
                                   stderr=subprocess.STDOUT if diagnostics else subprocess.DEVNULL)
        self.processes.append(process)
        if diagnostics:
            directory = Path(diagnostics)
            directory.mkdir(parents=True, exist_ok=True)
            def capture():
                from project.lib.capability_logging import redact
                with (directory / ('child-' + str(process.pid) + '.log')).open('a') as log:
                    for raw in iter(process.stdout.readline, b''):
                        value = raw.decode('utf-8', errors='replace')
                        # File credentials exist only in env, not os.environ;
                        # redact from this child mapping before any log write.
                        for name in (*PARTICIPANT_KEYS, 'BRIEFING_MCP_TOKEN'):
                            secret = env.get(name, '')
                            if secret:
                                value = value.replace(secret, '[credential redacted]')
                                for index in range(len(secret) - 7):
                                    value = value.replace(secret[index:index + 8], '[credential fragment redacted]')
                        log.write(redact(value))
                        log.flush()
            thread = threading.Thread(target=capture, daemon=True)
            self.log_threads.append(thread)
            thread.start()
        return process

    def stop(self, process):
        others = [p for p in self.processes if p is not process]
        self.processes = [process]
        try:
            self.close()
        except Exception:
            self.processes = others + [process]
            raise
        else:
            self.processes = others

    def close(self):
        # Signal groups even if their leader has already exited.
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for process in reversed(self.processes):
                try:
                    os.killpg(process.pid, sig)
                except ProcessLookupError:
                    pass
            until = time.monotonic() + (3 if sig == signal.SIGTERM else 2)
            for process in self.processes:
                try:
                    process.wait(timeout=max(0.01, until - time.monotonic()))
                except subprocess.TimeoutExpired:
                    pass
            # Waiting for a group leader does not wait for its descendants.
            # Give the whole owned group the remaining signal deadline to exit.
            while True:
                group_present = False
                for process in self.processes:
                    try:
                        os.killpg(process.pid, 0)
                        group_present = True
                    except ProcessLookupError:
                        pass
                remaining = until - time.monotonic()
                if not group_present or remaining <= 0:
                    break
                time.sleep(min(0.05, remaining))
            if not group_present:
                break
        alive = []
        for process in self.processes:
            try:
                os.killpg(process.pid, 0)
                alive.append(process.pid)
            except ProcessLookupError:
                pass
        self.processes.clear()
        if alive:
            raise DemoError('A demo child has not stopped; do not start another demo until its process group is gone.')


def completed(children, argv, *, cwd, env, timeout, failure):
    process = children.start(argv, cwd=cwd, env=env)
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        raise DemoError(failure) from None
    if code:
        raise DemoError(failure)


def setup():
    if shutil.which('uv') is None:
        raise DemoError('Install uv, then run ./demo setup again.')
    for directory in (WORKER, PROJECT):
        registry_lock(directory)
    from demo_make import check_environment_target, mark_environment
    for directory in (WORKER, PROJECT):
        check_environment_target(directory)
    env = child_environment(credentials=False)
    # Locate an EXISTING managed interpreter in the caller's normal data home.
    # Runtime data remains redirected; discovery never downloads or installs.
    find_env = env.copy()
    for name in ('XDG_DATA_HOME', 'UV_PYTHON_INSTALL_DIR'):
        if name in os.environ:
            find_env[name] = os.environ[name]
        else:
            find_env.pop(name, None)
    result = subprocess.run(['uv', 'python', 'find', '3.12', '--no-python-downloads'],
                            env=find_env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, timeout=20)
    if result.returncode or not Path(result.stdout.strip()).is_file():
        raise DemoError('Install Python 3.12, then run ./demo setup again.')
    interpreter = result.stdout.strip()
    check = subprocess.run([interpreter, '-c', 'import sys; sys.exit(sys.version_info[:2] != (3,12))'],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    if check.returncode:
        raise DemoError('Use Python 3.12 for both class environments, then run ./demo setup again.')
    children = Children()
    try:
        for directory, label in ((WORKER, 'worker'), (PROJECT, 'Mantle')):
            print('Installing the locked ' + label + ' environment from PyPI.', flush=True)
            completed(children, ['uv', 'sync', '--frozen', '--project', str(directory),
                      '--python', interpreter, '--no-python-downloads'], cwd=ROOT, env=env,
                      timeout=600, failure='Setup could not install the locked release; check network access to PyPI and rerun ./demo setup.')
            mark_environment(directory)
        print('Both Python 3.12 environments are installed. Run ./demo run.', flush=True)
    finally:
        children.close()


def require_free_ports(host="127.0.0.1"):
    for port in (8942, 5005):
        with socket.socket() as probe:
            try:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind((host, port))
            except OSError:
                raise DemoError('Port ' + str(port) + ' is in use; stop your earlier demo before ./demo run.') from None


def wait_http(process, url, timeout=45):
    until = time.monotonic() + timeout
    opener = build_opener(ProxyHandler({}))
    while time.monotonic() < until:
        if process.poll() is not None:
            raise DemoError('A demo service stopped before it was ready; check the released class pin and run ./demo setup.')
        try:
            with opener.open(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise DemoError('The demo did not become ready in time; stop it and check the class release before retrying.')


def start_inspector(children, env, mode):
    argv = [str(python_at(PROJECT)), str(Path(__file__).resolve()), '_inspector', mode]
    process = children.start(argv, cwd=PROJECT, env=env)
    try:
        wait_http(process, 'http://' + env.get('BRIEFING_DEMO_HOST', '127.0.0.1') + ':5005/webhooks/inspector/inspect.html', timeout=90)
        return process, env
    except DemoError:
        if not env.get('DEEPGRAM_API_KEY', '').strip():
            raise
        children.stop(process)
        text_env = env.copy()
        text_env.pop('DEEPGRAM_API_KEY', None)
        print(VOICE_FAILED_TEXT, flush=True)
        process = children.start(argv, cwd=PROJECT, env=text_env)
        wait_http(process, 'http://' + env.get('BRIEFING_DEMO_HOST', '127.0.0.1') + ':5005/webhooks/inspector/inspect.html', timeout=90)
        return process, text_env


def configure_native_sources(environment, scripted):
    """A managed-session model is independent from Mantle's conversation model."""
    if scripted or not environment.get('OPENAI_API_KEY', '').strip():
        return False
    if not environment.get('BRIEFING_AGENTS_MODEL', '').strip():
        environment['BRIEFING_AGENTS_MODEL'] = 'gpt-6-astra'
    return True


def run_demo(scripted=False, host="127.0.0.1"):
    try:
        require_viewer_access(host)
    except ValueError:
        raise DemoError('Tailnet Inspector has no authentication; confirm the operator-device ACL or explicit operator acceptance in BRIEFING_VIEWER_ACCESS before launch.') from None
    if os.name != 'posix':
        raise DemoError('Use macOS, Linux or WSL for this process-group launcher.')
    if not all(python_at(d).is_file() for d in (PROJECT, WORKER)):
        raise DemoError('Run ./demo setup before ./demo run.')
    require_free_ports(host)
    env = child_environment()
    env['BRIEFING_DEMO_HOST'] = host
    force_scripted = scripted
    scripted = scripted or not any(env.get(k, '').strip() for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY'))
    if scripted:
        for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
            env.pop(key, None)
    if force_scripted:
        env.pop('DEEPGRAM_API_KEY', None)
    print('RASA_LICENSE: ' + ('SET' if env.get('RASA_LICENSE', '').strip() else 'MISSING'), flush=True)
    if not env.get('RASA_LICENSE', '').strip():
        raise DemoError('Get your free Rasa Developer Edition licence at https://rasa.com/rasa-pro-developer-edition-license-key-request and set RASA_LICENSE in the example .env or your shell before rerunning ./demo run.')
    env['BRIEFING_MCP_TOKEN'] = secrets.token_urlsafe(32)
    from demo_make import CheckoutControl
    control = CheckoutControl(ROOT)
    children = Children()
    previous = {}
    def interrupt(_signum, _frame):
        raise KeyboardInterrupt
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, interrupt)
    try:
        control.start()
        print(SCRIPTED_LABEL if scripted else 'LIVE model mode; public source data stays separate from model prose.', flush=True)
        for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPGRAM_API_KEY'):
            print(key + ': ' + ('SET' if env.get(key, '').strip() else 'MISSING'), flush=True)
        doctor = [str(python_at(PROJECT)), str(ROOT / 'class_doctor.py')]
        if scripted:
            doctor.append('--scripted')
        completed(children, doctor, cwd=ROOT, env=env, timeout=30,
                  failure='The selected model path is not ready; set its key in your terminal or use ./demo run --scripted.')
        if not env.get('DEEPGRAM_API_KEY', '').strip():
            print(VOICE_OFF_TEXT, flush=True)
        completed(children, [str(python_at(PROJECT)), '-m', 'rasa', 'train'],
                  cwd=PROJECT, env=env, timeout=180,
                  failure='Mantle training failed; check the class project and its locked release before running again.')
        managed_sources = configure_native_sources(env, scripted)
        print('Managed Agents API selects real public-source tools.' if managed_sources
              else SCRIPTED_LABEL, flush=True)
        service = children.start([str(python_at(WORKER)), '-m', 'briefing', '--public-sources', '--host', host], cwd=ROOT, env=env)
        wait_http(service, 'http://' + host + ':8942/cards')
        mode = 'scripted' if scripted else 'live'
        inspector, inspector_env = start_inspector(children, env, mode)
        print('Open the demo: http://' + host + ':8942/', flush=True)
        print('Cards diagnostic: http://' + host + ':8942/cards', flush=True)
        print('Mantle Inspector diagnostic: http://' + host + ':5005/webhooks/inspector/inspect.html', flush=True)
        print('Open the page and ask, for example: Which flights are in the air heading to New York?', flush=True)
        print('Choose a flight, then say when your meeting is, for example tomorrow at 6 pm.', flush=True)
        print('Press Ctrl-C here to stop both services and their children.', flush=True)
        while True:
            if service.poll() is not None:
                raise DemoError('The source service stopped; both services are being shut down. Run ./demo setup before retrying.')
            if inspector.poll() is not None:
                if inspector_env.get('DEEPGRAM_API_KEY', '').strip():
                    children.stop(inspector)
                    inspector_env = inspector_env.copy()
                    inspector_env.pop('DEEPGRAM_API_KEY', None)
                    print(VOICE_FAILED_TEXT, flush=True)
                    inspector, inspector_env = start_inspector(children, inspector_env, mode)
                else:
                    raise DemoError('The Inspector stopped; both services are being shut down. Run ./demo setup before retrying.')
            time.sleep(0.2)
    except KeyboardInterrupt:
        print('Stopping the demo.', flush=True)
    finally:
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            try:
                children.close()
            finally:
                control.close()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def tool_record(value):
    """Decode MCP tool-result containers only; never inspect model prose."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if isinstance(value, dict):
        if value.get('status') in ('started', 'running', 'queued', 'complete', 'incomplete', 'needs_input', 'failed', 'found', 'no_results', 'unavailable', 'unsupported_destination'):
            return value
        for key in ('structuredContent', 'content', 'text', 'value'):
            found = tool_record(value.get(key))
            if found:
                return found
    if isinstance(value, list):
        for item in reversed(value):
            found = tool_record(item)
            if found:
                return found
    return None


def speech_confirmation(text):
    """A positive speech reference is not an override or a negative answer."""
    import re
    from briefing.traveller import flight_number
    words = re.findall(r"[a-z]+|[0-9]+", text.casefold())
    if not words or words[0] not in ('yes', 'yeah', 'yep', 'that'):
        return False
    allowed = {'yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'that', 'this', 'the',
               'one', 'is', 'it', 's', 'please', 'correct', 'right', 'sounds', 'good', 'works'}
    if any(word not in allowed for word in words):
        return False
    if flight_number(text) is not None:
        return False
    numbers = {'two', 'three', 'four', 'five', 'first', 'second', 'third', 'fourth', 'fifth'}
    if any(word.isdigit() or word in numbers for word in words):
        return False
    if 'one' in words and not any(word in ('that', 'the') for word in words[:words.index('one')]):
        return False
    return True


class ScriptedClient:
    """No model/network client. Deterministic selection in the ACTUAL inspector."""
    def __init__(self):
        self.count = 0

    async def acompletion(self, messages, **kwargs):
        import asyncio
        from rasa.shared.providers.llm.llm_response import LLMResponse, LLMToolCall
        self.count += 1
        users = [i for i, m in enumerate(messages) if m.get('role') == 'user']
        latest = users[-1] if users else len(messages)
        current = [tool_record(m.get('content')) for m in messages[latest + 1:] if m.get('role') == 'tool']
        current = [v for v in current if v]
        previous = [tool_record(m.get('content')) for m in messages[:latest] if m.get('role') == 'tool']
        previous = [v for v in previous if v]
        offered = {t.get('function', {}).get('name') for t in kwargs.get('tools') or []}
        briefing = next((n for n in offered if n in ('briefing', 'mcp/briefing:briefing')), None)
        finder = next((n for n in offered if n in ('find_flights', 'mcp/briefing:find_flights')), None)
        def reply(name, args, notice=None):
            return LLMResponse(id='scripted', choices=[notice] if notice else [], created=0,
                tool_calls=[LLMToolCall(id='script-' + str(self.count), tool_name=name, tool_args=args)])
        if len(current) > 12:
            return LLMResponse(id='scripted', choices=['SCRIPTED: the source check has not completed. Please retry explicitly.'], created=0)
        if not briefing:
            if 'activate' in offered:
                return reply('activate', {'target_id': 'briefing'})
            return LLMResponse(id='scripted', choices=['SCRIPTED: the briefing skill is unavailable; check the class release.'], created=0)
        if current:
            result = current[-1]
            if result.get('status') in ('started', 'running', 'queued'):
                await asyncio.sleep(0.2)
                capability = next((v['briefing_id'] for v in reversed(previous + current) if isinstance(v.get('briefing_id'), str)), None)
                if capability is None:
                    return LLMResponse(id='scripted', choices=['SCRIPTED: the source check has no usable private job state.'], created=0)
                return reply(briefing, {'action': 'get', 'briefing_id': capability})
            return LLMResponse(id='scripted', choices=['SCRIPTED: read the validated source cards and any missing-input question.'], created=0)
        text = str(messages[latest].get('content', '')) if users else ''
        capability = next((v['briefing_id'] for v in reversed(previous) if isinstance(v.get('briefing_id'), str)), None)
        from briefing.traveller import destination_hint, flight_number, TravellerQuestion
        try:
            destination = destination_hint(text)
        except TravellerQuestion:
            # Let the backend ask its ordinary clarification. Preserve the
            # exact ambiguous words, including during a selected journey.
            if capability:
                return reply(briefing, {'action': 'revise', 'briefing_id': capability, 'change': text})
            return reply(briefing, {'action': 'start', 'request': text})
        from briefing.traveller import destination_request, unknown_flight
        wants_search = any(phrase in text.lower() for phrase in ('which flights', 'find flights', 'look for flights'))
        query = destination_request(text)
        last_result = previous[-1] if previous else {}
        missing = last_result.get('needs_input')
        awaiting_flight = (last_result.get('status') == 'needs_input'
                           and isinstance(missing, dict) and missing.get('field') == 'flight')
        if unknown_flight(text) and (awaiting_flight or last_result.get('status') == 'unsupported_destination'):
            # A short answer belongs to the traveller's last stated destination,
            # not a fresh parse of "no". Do not infer a destination from a flight.
            for message in reversed(messages[:latest]):
                if message.get('role') != 'user':
                    continue
                try:
                    query = destination_request(str(message.get('content', '')))
                except TravellerQuestion:
                    break
                if query:
                    break
            if query and previous and previous[-1].get('status') == 'unsupported_destination':
                return LLMResponse(id='scripted', choices=["No problem. You don't need to answer the flight-number question again. "
                    "This demo can discover New York flights only. You can try New York, or stop here without choosing a flight."], created=0)
            if finder and query:
                return reply(finder, {'destination': query}, "I'll look for flights heading to " + query + " now.")
        if finder and query and flight_number(text) is None and (not capability or wants_search or destination is None):
            return reply(finder, {'destination': text})
        # The Inspector's opening question can create an empty briefing before
        # flight discovery. Choose from a newer search instead of revising that
        # older job; subsequent answers use the selected flight's newer job.
        capability_index = max((i for i, value in enumerate(previous)
                                if isinstance(value.get('briefing_id'), str)), default=-1)
        discovery_index = max((i for i, value in enumerate(previous)
                               if 'discovery_id' in value or 'candidates' in value), default=-1)
        discovery = previous[discovery_index] if discovery_index >= 0 else None
        if discovery and not (isinstance(discovery.get('discovery_id'), str)
                and discovery.get('status') == 'found' and discovery.get('partial') is not True
                and isinstance(discovery.get('candidates'), list) and 1 <= len(discovery['candidates']) <= 5):
            discovery = None
        if discovery and discovery_index > capability_index:
            import re
            words = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5}
            match = re.fullmatch(r'(?:the )?(first|second|third|fourth|fifth|[1-5])(?: one| flight)?[.!]?', text.strip().lower())
            choice = (words.get(match[1]) or int(match[1])) if match else None
            spoken_words = re.findall(r"[a-z]+|[0-9]+", text.casefold())
            if (spoken_words and spoken_words[0] in ('yes', 'yeah', 'that')
                    and any(word in ('no', 'not', 'never', 'dont', 'don') for word in spoken_words)):
                return LLMResponse(id='scripted', choices=["I won't select a flight from a negative confirmation. Tell me its list number or flight number when you are ready."], created=0)
            selected = flight_number(text)
            if selected:
                choice = next((row.get('choice') for row in discovery['candidates']
                               if row.get('callsign') == selected), choice)
            # A positive short answer refers only to the named suggestion from
            # this exact search. A rejected suggestion is no longer implicit.
            offered_at = max((i for i, message in enumerate(messages[:latest])
                if message.get('role') == 'tool' and (tool_record(message.get('content')) or {}).get('discovery_id') == discovery['discovery_id']), default=-1)
            declined = any(message.get('role') == 'user' and unknown_flight(str(message.get('content', '')))
                           for message in messages[offered_at + 1:latest]) if offered_at >= 0 else False
            if speech_confirmation(text) and not declined:
                from briefing.traveller import discovery_notice, suggested_flight
                try:
                    discovery_notice(discovery)  # Same validated notice as the presentation hook.
                    suggestion = suggested_flight(discovery)
                except ValueError:
                    suggestion = None
                choice = suggestion['choice'] if suggestion else None
            if choice is not None and choice <= len(discovery.get('candidates', [])):
                return reply(briefing, {'action': 'start', 'request': text,
                    'discovery_id': discovery['discovery_id'], 'choice': choice})
            if flight_number(text) is None:
                question = ("I won't select a flight without your choice. Tell me its list number or flight number when you are ready."
                            if declined else "Which flight is yours? Say a list number, such as the second one, or its flight number.")
                return LLMResponse(id='scripted', choices=[question], created=0)
        if capability:
            if text.strip().lower() in ('status', 'get', 'show cards', 'check'):
                return reply(briefing, {'action': 'get', 'briefing_id': capability})
            return reply(briefing, {'action': 'revise', 'briefing_id': capability, 'change': text})
        return reply(briefing, {'action': 'start', 'request': text})


def merge_voice_channels(values, voice):
    """Validate raw owner config through Mantle's integrations.yml parser."""
    from rasa.mantle.config.channels import parse_channels
    result = dict(values or {})
    result.update(parse_channels(voice))
    return result


def install_voice_channels(voice):
    """Patch the common Mantle channel loader in this Inspector child only."""
    from rasa.mantle.config import channels
    from rasa.shared.utils.yaml import read_yaml_file
    def runtime_channels(project_root=None):
        # The pinned loader expands unrelated model credentials before selecting
        # channels. This example owns static channel settings, so select that
        # section first and retain the engine's normal parser and validation.
        raw = read_yaml_file(Path(project_root or PROJECT) / 'integrations.yml',
                             expand_env_vars=False)
        declared = raw.get('channels') or {}
        return merge_voice_channels(channels.parse_channels(declared), voice)
    channels.load_integration_channels = runtime_channels


class SafeRunParser(argparse.ArgumentParser):
    def error(self, message):
        raise DemoError('Use ./demo run [--scripted] [--host TAILNET_ADDRESS].')


def install_mcp_host(host):
    """Runtime endpoint selection; preserve parser, token placeholder and auth."""
    from rasa.mantle.config.mcp import MCPServersSettings
    original = MCPServersSettings.to_connection_config
    def connection(settings, server_id):
        result = original(settings, server_id)
        if server_id == 'briefing' and result['url'] == 'http://127.0.0.1:8942/mcp':
            result['url'] = 'http://' + validate_host(host) + ':8942/mcp'
        return result
    MCPServersSettings.to_connection_config = connection


def inspector(mode):
    # Import the normal entrypoint before touching the pinned factory seam.
    sys.path[:0] = [str(ROOT), str(PROJECT)]
    from project.lib.capability_logging import install
    install()
    from rasa.__main__ import main as rasa_main
    # The channel loader is the pinned engine's common inspect/run seam.
    # Merge owner-supplied voice config in memory: no key/config file is written.
    try:
        from voice_config import voice_channels
    except ImportError:
        voice = {}
    else:
        voice = voice_channels(os.environ)
    install_voice_channels(voice)
    host = validate_host(os.environ.get('BRIEFING_DEMO_HOST', '127.0.0.1'))
    install_mcp_host(host)
    if os.environ.get('BRIEFING_VIEWER_AUDIT'):
        from viewer_audit import install_inspector_audit
        install_inspector_audit()
    sys.argv = ['rasa', 'inspect', '--interface', host, '--port', '5005', '--quiet']
    with ExitStack() as cleanup:
        if mode == 'scripted':
            from rasa.mantle.llm.client import LLMClient
            from rasa.mantle.model_archive import bootstrap
            # Stable Mantle resolves provider credentials before constructing
            # its client. This labelled scripted child has no provider client
            # or credential; supply only the deterministic selection seam.
            cleanup.callback(setattr, LLMClient, 'from_bootstrap', LLMClient.__dict__['from_bootstrap'])
            cleanup.callback(setattr, bootstrap, 'resolve_integration_llm_config', bootstrap.resolve_integration_llm_config)
            LLMClient.from_bootstrap = classmethod(lambda cls, bootstrap: ScriptedClient())
            bootstrap.resolve_integration_llm_config = lambda agent, project_root: {}
            from rasa.mantle.config.a2a_server import MantleA2AConfigSource
            original_a2a = MantleA2AConfigSource._read_raw_block
            # The shipped demo has no A2A server. Stable Mantle otherwise
            # expands unrelated model placeholders just to discover absence.
            def declared_a2a_only(source):
                return original_a2a(source) if source.is_declared() else None
            cleanup.callback(setattr, MantleA2AConfigSource, '_read_raw_block', original_a2a)
            MantleA2AConfigSource._read_raw_block = declared_a2a_only
        rasa_main()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if len(argv) == 2 and argv[0] == 'make-target':
            from demo_make import perform
            perform(argv[1])
        elif argv == ['setup']:
            setup()
        elif argv and argv[0] == 'run':
            parser = SafeRunParser(add_help=False)
            parser.add_argument('--host', default=os.environ.get('BRIEFING_VIEWER_HOST', '127.0.0.1'))
            parser.add_argument('--scripted', action='store_true')
            args = parser.parse_args(argv[1:])
            run_demo(scripted=args.scripted, host=args.host)
        elif argv in (['_inspector', 'scripted'], ['_inspector', 'live']):
            inspector(argv[1])
        else:
            raise DemoError('Use ./demo setup, then ./demo run; ./demo run --scripted always disables model and voice calls.')
        return 0
    except KeyboardInterrupt:
        print('Stopped; no successful demo run is claimed.')
        return 130
    except Exception:
        # Exception details from dependencies may contain secrets. Print only
        # our fixed messages; never echo an argument or subprocess diagnostics.
        error = sys.exception()
        print(str(error) if isinstance(error, DemoError) else 'The demo could not start; check Python 3.12, uv and the class checkout.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
