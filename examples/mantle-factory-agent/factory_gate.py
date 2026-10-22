"""Offline teaching requests through the unchanged Chapter 6 protected gate.

sow: software-factories-masterclass-SOW-02
No model, provider client, credentials, or product integration is used here.
"""
import hashlib
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


def _pack():
    here = Path(__file__).resolve()
    relative = Path('workshops/software-factories-masterclass/book/ready/ch06')
    for root in (here.parents[2], here.parent / 'source'):
        candidate = root / relative
        if (candidate / 'run_a6.py').is_file():
            return candidate
    raise FileNotFoundError('Chapter 6 teaching pack is missing')


def _run(arguments, cwd, timeout):
    # The verifier gives its candidate children their own OS no-network sandbox.
    # Give the entire invocation a process group so a timeout leaves no children.
    with subprocess.Popen(
        [sys.executable, '-I', *arguments], cwd=cwd,
        env={'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent',
             'PYTHONDONTWRITEBYTECODE': '1'},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,
    ) as child:
        try:
            stdout, stderr = child.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
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


def run_factory(request: str) -> dict:
    """Judge 'good' or 'ignores-limit' offline; every call uses a fresh copy.

    The good attempt is written by the existing labelled scripted builder for a
    limit of three. The bad attempt is the existing b-ignores-limit fixture.
    NOT_READY means no usable verdict was obtained; it never implies ACCEPT.
    """
    started = time.monotonic()
    result = {'verdict': 'NOT_READY', 'failing_test': None,
              'fingerprint': '', 'seconds': 0.0}
    try:
        if request not in ('good', 'ignores-limit'):
            result['reason'] = 'Use request kind good or ignores-limit.'
            return result
        if shutil.which('sandbox-exec') is None:
            result['reason'] = 'The protected gate requires macOS sandbox-exec.'
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
                code, _, _ = _run(['scripted_builder.py', str(task_path), str(attempt)], work, 15)
                if code:
                    result['reason'] = 'The scripted builder could not prepare an attempt.'
                    return result
            result['fingerprint'] = _fingerprint(attempt)
            code, stdout, _ = _run(['run_a6.py', str(task_path), str(attempt)], work, 200)
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
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result['reason'] = 'The offline factory could not run; no acceptance is claimed.'
    finally:
        result['seconds'] = round(time.monotonic() - started, 3)
    return result
