"""Friendly Make targets and checkout-owned lifecycle controls.

"""
import errno
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import stat
import subprocess
import threading
import time

# Keep imports lazy so demo_launcher remains the single command entrypoint.
def launcher():
    import demo_launcher
    return demo_launcher


PURPOSES = {
    'help': 'Show the demo commands in the order to use them.',
    'env': 'Create a private credential file without overwriting your values.',
    'setup': 'Install the two locked Python 3.12 environments.',
    'doctor': 'Check readiness and show credential names as SET or MISSING.',
    'run': 'Start the real Inspector and source-card page.',
    'run-scripted': 'Start the labelled scripted text path without model or voice calls.',
    'test': 'Run the example controls without live provider calls.',
    'stop': 'Stop only the demo launched from this checkout.',
    'clean': 'Remove this checkout’s marked local environments and cache; keep .env.',
}
SOURCES = {
    'RASA_LICENSE': 'https://rasa.com/rasa-pro-developer-edition-license-key-request',
    'OPENAI_API_KEY': 'https://platform.openai.com/api-keys',
    'ANTHROPIC_API_KEY (optional)': 'https://console.anthropic.com/settings/keys',
    'DEEPGRAM_API_KEY (optional)': 'https://console.deepgram.com/signup',
}


def runtime_directory(root):
    demo = launcher()
    directory = Path(root) / '.demo-runtime'
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise demo.DemoError('The checkout runtime directory is unsafe; use a private regular .demo-runtime directory.')
    return directory


def control_address(root):
    address = os.path.relpath(Path(root) / '.demo-runtime' / 'control.sock')
    if len(os.fsencode(address)) > 100:
        raise launcher().DemoError('Run the command from the demo directory so its local control socket can be used.')
    return address


class CheckoutControl:
    """No PID files: stop talks only to the socket this invocation owns."""
    def __init__(self, root):
        self.root = Path(root)
        self.server = None
        self.thread = None
        self.identity = None
        self.closed = threading.Event()

    def start(self):
        demo = launcher()
        directory = runtime_directory(self.root)
        self.path = directory / 'control.sock'
        if self.path.exists() or self.path.is_symlink():
            raise demo.DemoError('This checkout already has a demo control socket; run make stop before starting another demo.')
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(control_address(self.root))
            self.identity = self.path.lstat().st_ino
            self.path.chmod(0o600)
            server.listen(1)
            server.settimeout(0.2)
        except BaseException:
            server.close()
            raise
        self.server = server
        def serve():
            while not self.closed.is_set():
                try:
                    connection, _ = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    return
                with connection:
                    connection.settimeout(1)
                    try:
                        if connection.recv(16) != b'STOP\n':
                            continue
                        connection.sendall(b'STOPPING\n')
                    except OSError:
                        continue
                # Existing launcher signal handling cleans both child groups.
                os.kill(os.getpid(), signal.SIGINT)
                return
        self.thread = threading.Thread(target=serve, daemon=True)
        self.thread.start()

    def close(self):
        self.closed.set()
        if self.server is not None:
            self.server.close()
        if self.thread is not None:
            self.thread.join(timeout=2)
        if self.identity is not None:
            try:
                if self.path.lstat().st_ino == self.identity:
                    self.path.unlink()
            except FileNotFoundError:
                pass


def stop_checkout(root):
    demo = launcher()
    path = Path(root) / '.demo-runtime' / 'control.sock'
    if not path.exists() and not path.is_symlink():
        print('No demo is running from this checkout.', flush=True)
        return
    info = path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise demo.DemoError('The demo control socket is unsafe; no process was signalled.')
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(control_address(root))
            client.sendall(b'STOP\n')
            if client.recv(32) != b'STOPPING\n':
                raise demo.DemoError('The checkout did not confirm shutdown; no other process was signalled.')
        deadline = time.monotonic() + 12
        while path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        if path.exists():
            raise demo.DemoError('The checkout has not finished stopping; do not start another demo yet.')
    except OSError as exc:
        if exc.errno == errno.ECONNREFUSED:
            # A crashed launcher leaves a socket inode, never a PID to signal.
            # Recheck the exact private inode after the failed connection so a
            # replaced path, symlink or foreign object cannot be removed.
            try:
                current = path.lstat()
            except FileNotFoundError:
                print('The stopped demo control socket is already gone.', flush=True)
                return
            identity = lambda item: (item.st_dev, item.st_ino, item.st_uid, item.st_mode)
            if (identity(current) == identity(info)
                    and stat.S_ISSOCK(current.st_mode)
                    and current.st_uid == os.getuid()
                    and stat.S_IMODE(current.st_mode) == 0o600):
                path.unlink()
                print('Removed the crashed demo’s stale control socket; no process was signalled.', flush=True)
                return
        raise demo.DemoError('The checkout control socket is stale or unavailable; no process was signalled.') from None


def check_environment_target(directory):
    demo = launcher()
    directory = Path(directory)
    target = directory / '.venv'
    if directory.is_symlink() or target.is_symlink() or (target.exists() and not target.is_dir()):
        raise demo.DemoError('Use regular local project and worker environment directories, not symbolic links.')


