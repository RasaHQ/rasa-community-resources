"""Local class entrypoint; real Mantle inspector, explicitly scripted without keys.

sow: software-factories-masterclass-SOW-02
No installed engine files are changed. The keyless child supplies deterministic
LLM responses at the pinned engine's LLMClient factory; everything downstream is
actual engine orchestration, MCP, hooks and the Inspector channel.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import tomllib
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / 'project'
WORKER = ROOT / 'worker'
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


def child_environment():
    env = os.environ.copy()
    # Caches and generated data stay in this owned example. Never load dotenv.
    cache = ROOT / '.demo-cache'
    cache.mkdir(exist_ok=True)
    (cache / 'tmp').mkdir(exist_ok=True)
    for name in list(env):
        if name.startswith(('UV_', 'PIP_')):
            env.pop(name)
    env.update(UV_CACHE_DIR=str(cache / 'uv'), UV_NO_CONFIG='1', UV_NO_ENV_FILE='1',
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

    def start(self, argv, *, cwd, env):
        process = subprocess.Popen(argv, cwd=cwd, env=env, start_new_session=True,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        self.processes.append(process)
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
    env = child_environment()
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
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    if check.returncode:
        raise DemoError('Use Python 3.12 for both class environments, then run ./demo setup again.')
    children = Children()
    try:
        for directory, label in ((WORKER, 'worker'), (PROJECT, 'Mantle')):
            print('Installing the locked ' + label + ' environment from PyPI.', flush=True)
            completed(children, ['uv', 'sync', '--frozen', '--project', str(directory),
                      '--python', interpreter, '--no-python-downloads'], cwd=ROOT, env=env,
                      timeout=600, failure='Setup could not install the locked release; check network access to PyPI and rerun ./demo setup.')
        print('Both Python 3.12 environments are installed. Run ./demo run.', flush=True)
    finally:
        children.close()


def require_free_ports():
    for port in (8942, 5005):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
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
        wait_http(process, 'http://127.0.0.1:5005/webhooks/inspector/inspect.html', timeout=90)
        return process, env
    except DemoError:
        if not env.get('DEEPGRAM_API_KEY', '').strip():
            raise
        children.stop(process)
        text_env = env.copy()
        text_env.pop('DEEPGRAM_API_KEY', None)
        print('Inspector with voice was unavailable; retrying in text.', flush=True)
        process = children.start(argv, cwd=PROJECT, env=text_env)
        wait_http(process, 'http://127.0.0.1:5005/webhooks/inspector/inspect.html', timeout=90)
        return process, text_env


def run_demo(scripted=False):
    if os.name != 'posix':
        raise DemoError('Use macOS, Linux or WSL for this process-group launcher.')
    if not all(python_at(d).is_file() for d in (PROJECT, WORKER)):
        raise DemoError('Run ./demo setup before ./demo run.')
    require_free_ports()
    env = child_environment()
    force_scripted = scripted
    scripted = scripted or not any(env.get(k, '').strip() for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY'))
    if scripted:
        for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
            env.pop(key, None)
    if force_scripted:
        env.pop('DEEPGRAM_API_KEY', None)
    print('RASA_LICENSE: ' + ('SET' if env.get('RASA_LICENSE', '').strip() else 'MISSING'), flush=True)
    if not env.get('RASA_LICENSE', '').strip():
        raise DemoError('Rasa Inspector needs a free Rasa Developer Edition licence: set RASA_LICENSE in your own terminal, then rerun ./demo run. Scripted mode needs no model key.')
    env['BRIEFING_MCP_TOKEN'] = secrets.token_urlsafe(32)
    # No .env loader may introduce credentials into either process.
    for directory in (ROOT, PROJECT, WORKER):
        if any(directory.glob('.env')) or any(directory.glob('.env.*')):
            # .env.example is documentation only.
            if any(p.name != '.env.example' for p in [*directory.glob('.env'), *directory.glob('.env.*')]):
                raise DemoError('Remove runtime dotenv files from this demo; supply credentials only in your terminal environment.')
    children = Children()
    previous = {}
    def interrupt(_signum, _frame):
        raise KeyboardInterrupt
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, interrupt)
    try:
        print(SCRIPTED_LABEL if scripted else 'LIVE model mode; public source data stays separate from model prose.', flush=True)
        for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPGRAM_API_KEY'):
            print(key + ': ' + ('SET' if env.get(key, '').strip() else 'MISSING'), flush=True)
        doctor = [str(python_at(PROJECT)), str(ROOT / 'class_doctor.py')]
        if scripted:
            doctor.append('--scripted')
        completed(children, doctor, cwd=ROOT, env=env, timeout=30,
                  failure='The selected model path is not ready; set its key in your terminal or use ./demo run --scripted.')
        if not env.get('DEEPGRAM_API_KEY', '').strip():
            print('Voice is off; continue in text.', flush=True)
        completed(children, [str(python_at(PROJECT)), '-m', 'rasa', 'train'],
                  cwd=PROJECT, env=env, timeout=180,
                  failure='Mantle training failed; check the class project and its locked release before running again.')
        service = children.start([str(python_at(WORKER)), '-m', 'briefing', '--public-sources'], cwd=ROOT, env=env)
        wait_http(service, 'http://127.0.0.1:8942/cards')
        mode = 'scripted' if scripted else 'live'
        inspector, inspector_env = start_inspector(children, env, mode)
        print('Cards: http://127.0.0.1:8942/cards', flush=True)
        print('Mantle inspector: http://127.0.0.1:5005/webhooks/inspector/inspect.html', flush=True)
        print('Enter your journey: callsign=TEST123 meeting=2026-10-22T21:00:00Z transfer=45', flush=True)
        print('TEST123 is syntax, not a promised airborne flight. Use an actual callsign for available flight data.', flush=True)
        print('Press Ctrl-C here to stop both services and their children.', flush=True)
        while True:
            if service.poll() is not None:
                raise DemoError('The source service stopped; both services are being shut down. Run ./demo setup before retrying.')
            if inspector.poll() is not None:
                if inspector_env.get('DEEPGRAM_API_KEY', '').strip():
                    children.stop(inspector)
                    inspector_env = inspector_env.copy()
                    inspector_env.pop('DEEPGRAM_API_KEY', None)
                    print('Inspector stopped; retrying once without voice.', flush=True)
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
            children.close()
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
        if value.get('status') in ('started', 'running', 'queued', 'complete', 'incomplete', 'needs_input', 'failed'):
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
        def reply(name, args):
            return LLMResponse(id='scripted', choices=[], created=0,
                tool_calls=[LLMToolCall(id='script-' + str(self.count), tool_name=name, tool_args=args)])
        if self.count > 12:
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
        if capability:
            if text.strip().lower() in ('status', 'get', 'show cards', 'check'):
                return reply(briefing, {'action': 'get', 'briefing_id': capability})
            return reply(briefing, {'action': 'revise', 'briefing_id': capability, 'change': text})
        return reply(briefing, {'action': 'start', 'request': text})


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
    if voice:
        from rasa.mantle.config import channels
        original = channels.load_integration_channels
        def runtime_channels(project_root=None):
            values = dict(original(project_root) or {})
            values.update(voice)
            return values
        channels.load_integration_channels = runtime_channels
    if mode == 'scripted':
        from rasa.mantle.llm.client import LLMClient
        LLMClient.from_bootstrap = classmethod(lambda cls, bootstrap: ScriptedClient())
    sys.argv = ['rasa', 'inspect', '--interface', '127.0.0.1', '--port', '5005', '--quiet']
    rasa_main()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv == ['setup']:
            setup()
        elif argv in (['run'], ['run', '--scripted']):
            run_demo(scripted='--scripted' in argv)
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
