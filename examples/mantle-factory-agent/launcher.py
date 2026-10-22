"""Owned, expiring processes for the scripted Mantle factory demonstration."""
import argparse
from datetime import datetime, timezone
import ipaddress
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / 'project'
PYTHON = PROJECT / '.venv/bin/python'


def inspector():
    sys.path.insert(0, str(ROOT))
    from rasa.__main__ import main
    from rasa.mantle.llm.client import LLMClient
    from scripted import ScriptedClient
    from rasa.core import run
    original = run.configure_app

    def configure(*args, **kwargs):
        app = original(*args, **kwargs)

        async def access(request):
            from sanic.response import text
            from server import audit
            audit(request.ip, 'inspector')
            if request.ip not in os.environ['FACTORY_ALLOWED_PEERS'].split(','):
                return text('Viewer not allowed', status=403)
        app.register_middleware(access, 'request')
        return app
    run.configure_app = configure
    LLMClient.from_bootstrap = classmethod(lambda cls, bootstrap: ScriptedClient())
    sys.argv = ['rasa', 'inspect', '--interface', os.environ['FACTORY_HOST'], '--port', '5007', '--quiet']
    main()


def wait_ready(child, url, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError('Owned runtime exited before readiness; inspect its local log.')
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(.2)
    raise RuntimeError('Owned runtime did not become ready in time.')


def run(args):
    host = str(ipaddress.ip_address(args.host))
    if host != '127.0.0.1' and ipaddress.ip_address(host) not in ipaddress.ip_network('100.64.0.0/10'):
        raise ValueError('Use loopback or a private tailnet address.')
    if host != '127.0.0.1' and args.viewer_access != 'operator-accepted':
        raise ValueError('Tailnet Inspector has no authentication; require --viewer-access operator-accepted.')
    if args.viewer_name and not re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.ts\.net', args.viewer_name):
        raise ValueError('Viewer name must be a ts.net hostname.')
    expiry = datetime.fromisoformat(args.expires_at.replace('Z', '+00:00'))
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise ValueError('Expiry must be a future UTC timestamp.')
    for bind, port in [(host, 8947), (host, 5007), ('127.0.0.1', 8948)]:
        with socket.socket() as probe:
            probe.bind((bind, port))
    if not PYTHON.is_file():
        raise ValueError('Run ./demo setup first.')
    # Only the license enters the child. Provider keys are deliberately absent.
    license_value = os.environ.get('RASA_LICENSE', '')
    if not license_value and args.env_file:
        from dotenv import dotenv_values
        license_value = dotenv_values(args.env_file, interpolate=False).get('RASA_LICENSE', '')
    if not license_value:
        raise ValueError('RASA_LICENSE is required, including scripted mode. Obtain a free Rasa Developer Edition license.')
    allowed = {'127.0.0.1', host, *args.allow_peer}
    for peer in allowed:
        ipaddress.ip_address(peer)
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG') if k in os.environ}
    env.update(RASA_LICENSE=license_value, FACTORY_MCP_TOKEN=secrets.token_urlsafe(32),
               FACTORY_HOST=host, FACTORY_ALLOWED_PEERS=','.join(sorted(allowed)),
               FACTORY_VIEWER_NAME=args.viewer_name or host,
               FACTORY_VIEWER_AUDIT=str(runtime / 'access.jsonl'),
               RASA_ENV_FILE='', PYTHON_DOTENV_DISABLED='1', RASA_TELEMETRY_ENABLED='false', DO_NOT_TRACK='1',
               PYTHONUNBUFFERED='1', PYTHONPATH=str(ROOT))
    # No child reads a dotenv file implicitly. All secrets stay out of logs.
    children = []
    logs = []
    def stop(*_):
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGINT)
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        print('SCRIPTED selection; existing supplied attempts; real protected gate; no model or voice calls.', flush=True)
        train = subprocess.run([str(PYTHON), '-m', 'rasa', 'train'], cwd=PROJECT, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
        if train.returncode:
            raise RuntimeError('Mantle training failed; no services started.')
        for label, command, cwd in [
            ('mcp', [str(PYTHON), str(ROOT / 'server.py'), 'mcp'], ROOT),
            ('inspector', [str(PYTHON), str(ROOT / 'launcher.py'), '_inspector'], PROJECT),
            ('entry', [str(PYTHON), str(ROOT / 'server.py'), 'entry'], ROOT),
        ]:
            log = open(runtime / (label + '.log'), 'ab')
            logs.append(log)
            children.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log,
                                             stderr=subprocess.STDOUT, start_new_session=True))
        wait_ready(children[1], f'http://{host}:5007/status')
        wait_ready(children[2], f'http://{host}:8947/')
        print(f'READY http://{args.viewer_name or host}:8947/ ; expires {args.expires_at}', flush=True)
        while datetime.now(timezone.utc) < expiry:
            if any(child.poll() is not None for child in children):
                raise RuntimeError('An owned service stopped; closing the demonstration.')
            time.sleep(.25)
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        stop()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=5)
        for log in logs:
            log.close()


if __name__ == '__main__':
    if sys.argv[1:] == ['_inspector']:
        inspector()
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('command', choices=['run'])
        parser.add_argument('--host', default='127.0.0.1')
        parser.add_argument('--viewer-name', default='')
        parser.add_argument('--viewer-access', default='')
        parser.add_argument('--allow-peer', action='append', default=[])
        parser.add_argument('--env-file', help='Read only RASA_LICENSE into child memory; never copy the file.')
        parser.add_argument('--expires-at', default=datetime.now(timezone.utc).strftime('%Y-%m-%dT16:30:00Z'))
        args = parser.parse_args()
        try:
            run(args)
        except (ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(1)
