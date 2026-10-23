"""Scripted and LIVE teaching requests through the existing protected factory.

sow: software-factories-masterclass-SOW-02
SCRIPTED is keyless. LIVE uses the existing Chapter 5 Agents API builder in a
separate worker, with the key in that child only. Neither mode integrates code
into the running product.
"""
import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def _pack(chapter='ch06'):
    here = Path(__file__).resolve()
    relative = Path('workshops/software-factories-masterclass/book/ready') / chapter
    for root in (here.parents[2], here.parent / 'source'):
        candidate = root / relative
        if (candidate / 'run_a6.py').is_file():
            return candidate
    raise FileNotFoundError('Chapter 6 teaching pack is missing')


def _run(arguments, cwd, timeout, *, python=None, key=None):
    # The verifier gives its candidate children their own OS no-network sandbox.
    # Give the entire invocation a process group so a timeout leaves no children.
    environment = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent',
                   'PYTHONDONTWRITEBYTECODE': '1'}
    if key:
        environment['OPENAI_API_KEY'] = key
    with subprocess.Popen(
        [str(python or sys.executable), '-I', *arguments], cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,
    ) as child:
        try:
            stdout, stderr = child.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.communicate()
            raise
        return child.returncode, stdout, stderr


def _fingerprint(attempt):
    """SHA256 of sorted relative paths and bytes, each framed by its byte length."""
    digest = hashlib.sha256()
    for path in sorted(p for p in attempt.rglob('*') if p.is_file()):
        for value in (path.relative_to(attempt).as_posix().encode(), path.read_bytes()):
            digest.update(len(value).to_bytes(8, 'big'))
            digest.update(value)
    return digest.hexdigest()


