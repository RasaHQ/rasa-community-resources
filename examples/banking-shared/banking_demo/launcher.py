"""One-command teaching host; no secrets are printed or written to config."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode


def inspector_address(port):
    name = os.environ.get('CODESPACE_NAME')
    if name:
        domain = os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', 'app.github.dev')
        origin = f'https://{name}-{port}.{domain}'
    else:
        origin = f'http://localhost:{port}'
    return origin, origin + '/webhooks/inspector/inspect.html?' + urlencode(
        {'projectUrl': origin, 'channel': 'inspector'})


def main(project):
    parser = argparse.ArgumentParser(description='Start the fictional banking teaching host and Inspector.')
    parser.add_argument('--port', type=int, default=5005)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('choose an unprivileged Inspector port')
    project = Path(project).resolve()
    from dotenv import load_dotenv
    load_dotenv(project / '.env', override=False)
    missing = [key for key in ('RASA_PRO_LICENSE', 'OPENAI_API_KEY', 'DEEPGRAM_API_KEY')
               if not os.environ.get(key, '').strip()]
    if missing:
        print('Not ready. The operator must configure these Codespaces secret names: ' + ', '.join(missing))
        return 2
    from importlib.metadata import version
    expected = '3.21.0.dev5'
    if version('rasa-pro') != expected:
        print('Not ready. Rebuild the locked project environment; the runtime pin differs.')
        return 2
    from rasa.mantle.model_archive.snapshot import package_model_archive
    from rasa.shared.utils.yaml import read_yaml_file, write_yaml
    from .client import HostClient
    settings = json.loads((project / 'demo.json').read_text())
    origin, inspector_url = inspector_address(args.port)
    server = None
    inspector = None
    try:
        # Keep ownership until the child inherits the listening descriptor.
        # Closing and rebinding the selected port would leave a local race.
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            reservation.listen(128)
            backend_port = reservation.getsockname()[1]
            environment = dict(os.environ)
            environment['BANKING_HOST_URL'] = f'http://127.0.0.1:{backend_port}'
            environment['BANKING_HOST_CAPABILITY'] = secrets.token_urlsafe(32)
            backend_environment = {key: value for key, value in os.environ.items()
                if key in {'PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'PYTHONPATH', 'SYSTEMROOT'}}
            backend_environment['BANKING_HOST_CAPABILITY'] = environment['BANKING_HOST_CAPABILITY']
            command = [sys.executable, '-m', 'banking_demo.launcher', settings['profile'],
                       str(reservation.fileno())]
            server = subprocess.Popen(command, env=backend_environment,
                                      pass_fds=(reservation.fileno(),))
        host = HostClient(environment['BANKING_HOST_URL'], environment['BANKING_HOST_CAPABILITY'])
        deadline = time.monotonic() + 20
        while True:
            if server.poll() is not None:
                raise RuntimeError('backend_exited')
            try:
                session = host.open_session()
                host.reset(session)
                break
            except ValueError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('backend_not_ready') from None
                time.sleep(.1)
        with tempfile.TemporaryDirectory(prefix='banking-run-') as directory:
            run = Path(directory)
            result = package_model_archive(str(project / 'agent.yml'), str(run / 'models'),
                                           fixed_model_name='banking', validate=True)
            if result.code:
                raise RuntimeError('agent_validation_failed')
            integrations = read_yaml_file(project / 'integrations.yml', expand_env_vars=False)
            integrations['channels']['inspector']['server_url'] = origin
            write_yaml(integrations, run / 'integrations.yml')
            (run / 'agent.yml').write_bytes((project / 'agent.yml').read_bytes())
            print('Mode: shared banking contract with fictional data; illustrative vendor mapping only.')
            print('Identity: one private teaching host, fixed simulated caller; not real bank sign-in.')
            print('Only fictional speech. The provider receives audio; request opt-out is not zero retention.')
            print('Inspector (keep the forwarded port private): ' + inspector_url, flush=True)
            print('Press Ctrl+C here to stop both owned services.', flush=True)
            inspector = subprocess.Popen([sys.executable, '-m', 'rasa', 'inspect', '--port', str(args.port),
                                          '--model', str(result.model)], cwd=run, env=environment)
            while inspector.poll() is None:
                if server.poll() is not None:
                    raise RuntimeError('backend_exited')
                time.sleep(.2)
            return inspector.returncode
    except KeyboardInterrupt:
        return 0
    except Exception:
        print('Not ready. An owned service failed; no secret or raw service error is exposed.')
        return 1
    finally:
        for child in (inspector, server):
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)


def _serve_backend():
    """Private child entrypoint: consume the already-bound loopback descriptor."""
    from .server import create_app
    import uvicorn
    profile, descriptor = sys.argv[1:]
    app = create_app(profile, os.environ.get('BANKING_HOST_CAPABILITY', ''), domain_fixture=True)
    uvicorn.run(app, fd=int(descriptor), access_log=False, log_level='warning')


if __name__ == '__main__':
    _serve_backend()
