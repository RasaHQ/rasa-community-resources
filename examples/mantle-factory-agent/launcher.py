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
import threading
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / 'project'
PYTHON = PROJECT / '.venv/bin/python'


def capture_log(process, log, environment):
    """Redact runtime credentials before any child output reaches disk."""
    values = [environment.get(k, '') for k in ('RASA_LICENSE', 'OPENAI_API_KEY', 'DEEPGRAM_API_KEY', 'FACTORY_MCP_TOKEN')]
    for raw in iter(process.stdout.readline, b''):
        text = raw.decode('utf-8', errors='replace')
        for value in values:
            if value:
                text = text.replace(value, '[credential redacted]')
                for i in range(max(0, len(value) - 7)):
                    text = text.replace(value[i:i + 8], '[credential fragment redacted]')
        log.write(text.encode()); log.flush()


def install_mcp_port(port):
    """Keep the valid checked-in URL, select the owner port only at connection time."""
    from rasa.mantle.config.mcp import MCPServersSettings
    original = MCPServersSettings.to_connection_config
    def connection(settings, server_id):
        result = original(settings, server_id)
        if server_id == 'factory' and result['url'] == 'http://127.0.0.1:8948/mcp':
            result['url'] = f'http://127.0.0.1:{port}/mcp'
        return result
    MCPServersSettings.to_connection_config = connection


def inspector():
    sys.path.insert(0, str(ROOT))
    from rasa.__main__ import main
    install_mcp_port(int(os.environ['FACTORY_MCP_PORT']))
    from rasa.mantle.llm.client import LLMClient
    from scripted import ScriptedClient
    from rasa.core import run
    from rasa.mantle.config import channels
    from rasa.shared.utils.yaml import read_yaml_file
    from voice_config import voice_channels
    voice = voice_channels(os.environ)
    if voice:
        def runtime_channels(project_root=None):
            raw = read_yaml_file(Path(project_root or PROJECT) / 'integrations.yml', expand_env_vars=False)
            result = dict(channels.parse_channels(raw.get('channels') or {}))
            result.update(channels.parse_channels(voice))
            return result
        channels.load_integration_channels = runtime_channels
        import voice_patch
        voice_patch.install()
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
    if os.environ.get('FACTORY_MANTLE_MODE', 'SCRIPTED') == 'SCRIPTED':
        LLMClient.from_bootstrap = classmethod(lambda cls, bootstrap: ScriptedClient())
    sys.argv = ['rasa', 'inspect', '--interface', os.environ['FACTORY_HOST'], '--port', os.environ['FACTORY_INSPECTOR_PORT'], '--quiet']
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
    ports = (args.entry_port, args.inspector_port, args.mcp_port)
    if any(not 1 <= port <= 65535 for port in ports) or len(set(ports)) != 3:
        raise ValueError('Use three distinct ports between 1 and 65535.')
    for bind, port in [(host, args.entry_port), (host, args.inspector_port), ('127.0.0.1', args.mcp_port)]:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((bind, port))
    if args.builder_mode == 'LIVE' and not Path(args.worker_python).is_file():
        raise ValueError('LIVE builder needs a separate worker: run ./demo setup-live first.')
    if not PYTHON.is_file():
        raise ValueError('Run ./demo setup first.')
    # The license enters runtime children; Deepgram goes only to the opted-in Inspector.
    license_value = os.environ.get('RASA_LICENSE', '')
    if not license_value and args.env_file:
        from dotenv import dotenv_values
        license_value = dotenv_values(args.env_file, interpolate=False).get('RASA_LICENSE', '')
    if not license_value:
        raise ValueError('RASA_LICENSE is required, including scripted mode. Obtain a free Rasa Developer Edition license.')
    voice_key = ''
    if args.voice:
        from dotenv import dotenv_values
        voice_key = (dotenv_values(args.env_file, interpolate=False).get('DEEPGRAM_API_KEY', '') if args.env_file else '')
        if not voice_key or not voice_key.strip():
            raise ValueError('Voice needs DEEPGRAM_API_KEY in the owner credential file.')
    mantle_key = ''
    mantle_mode = getattr(args, 'mantle_mode', 'SCRIPTED')
    if mantle_mode == 'LIVE':
        from dotenv import dotenv_values
        mantle_key = (dotenv_values(args.env_file, interpolate=False).get('OPENAI_API_KEY', '') if args.env_file else '')
        if not mantle_key or not mantle_key.strip():
            raise ValueError('Live Mantle needs OPENAI_API_KEY in the owner credential file.')
    allowed = {'127.0.0.1', host, *args.allow_peer}
    for peer in allowed:
        ipaddress.ip_address(peer)
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG') if k in os.environ}
    env.update(RASA_LICENSE=license_value, FACTORY_MCP_TOKEN=secrets.token_urlsafe(32),
               FACTORY_HOST=host, FACTORY_ALLOWED_PEERS=','.join(sorted(allowed)),
               FACTORY_ENTRY_PORT=str(args.entry_port),
               FACTORY_INSPECTOR_PORT=str(args.inspector_port),
               FACTORY_MCP_PORT=str(args.mcp_port),
               FACTORY_MCP_URL=f'http://127.0.0.1:{args.mcp_port}/mcp',
               FACTORY_VIEWER_NAME=args.viewer_name or host,
               FACTORY_BUILDER_MODE=args.builder_mode,
               FACTORY_MANTLE_MODE=mantle_mode,
               FACTORY_WORKER_PYTHON=str(Path(args.worker_python).absolute()) if args.builder_mode == 'LIVE' else str(PYTHON),
               FACTORY_ENV_FILE=str(Path(args.env_file).resolve()) if args.env_file else '',
               FACTORY_EVIDENCE_ROOT=str(Path(args.evidence_root).resolve()),
               FACTORY_EXPIRES_AT=args.expires_at,
               FACTORY_VIEWER_AUDIT=str(runtime / 'access.jsonl'),
               RASA_ENV_FILE='', PYTHON_DOTENV_DISABLED='1', RASA_TELEMETRY_ENABLED='false', DO_NOT_TRACK='1',
               PYTHONUNBUFFERED='1', PYTHONPATH=str(ROOT))
    # No child reads a dotenv file implicitly. All secrets stay out of logs.
    children = []
    logs = []
    log_threads = []
    def stop(*_):
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGINT)
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        print('Mantle selection ' + mantle_mode + '; builder mode ' + args.builder_mode + '; protected gate; no voice qualification.', flush=True)
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
            child_env = dict(env)
            if label == 'inspector':
                if voice_key:
                    child_env['DEEPGRAM_API_KEY'] = voice_key
                if mantle_key:
                    child_env['OPENAI_API_KEY'] = mantle_key
            process = subprocess.Popen(command, cwd=cwd, env=child_env, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            children.append(process)
            thread = threading.Thread(target=capture_log, args=(process, log, child_env), daemon=True)
            log_threads.append(thread)
            thread.start()
        wait_ready(children[1], f'http://{host}:{args.inspector_port}/status')
        wait_ready(children[2], f'http://{host}:{args.entry_port}/')
        print(f'READY http://{args.viewer_name or host}:{args.entry_port}/ ; expires {args.expires_at}', flush=True)
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
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)
        for thread in log_threads:
            thread.join(timeout=5)
        for log in logs:
            log.close()