def mark_environment(directory):
    demo = launcher()
    check_environment_target(directory)
    target = Path(directory) / '.venv'
    if not target.is_dir():
        raise demo.DemoError('Setup did not create its local environment; rerun make setup.')
    marker = target / '.demo-owner.json'
    if marker.is_symlink():
        raise demo.DemoError('The environment ownership marker is unsafe; no cleanup was authorized.')
    value = {'checkout': str(demo.ROOT.resolve()), 'environment': str(target.resolve())}
    descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        json.dump(value, output)


def clean_environments():
    demo = launcher()
    control = demo.ROOT / '.demo-runtime' / 'control.sock'
    if control.exists() or control.is_symlink():
        raise demo.DemoError('Run make stop before cleaning this checkout’s environments.')
    targets = []
    # Validate every target before removing any of them.
    for directory in (demo.WORKER, demo.PROJECT):
        check_environment_target(directory)
        target = directory / '.venv'
        if not target.exists():
            continue
        marker = target / '.demo-owner.json'
        if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 1024:
            raise demo.DemoError('An environment has no safe checkout ownership marker; nothing was removed.')
        try:
            owner = json.loads(marker.read_text())
        except (OSError, ValueError):
            raise demo.DemoError('An environment ownership marker is invalid; nothing was removed.') from None
        if owner != {'checkout': str(demo.ROOT.resolve()), 'environment': str(target.resolve())}:
            raise demo.DemoError('An environment belongs to another checkout; nothing was removed.')
        targets.append(target)
    cache = demo.ROOT / '.demo-cache'
    if cache.exists() or cache.is_symlink():
        info = cache.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise demo.DemoError('The local demo cache is unsafe; nothing was removed.')
        targets.append(cache)
    for target in targets:
        shutil.rmtree(target)


def create_env():
    demo = launcher()
    demo.check_dotenv_git(demo.ROOT, os.environ, require_ignored=True)
    path = demo.ROOT / '.env'
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise demo.DemoError('Use a regular .env owned by you; the existing path was not changed.')
        path.chmod(0o600)
        print('Kept your existing .env; permissions are private.', flush=True)
    else:
        template = demo.ROOT / '.env.example'
        if template.is_symlink() or not template.is_file() or template.stat().st_size > 4096:
            raise demo.DemoError('The empty .env.example is missing or unsafe; use the complete class checkout.')
        contents = template.read_bytes()
        entries = [line.strip() for line in contents.decode('utf-8').splitlines()
                   if line.strip() and not line.lstrip().startswith('#')]
        if set(entries) != {key + '=' for key in demo.PARTICIPANT_KEYS} or len(entries) != 4:
            raise demo.DemoError('The .env.example must contain exactly four empty credential entries.')
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(contents)
        print('Created private .env; fill it in with your own values.', flush=True)
    for name, url in SOURCES.items():
        print(name + ': ' + url, flush=True)


def ready_environment(*, credentials=True):
    demo = launcher()
    if credentials and not (demo.ROOT / '.env').exists():
        raise demo.DemoError('Run make env first, then fill in your own credential values.')
    return demo.child_environment(credentials=credentials)


def project_python():
    demo = launcher()
    interpreter = demo.python_at(demo.PROJECT)
    if not interpreter.is_file():
        raise demo.DemoError('Run make setup first to install the Python 3.12 environments.')
    result = subprocess.run([str(interpreter), '-c', 'import sys; sys.exit(sys.version_info[:2] != (3,12))'],
                            env=demo.child_environment(credentials=False), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    if result.returncode:
        raise demo.DemoError('Install Python 3.12 and run make setup again.')
    return interpreter


def perform(target):
    demo = launcher()
    if target not in PURPOSES:
        raise demo.DemoError('Use make help to see the supported demo commands.')
    print(PURPOSES[target], flush=True)
    if target == 'help':
        for name, sentence in PURPOSES.items():
            print('make ' + name + ': ' + sentence, flush=True)
        if not (demo.ROOT / '.env').exists():
            print('Run make env first, then fill in your own credential values.', flush=True)
    elif target == 'env':
        create_env()
    elif target == 'stop':
        stop_checkout(demo.ROOT)
    elif target == 'clean':
        clean_environments()
    else:
        env = ready_environment(credentials=target not in ('setup', 'test'))
        if target == 'setup':
            demo.setup()
        elif target in ('run', 'run-scripted'):
            from demo_host import validate_host
            host = validate_host(env.get('BRIEFING_VIEWER_HOST', '127.0.0.1'))
            print('Demo page: http://' + host + ':8942/', flush=True)
            demo.run_demo(scripted=target == 'run-scripted', host=host)
        else:
            interpreter = project_python()
            argv = ([str(interpreter), str(demo.ROOT / 'class_doctor.py')]
                    if target == 'doctor' else
                    [str(interpreter), '-m', 'unittest', 'discover', '-s', str(demo.ROOT / 'tests')])
            if target == 'test':
                # Tests must not inherit any participant credential.
                for name in demo.PARTICIPANT_KEYS:
                    env.pop(name, None)
            if target == 'doctor':
                for name in ('RASA_LICENSE', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPGRAM_API_KEY'):
                    print(name + ': ' + ('SET' if env.get(name, '').strip() else 'MISSING'), flush=True)
            children = demo.Children()
            try:
                demo.completed(children, argv, cwd=demo.ROOT, env=env, timeout=300,
                               failure='The check did not pass; review its safe diagnostics and the class checkout.')
                print('Readiness check passed.' if target == 'doctor' else 'Example controls passed.', flush=True)
            finally:
                children.close()