def _live(result, *, worker_python, evidence_root, env_file, max_funded_runs):
    """One bounded native build. Repeated/concurrent calls cannot reset the budget."""
    deadline = time.monotonic() + 330
    root = Path(evidence_root or Path.home() / '.cache/mantle-factory-agent').resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / 'funded.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            result['reason'] = 'Factory busy; no second build was started.'
            return
        ledger = root / 'funded-runs.json'
        used = json.loads(ledger.read_text()) if ledger.exists() else {'used': 0}
        if type(used.get('used')) is not int or used['used'] < 0:
            result['reason'] = 'The funded-run ledger is invalid; use SCRIPTED mode.'
            return
        if max_funded_runs is not None and used['used'] >= max_funded_runs:
            result['reason'] = 'The configured funded runs are used; use SCRIPTED mode.'
            return
        python = str(worker_python or sys.executable)
        check = 'from importlib.metadata import version; assert version("zeocore")=="0.35.6"; assert version("openai")=="3.36.1"'
        code, _, _ = _run(['-c', check], root, 15, python=python)
        if code:
            result['reason'] = 'Use the separate Python 3.12 worker with the Chapter 5 dependency pins.'
            return
        # Read this one key into the build child only, without modifying os.environ.
        from dotenv import dotenv_values
        key = dotenv_values(env_file or Path.cwd() / '.env').get('OPENAI_API_KEY')
        if not isinstance(key, str) or not key.strip():
            result['reason'] = 'The LIVE builder key is missing; use SCRIPTED mode.'
            return
        directory = Path(tempfile.mkdtemp(prefix='live-', dir=root))
        directory.chmod(0o700)
        work = directory / 'ch05'
        shutil.copytree(_pack('ch05'), work, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        task_path = work / 'tasks/b-limit-currencies.json'
        task = json.loads(task_path.read_text())
        task['limit'] = 3
        task_path.write_text(json.dumps(task, indent=2) + '\n')
        # Reserve before starting; failures also consume a slot. No automatic retry.
        used['used'] += 1
        temporary = root / 'funded-runs.pending'
        temporary.write_text(json.dumps(used) + '\n')
        temporary.replace(ledger)
        result['reason'] = 'Expected cost 15–150 cents, not a monetary cap. Actual cost is unmeasured.'
        code, _, _ = _run([
            'build.py', 'tasks/b-limit-currencies.json', 'attempts/live', '--live',
            '--model', 'gpt-6-astra', '--expected-cost-cents-min', '15',
            '--expected-cost-cents-max', '150',
        ], work, min(300, max(1, deadline - time.monotonic())), python=python, key=key.strip())
        native = work / 'runs/live/run/native.json'
        if native.exists():
            result['builder_calls'] = len(json.loads(native.read_text()).get('tools_called', []))
        attempt = work / 'attempts/live'
        if code or not attempt.is_dir():
            result['reason'] = 'The LIVE builder did not export an accepted attempt; no retry. Expected cost 15–150 cents; actual cost unmeasured.'
            return
        # build.py already judges its candidate before export. Independently rerun
        # the unchanged chapter gate on precisely those exported bytes.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            result['reason'] = 'The LIVE call reached its deadline; no retry.'
            return
        code, stdout, _ = _run(['run_a6.py', str(task_path), str(attempt)], work,
                               min(120, remaining), python=python)
        _verdict(result, code, stdout)
        if result['verdict'] in ('ACCEPT', 'REJECT'):
            result['fingerprint'] = _fingerprint(attempt)


def _verdict(result, code, stdout):
    if code == 0 and stdout.startswith('ACCEPT - protected acceptance passed'):
        result['verdict'] = 'ACCEPT'
    elif code == 1 and stdout.startswith('REJECT -'):
        failures = re.findall(r'\btest_[a-zA-Z0-9_]+', stdout)
        if failures:
            result['verdict'] = 'REJECT'
            result['failing_test'] = failures[0]
        else:
            result['reason'] = 'The protected gate did not produce a named test verdict.'
    else:
        result['reason'] = 'The protected gate could not run to completion.'


def run_factory(request: str, *, mode='SCRIPTED', worker_python=None,
                evidence_root=None, env_file=None, max_funded_runs=12) -> dict:
    """Judge 'good' or 'ignores-limit'; every call uses a fresh copy.

    The good attempt is written for a limit of three by the existing scripted
    builder or, in LIVE mode, the Chapter 5 gpt-6-astra Agents API builder.
    The bad attempt is always the existing SCRIPTED b-ignores-limit fixture.
    LIVE needs its own pinned worker, child-only env_file key and persistent
    evidence_root. The default funded-run limit is 12; the durable count survives
    restarts. Model choice is fixed; the builder itself never retries.
    NOT_READY means no usable verdict was obtained; it never implies ACCEPT.
    """
    started = time.monotonic()
    mode = mode.upper() if isinstance(mode, str) else ''
    result = {'verdict': 'NOT_READY', 'failing_test': None, 'mode': mode,
              'builder_calls': 0, 'fingerprint': '', 'seconds': 0.0}
    try:
        if request not in ('good', 'ignores-limit'):
            result['reason'] = 'Use request kind good or ignores-limit.'
            return result
        if mode not in ('SCRIPTED', 'LIVE'):
            result['reason'] = 'Use SCRIPTED or LIVE mode.'
            return result
        if max_funded_runs is not None and (type(max_funded_runs) is not int or max_funded_runs < 1):
            result['reason'] = 'Use a positive funded-run limit or leave it unset.'
            return result
        if shutil.which('sandbox-exec') is None:
            result['reason'] = 'The protected gate requires macOS sandbox-exec.'
            return result
        if request == 'ignores-limit':
            result['mode'] = 'SCRIPTED'
        elif mode == 'LIVE':
            _live(result, worker_python=worker_python, evidence_root=evidence_root, env_file=env_file,
                  max_funded_runs=max_funded_runs)
            return result
        with tempfile.TemporaryDirectory(prefix='mantle-factory-agent-') as directory:
            work = Path(directory) / 'ch06'
            shutil.copytree(_pack(), work, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            task_path = work / 'tasks/b-limit-currencies.json'
            task = json.loads(task_path.read_text())
            task['limit'] = 3
            task_path.write_text(json.dumps(task, indent=2) + '\n')
            attempt = work / 'attempts' / ('mine' if request == 'good' else 'b-ignores-limit')
            if request == 'good':
                if attempt.exists():
                    shutil.rmtree(attempt)
                code, _, _ = _run(['scripted_builder.py', str(task_path), str(attempt)], work, 15, python=worker_python)
                if code:
                    result['reason'] = 'The scripted builder could not prepare an attempt.'
                    return result
            result['fingerprint'] = _fingerprint(attempt)
            code, stdout, _ = _run(['run_a6.py', str(task_path), str(attempt)], work, 200, python=worker_python)
            _verdict(result, code, stdout)
    except (OSError, ValueError, ImportError, subprocess.TimeoutExpired):
        result['reason'] = 'The offline factory could not run; no acceptance is claimed.'
    finally:
        result['seconds'] = round(time.monotonic() - started, 3)
    return result
