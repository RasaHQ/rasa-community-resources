"""Offline checks for the first commands a reader runs."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from shop_demo.startup import HELP, chat_id, doctor, failure_hint
from setup_environments import ensure


class StartupTests(unittest.TestCase):
    def setUp(self):
        network = patch("urllib.request.urlopen", side_effect=AssertionError("Real Telegram HTTP is forbidden in startup tests"))
        network.start()
        self.addCleanup(network.stop)

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

    def test_missing_chat_guidance_uses_challenge_binding(self):
        hint = HELP['SHOP_OPERATOR_CHAT_ID']
        self.assertIn('make telegram', hint)
        self.assertIn('fresh setup code', hint)
        self.assertNotIn('make chat-id', hint)

    def test_retired_chat_id_never_reads_a_lone_unrelated_sender(self):
        output = io.StringIO()
        fetch = Mock(return_value={'ok': True, 'result': [
            {'message': {'text': '/start', 'chat': {'id': 987654321, 'type': 'private'}}}]})
        identify = Mock(return_value={'username': 'example_shop_bot', 'is_bot': True})
        with tempfile.TemporaryDirectory() as directory:
            environ = {'TELEGRAM_BOT_TOKEN': '123:SECRET', 'SHOP_STATE_DIR': directory}
            original = dict(environ)
            self.assertEqual(chat_id(environ, fetch, output, identify=identify), 1)
            self.assertEqual(environ, original)
            self.assertEqual(list(Path(directory).iterdir()), [])
        fetch.assert_not_called()
        identify.assert_not_called()
        self.assertIn('retired', output.getvalue())
        self.assertIn('make telegram', output.getvalue())
        self.assertNotIn('987654321', output.getvalue())
        self.assertNotIn('SECRET', output.getvalue())
        self.assertNotIn('Your private chat ID:', output.getvalue())

    def test_retired_cli_refuses_without_provider_access(self):
        from shop_demo import startup
        output = io.StringIO()
        with patch('sys.argv', ['startup', 'chat-id']), patch('sys.stdout', output):
            self.assertEqual(startup.main(), 1)
        self.assertIn('make telegram', output.getvalue())
        self.assertNotIn('Your private chat ID:', output.getvalue())

    def test_retired_make_target_refuses_without_an_interpreter(self):
        result = subprocess.run(['make', '--no-print-directory', 'chat-id',
            'CONSENT_PYTHON=/bin/false'], cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=10, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('retired', result.stdout)
        self.assertIn('make telegram', result.stdout)
        self.assertNotIn('Run make setup', result.stdout)

    def test_lock_hint_includes_transient_status_probe(self):
        hint = failure_hint(BlockingIOError('SECRET'))
        self.assertIn('local command', hint)
        self.assertIn('make status', hint)
        self.assertIn('foreground assistant', hint)
        self.assertNotIn('SECRET', hint)

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
