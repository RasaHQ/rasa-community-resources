"""Bounded children prove special files are refused before they can block."""
import fcntl
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from shop_demo.activity import private_file
from shop_demo.state import open_state

PROJECT = Path(__file__).resolve().parents[1]
CHILD = textwrap.dedent('''
    import fcntl, io, os, sys
    from pathlib import Path
    from unittest.mock import Mock, patch
    from shop_demo.activity import assistant_activity, private_file
    from shop_demo.telegram_setup import guided, status

    directory, action = Path(sys.argv[1]), sys.argv[2]
    output = io.StringIO()
    real_http = Mock(side_effect=AssertionError('Real provider forbidden'))
    fetch = Mock(side_effect=AssertionError('No update poll allowed'))
    def metadata(token, method, payload, **kwargs):
        if method == 'getMe':
            return {'id': 123, 'is_bot': True, 'username': 'synthetic_test_bot'}
        if method == 'getWebhookInfo':
            return {'url': ''}
        return fetch(token, method, payload, **kwargs)
    request = Mock(side_effect=metadata)
    with patch('urllib.request.urlopen', real_http):
        if action == 'discover':
            result = guided({'TELEGRAM_BOT_TOKEN': '123:SYNTHETIC_CANARY',
                'SHOP_STATE_DIR': str(directory)}, request=request, ask=lambda _: 'yes',
                output=output)
            assert result == 1
            assert 'The Telegram check could not finish' in output.getvalue()
            assert [call.args[1] for call in request.call_args_list] == ['getMe', 'getWebhookInfo']
            # The discovery context already acquired this lock before the
            # activity admission failed. It MUST release it on the error path.
            descriptor = private_file(directory / 'run.sqlite3', os.O_RDWR)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(descriptor)
        elif action == 'assistant':
            try:
                with assistant_activity(directory, '123:SYNTHETIC_CANARY', 77):
                    raise AssertionError('FIFO was admitted')
            except OSError:
                output.write('Private activity refused; preserve state and inspect permissions.')
            else:
                raise AssertionError('Expected refusal')
        else:
            result = status({'SHOP_STATE_DIR': str(directory)}, request=fetch,
                probe=fetch, output=output)
            assert result == 1
            assert 'Local activity: unavailable' in output.getvalue()
        fetch.assert_not_called()
        real_http.assert_not_called()
    assert 'SYNTHETIC_CANARY' not in output.getvalue()
    print(output.getvalue(), end='')
    print('PROVIDER_CALLS=0; POLL_CALLS=0; BUSINESS_CALLS=0; REFUSED')
''')


class ActivityAdmissionTests(unittest.TestCase):
    def child(self, directory, action):
        # subprocess.run kills/reaps only this owned, childless process if an
        # old blocking-open regression prevents the three-second bound.
        result = subprocess.run([sys.executable, '-B', '-c', CHILD, str(directory), action],
            cwd=PROJECT, capture_output=True, text=True, timeout=3,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PROVIDER_CALLS=0; POLL_CALLS=0; BUSINESS_CALLS=0; REFUSED', result.stdout)
        self.assertNotIn('SYNTHETIC_CANARY', result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_fifo_activity_refused_by_guided_setup_and_assistant_without_replacement(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            fifo = directory / 'activity.json'
            os.mkfifo(fifo, 0o600)
            before = fifo.stat(follow_symlinks=False)
            for action in ('discover', 'assistant'):
                self.child(directory, action)
                after = fifo.stat(follow_symlinks=False)
                self.assertEqual((after.st_dev, after.st_ino, after.st_mode),
                    (before.st_dev, before.st_ino, before.st_mode))
                self.assertTrue(stat.S_ISFIFO(after.st_mode))

    def test_status_fifo_lock_refuses_without_creating_activity(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            fifo = directory / 'run.sqlite3'
            os.mkfifo(fifo, 0o600)
            before = fifo.stat(follow_symlinks=False)
            self.child(directory, 'status')
            self.assertEqual(fifo.stat(follow_symlinks=False).st_ino, before.st_ino)
            self.assertEqual([p.name for p in directory.iterdir()], ['run.sqlite3'])

    def test_status_fifo_activity_refuses_under_an_existing_owner_lock(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            lock_path = directory / 'run.sqlite3'
            open_state(lock_path).close()
            fifo = directory / 'activity.json'
            os.mkfifo(fifo, 0o600)
            before = fifo.stat(follow_symlinks=False)
            with lock_path.open('rb') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.child(directory, 'status')
            self.assertEqual(fifo.stat(follow_symlinks=False).st_ino, before.st_ino)
            descriptor = private_file(lock_path, os.O_RDWR)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(descriptor)

    def test_regular_file_allowed_links_and_wrong_mode_refused_without_changes(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            path = directory / 'activity.json'
            descriptor = private_file(path, os.O_CREAT | os.O_RDWR)
            os.close(descriptor)
            path.write_text('original')
            link = directory / 'link'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                private_file(link, os.O_RDONLY)
            link.unlink()
            os.link(path, link)
            with self.assertRaises(PermissionError):
                private_file(path, os.O_RDONLY)
            link.unlink()
            path.chmod(0o644)
            with self.assertRaises(PermissionError):
                private_file(path, os.O_RDONLY)
            self.assertEqual(path.read_text(), 'original')

    def test_descriptor_is_closed_if_admission_fails(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'activity.json'
            path.write_text('original')
            path.chmod(0o600)
            opened = []
            original = os.open
            def track(*args, **kwargs):
                descriptor = original(*args, **kwargs)
                opened.append(descriptor)
                return descriptor
            with patch('shop_demo.activity.os.open', side_effect=track), \
                    patch('shop_demo.activity.os.fstat', side_effect=OSError('synthetic admission failure')):
                with self.assertRaises(OSError):
                    private_file(path, os.O_RDONLY)
            for descriptor in opened:
                with self.assertRaises(OSError):
                    os.fstat(descriptor)
            self.assertEqual(path.read_text(), 'original')