if __name__ == '__main__':
    if sys.argv[1:] == ['_inspector']:
        inspector()
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('command', choices=['run'])
        parser.add_argument('--voice', action='store_true', help='Enable Deepgram in the Inspector child only.')
        parser.add_argument('--host', default='127.0.0.1')
        parser.add_argument('--entry-port', type=int, default=8947)
        parser.add_argument('--inspector-port', type=int, default=5007)
        parser.add_argument('--mcp-port', type=int, default=8948)
        parser.add_argument('--viewer-name', default='')
        parser.add_argument('--viewer-access', default='')
        parser.add_argument('--allow-peer', action='append', default=[])
        parser.add_argument('--mantle-mode', type=str.upper, choices=['SCRIPTED', 'LIVE'], default='SCRIPTED', help='LIVE uses the configured OpenAI orchestrator; SCRIPTED keeps the teaching fallback.')
        parser.add_argument('--builder-mode', type=str.upper, choices=['SCRIPTED', 'LIVE'], default='SCRIPTED')
        parser.add_argument('--worker-python', default=str(ROOT / 'worker/.venv/bin/python'))
        parser.add_argument('--evidence-root', default=str(ROOT / '.runtime/factory-evidence'))
        parser.add_argument('--env-file', help='Owner credential file: launcher reads RASA_LICENSE; the LIVE tool reads OPENAI_API_KEY for the builder child only.')
        parser.add_argument('--expires-at', default=datetime.now(timezone.utc).strftime('%Y-%m-%dT16:30:00Z'))
        args = parser.parse_args()
        try:
            run(args)
        except (ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(1)
