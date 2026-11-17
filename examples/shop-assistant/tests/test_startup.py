"""Offline checks for the first commands a reader runs."""
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from shop_demo.startup import HELP, chat_id, doctor, failure_hint
from setup_environments import ensure


class StartupTests(unittest.TestCase):
    def test_doctor_explains_every_missing_name_without_io(self):
        output = io.StringIO()
        self.assertEqual(doctor({}, output), 1)
        for name, hint in HELP.items():
            self.assertIn(name, output.getvalue())
            self.assertIn(hint, output.getvalue())

    def test_doctor_never_prints_values(self):
        env = {name: 'PRIVATE-VALUE' for name in HELP}
        env.update(SHOP_SHEET_ID='a' * 25, SHOP_OPERATOR_CHAT_ID='12345')
        output = io.StringIO()
        self.assertEqual(doctor(env, output), 0)
        self.assertNotIn('PRIVATE-VALUE', output.getvalue())
        self.assertNotIn('12345', output.getvalue())
        self.assertNotIn('a' * 25, output.getvalue())

    def discover(self, result, **extra):
        output = io.StringIO()
        fetch = Mock(return_value={'ok': True, 'result': result})
        with tempfile.TemporaryDirectory() as directory:
            status = chat_id({'TELEGRAM_BOT_TOKEN': '123:SECRET', 'SHOP_STATE_DIR': directory}, fetch, output)
            self.assertEqual({p.name for p in Path(directory).iterdir()}, {'run.sqlite3'})
        return status, output.getvalue(), fetch

    def test_chat_id_private_only_and_deduplicates(self):
        messages = [{'message': {'chat': {'id': 55, 'type': 'private'}}}] * 2
        messages.append({'message': {'chat': {'id': -99, 'type': 'group'}}})
        status, output, fetch = self.discover(messages)
        self.assertEqual(status, 0)
        self.assertIn('Your private chat ID: 55', output)
        fetch.assert_called_once_with('123:SECRET')

    def test_no_messages_explains_start(self):
        status, output, _ = self.discover([])
        self.assertEqual(status, 1)
        self.assertIn('Send /start', output)

    def test_multiple_chats_no_guess(self):
        status, output, _ = self.discover([{'message': {'chat': {'id': n, 'type': 'private'}}} for n in (1, 2)])
        self.assertEqual(status, 1)
        self.assertIn('no chat was selected', output)

    def test_chat_id_refuses_local_running_assistant(self):
        from shop_demo.state import open_state
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run.sqlite3'
            open_state(path).close()
            with path.open('rb') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fetch, output = Mock(), io.StringIO()
                status = chat_id({'TELEGRAM_BOT_TOKEN': '123:SECRET', 'SHOP_STATE_DIR': directory}, fetch, output)
                self.assertEqual(status, 1)
                fetch.assert_not_called()
                self.assertIn('Stop it with Ctrl-C', output.getvalue())

    def test_invalid_token_no_network(self):
        fetch, output = Mock(), io.StringIO()
        self.assertEqual(chat_id({}, fetch, output), 1)
        fetch.assert_not_called()

    def test_provider_error_does_not_leak_token_or_response(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(chat_id({'TELEGRAM_BOT_TOKEN': '123:SECRET', 'SHOP_STATE_DIR': directory}, Mock(side_effect=RuntimeError('123:SECRET response')), output), 1)
        self.assertNotIn('123:SECRET', output.getvalue())
        self.assertIn('RuntimeError', output.getvalue())

    def test_launcher_error_hint_never_interpolates_exception(self):
        for error in (ValueError('SECRET'), RuntimeError('SECRET'), FileNotFoundError('SECRET'), BlockingIOError('SECRET')):
            self.assertNotIn('SECRET', failure_hint(error))
            self.assertIn(type(error).__name__, failure_hint(error))

    def test_setup_missing_environment_uses_locked_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = Mock()
            self.assertEqual(ensure(directory, 'shop-native', runner), 'created')
            command = runner.call_args.args[0]
            self.assertIn('../../scripts/workspace.py', command)
            self.assertEqual(command[-2:], ['--owner', 'shop-native'])

    def owned_environment(self, root):
        project = Path(root)
        for name in ('pyproject.toml', 'uv.lock'):
            (project / name).write_text(name)
        (project / '.venv/bin').mkdir(parents=True)
        (project / '.venv/bin/python').write_text('fake')
        record = {'owner': 'shop-native', 'project': str(project), 'inputs': {
            name: hashlib.sha256((project / name).read_bytes()).hexdigest() for name in ('pyproject.toml', 'uv.lock')}}
        (project / '.venv/.rasa-workspace.json').write_text(json.dumps(record))
        return project

    def test_setup_reuses_without_installer(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.owned_environment(directory)
            runner = Mock()
            self.assertEqual(ensure(project, 'shop-native', runner), 'reused')
            runner.assert_not_called()

    def test_setup_changed_lock_preserves_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.owned_environment(directory)
            (project / 'uv.lock').write_text('changed')
            runner = Mock()
            with self.assertRaisesRegex(ValueError, 'Preserve'):
                ensure(project, 'shop-native', runner)
            runner.assert_not_called()
            self.assertTrue((project / '.venv/bin/python').exists())

    def test_plain_make_only_shows_help_and_run_checks_doctor(self):
        project = Path(__file__).resolve().parents[1]
        result = subprocess.run(['make', '-n'], cwd=project, capture_output=True, text=True, check=True)
        self.assertIn('doctor', result.stdout)
        self.assertNotIn('workspace.py start', result.stdout)
        self.assertNotIn('-m shop_demo.launcher', result.stdout)
        dry_run = subprocess.run(['make', '-n', 'run'], cwd=project, capture_output=True, text=True, check=True)
        self.assertLess(dry_run.stdout.index('startup doctor'), dry_run.stdout.index('shop_demo.launcher'))


if __name__ == '__main__':
    unittest.main()
