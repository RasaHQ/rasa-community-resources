"""Guided setup uses synthetic Telegram and Sheets, never real HTTP."""
import fcntl
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, patch

from pydantic import SecretStr
from shop_demo import telegram_setup as setup
from shop_demo.activity import assistant_activity, local_activity
from shop_demo.startup import discovery_lock, doctor
from shop_demo.status_sheet import check
from shop_demo.setup_sheet import SheetSettings

TOKEN = '123:SYNTHETIC_CANARY'
IDENTITY = {'username': 'example_shop_bot', 'is_bot': True}
CHALLENGE = '/start shop-' + 'a' * 32
PRIVATE = {'message': {'text': CHALLENGE, 'chat': {'id': 77, 'type': 'private'},
    'entities': [{'offset': 0, 'length': 6, 'type': 'bot_command'}]}}


class Clock:
    value = 0
    def __call__(self):
        return self.value
    def sleep(self, seconds):
        self.value += seconds


class TelegramSetupTests(unittest.TestCase):
    def setUp(self):
        block = patch('urllib.request.urlopen', side_effect=AssertionError('Real HTTP forbidden'))
        block.start()
        self.addCleanup(block.stop)
        challenge = patch.object(setup.secrets, 'token_hex', return_value='a' * 32)
        challenge.start()
        self.addCleanup(challenge.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env = {'SHOP_STATE_DIR': self.directory.name}

    def run_setup(self, updates=None, *, env=None, ask=None, request=None, secret=None, shell=None):
        clock, output = Clock(), io.StringIO()
        if request is None:
            def request(token, method, payload, **kwargs):
                self.assertEqual(token, TOKEN)
                self.assertNotIn('offset', payload)
                if method == 'getMe':
                    return IDENTITY
                if method == 'getWebhookInfo':
                    return {'url': ''}
                self.assertEqual(method, 'getUpdates')
                self.assertIn('message', payload['allowed_updates'])
                return [PRIVATE] if updates is None else updates
        request = Mock(side_effect=request)
        shell = Mock(return_value=0) if shell is None else shell
        result = setup.guided(self.env if env is None else env, request=request,
            ask=Mock(return_value='no') if ask is None else ask,
            secret=Mock(return_value=TOKEN) if secret is None else secret, clock=clock,
            sleep=clock.sleep, shell=shell, output=output, seconds=4)
        for canary in (TOKEN, 'PRIVATE_TEXT_CANARY', 'RAW_PROVIDER_CANARY'):
            self.assertNotIn(canary, output.getvalue())
        return result, output.getvalue(), request, shell, clock

    def test_private_start_and_edited_text_keep_original_offsets(self):
        for kind in ('message', 'edited_message'):
            result, text, request, shell, _ = self.run_setup([{kind: PRIVATE['message']}], ask=Mock(return_value='no'))
            # Saving is the default explicit alternative to a session.
            self.assertEqual(result, 0)
            self.assertIn('This is @example_shop_bot', text)
            self.assertIn('Your private chat ID: 77', text)
            self.assertIn('stop and start', text)
            self.assertEqual([call.args[1] for call in request.call_args_list], ['getMe', 'getWebhookInfo', 'getUpdates'])
            shell.assert_not_called()

    def test_empty_poll_then_private_arrival_uses_same_token_without_offset(self):
        polls = []
        def request(token, method, payload, **kwargs):
            if method == 'getMe':
                return IDENTITY
            if method == 'getWebhookInfo':
                return {'url': ''}
            polls.append(dict(payload))
            self.assertEqual(token, TOKEN)
            self.assertNotIn('offset', payload)
            return [] if len(polls) == 1 else [PRIVATE]
        result, text, _, _, clock = self.run_setup(request=request, ask=Mock(return_value='no'))
        self.assertEqual(result, 0)
        self.assertEqual(len(polls), 2)
        self.assertEqual(clock.value, 2)
        self.assertIn('Your private chat ID: 77', text)

    def test_empty_membership_and_group_time_out(self):
        for updates in ([], [{'my_chat_member': {'chat': {'id': 77, 'type': 'private'}}}],
                [{'message': {'text': 'PRIVATE_TEXT_CANARY', 'chat': {'id': -9, 'type': 'group'}}}]):
            result, text, _, _, clock = self.run_setup(updates)
            self.assertEqual(result, 1)
            self.assertIn('No private message matched this setup code', text)
            self.assertEqual(clock.value, 4)

    def test_full_unrelated_pending_window_times_out_with_safe_recovery(self):
        updates = [{'message': {'text': '/start', 'chat': {'id': 88, 'type': 'private'}}}] * 100
        result, text, request, shell, clock = self.run_setup(updates)
        self.assertEqual(result, 1)
        self.assertEqual(clock.value, 4)
        self.assertIn('full older pending window', text)
        self.assertIn('fresh personal bot', text)
        self.assertNotIn('Your private chat ID:', text)
        shell.assert_not_called()
        polls = [call for call in request.call_args_list if call.args[1] == 'getUpdates']
        self.assertTrue(polls)
        for call in polls:
            self.assertEqual(call.args[2]['limit'], 100)
            self.assertNotIn('offset', call.args[2])

    def test_multiple_private_chats_refuse_selection(self):
        result, text, _, _, _ = self.run_setup([PRIVATE, {'message': {'text': CHALLENGE, 'chat': {'id': 88, 'type': 'private'}}}])
        self.assertEqual(result, 1)
        self.assertIn('no chat was selected', text)
        self.assertNotIn('Your private chat ID', text)

    def test_unrelated_queued_sender_cannot_become_operator(self):
        polls = []
        unrelated = {'message': {'text': '/start', 'chat': {'id': 88, 'type': 'private'}}}
        def request(token, method, payload, **kwargs):
            if method == 'getMe':
                return IDENTITY
            if method == 'getWebhookInfo':
                return {'url': ''}
            self.assertNotIn('offset', payload)
            polls.append(payload)
            return [unrelated] if len(polls) == 1 else [unrelated, PRIVATE]
        result, text, _, shell, _ = self.run_setup(request=request, ask=Mock(return_value='yes'))
        self.assertEqual(result, 0)
        self.assertEqual(len(polls), 2)
        self.assertEqual(shell.call_args.args[0]['SHOP_OPERATOR_CHAT_ID'], '77')
        self.assertIn(CHALLENGE, text)
        self.assertNotIn('Your private chat ID: 88', text)

    def test_doctor_recovery_cannot_select_an_unrelated_queued_sender(self):
        guidance = io.StringIO()
        original = dict(self.env)
        self.assertEqual(doctor(self.env, guidance), 1)
        self.assertIn('Run make telegram', guidance.getvalue())
        self.assertIn('fresh setup code', guidance.getvalue())
        self.assertNotIn('make chat-id', guidance.getvalue())
        unrelated = {'message': {'text': '/start', 'chat': {'id': 88, 'type': 'private'}}}
        result, text, _, shell, _ = self.run_setup([unrelated], env=self.env,
            ask=Mock(return_value='yes'))
        self.assertEqual(result, 1)
        self.assertEqual(self.env, original)
        self.assertNotIn('Your private chat ID:', text)
        shell.assert_not_called()

    def test_old_setup_code_or_partial_match_cannot_select_chat(self):
        for text in ('/start', '/start shop-' + 'b' * 32, CHALLENGE + ' extra'):
            update = {'message': {'text': text, 'chat': {'id': 88, 'type': 'private'}}}
            result, output, _, shell, _ = self.run_setup([update])
            self.assertEqual(result, 1)
            self.assertIn('No private message matched this setup code', output)
            self.assertNotIn('Your private chat ID', output)
            shell.assert_not_called()

    def test_empty_activity_during_startup_is_unavailable_not_healthy(self):
        directory = Path(self.directory.name)
        with discovery_lock(directory):
            path = directory / 'activity.json'
            path.write_text('')
            path.chmod(0o600)
            output = io.StringIO()
            result = setup.status({**self.env, 'TELEGRAM_BOT_TOKEN': TOKEN, 'SHOP_OPERATOR_CHAT_ID': '77'},
                request=Mock(side_effect=[IDENTITY, {'url': ''}]), output=output)
        self.assertEqual(result, 1)
        self.assertIn('startup may still be in progress', output.getvalue())
        self.assertNotIn('Local assistant: running', output.getvalue())

    def test_bad_token_no_provider_call(self):
        result, text, request, _, _ = self.run_setup(secret=Mock(return_value='RAW_PROVIDER_CANARY'))
        self.assertEqual(result, 1)
        request.assert_not_called()
        self.assertIn('missing or invalid', text)

    def test_existing_token_is_a_choice_not_a_dump(self):
        env = {**self.env, 'TELEGRAM_BOT_TOKEN': TOKEN}
        secret = Mock(side_effect=AssertionError('No second secret read'))
        result, text, _, _, _ = self.run_setup(env=env, secret=secret, ask=Mock(side_effect=['yes', 'no']))
        self.assertEqual(result, 0)
        secret.assert_not_called()
        self.assertNotIn(TOKEN, text)

    def test_no_tty_and_input_cancel_are_actionable(self):
        with patch('sys.stdin.isatty', return_value=False):
            with self.assertRaises(setup.PrivateTerminalRequired):
                setup.hidden_token('hidden')
        for error, expected in ((setup.PrivateTerminalRequired(), 'interactive terminal'),
                (KeyboardInterrupt(), 'Setup stopped'), (EOFError(), 'Setup stopped')):
            result, text, request, _, _ = self.run_setup(secret=Mock(side_effect=error))
            self.assertEqual(result, 1)
            self.assertIn(expected, text)
            request.assert_not_called()

    def test_hidden_input_never_falls_back_to_echo(self):
        import getpass
        with patch('sys.stdin.isatty', return_value=True), \
                patch('getpass.getpass', side_effect=getpass.GetPassWarning('RAW_PROVIDER_CANARY')):
            with self.assertRaises(setup.PrivateTerminalRequired):
                setup.hidden_token('hidden')

    def test_errors_are_plain_and_never_show_provider_text(self):
        for error, hint in [(setup.TelegramProblem(401), 'rejected'),
                (setup.TelegramProblem(409, True), 'webhook'),
                (setup.TelegramProblem(409), 'Another process'),
                (setup.TelegramProblem(429), 'Wait a minute'),
                (setup.TelegramProblem(500), 'connection'),
                (TimeoutError('RAW_PROVIDER_CANARY'), 'connection'),
                (urllib.error.URLError('RAW_PROVIDER_CANARY'), 'connection')]:
            result, text, _, _, _ = self.run_setup(request=Mock(side_effect=error))
            self.assertEqual(result, 1)
            self.assertIn(hint, text)

    def test_webhook_and_malformed_responses_never_poll(self):
        for responses in ([IDENTITY, {'url': 'https://RAW_PROVIDER_CANARY'}],
                [{'username': 'RAW_PROVIDER_CANARY\n', 'is_bot': True}],
                [IDENTITY, {'url': 42}]):
            result, text, request, _, _ = self.run_setup(request=Mock(side_effect=responses))
            self.assertEqual(result, 1)
            self.assertNotIn('getUpdates', [c.args[1] for c in request.call_args_list])

    def test_invalid_prompt_and_replacement_token(self):
        env = {**self.env, 'TELEGRAM_BOT_TOKEN': TOKEN}
        result, _, request, _, _ = self.run_setup(env=env, ask=Mock(return_value='maybe'))
        self.assertEqual(result, 1)
        request.assert_not_called()
        result, _, _, _, _ = self.run_setup(env=env, ask=Mock(side_effect=['no', 'no']))
        self.assertEqual(result, 0)
        result, _, _, shell, _ = self.run_setup(ask=Mock(return_value='maybe'))
        self.assertEqual(result, 1)
        shell.assert_not_called()

    def test_poll_cancel_and_local_competition_release_owned_lock(self):
        def cancelled(token, method, payload, **kwargs):
            if method == 'getMe':
                return IDENTITY
            if method == 'getWebhookInfo':
                return {'url': ''}
            raise KeyboardInterrupt()
        result, text, _, _, _ = self.run_setup(request=cancelled)
        self.assertEqual(result, 1)
        self.assertIn('Setup stopped', text)
        with discovery_lock(self.directory.name):
            result, text, request, _, _ = self.run_setup()
            self.assertEqual(result, 1)
            self.assertIn('local process', text)
            self.assertNotIn('getUpdates', [c.args[1] for c in request.call_args_list])

    def test_raw_transport_http_and_ok_false_classify_without_leaks(self):
        for code, webhook in ((401, False), (409, True), (409, False), (429, False)):
            body = {'description': ('webhook ' if webhook else '') + TOKEN, 'error_code': code, 'ok': False}
            error = urllib.error.HTTPError('https://' + TOKEN, code, TOKEN, {}, io.BytesIO(json.dumps(body).encode()))
            for transport in (Mock(side_effect=error), Mock(return_value=body)):
                with patch.object(setup, 'telegram_request', transport):
                    with self.assertRaises(setup.TelegramProblem) as caught:
                        setup.api(TOKEN, 'getMe', {})
                self.assertEqual((caught.exception.code, caught.exception.webhook), (code, webhook))
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_webhook_refuses_before_get_updates(self):
        request = Mock(side_effect=[IDENTITY, {'url': 'https://RAW_PROVIDER_CANARY'}])
        result, text, request, _, _ = self.run_setup(request=request)
        self.assertEqual(result, 1)
        self.assertIn('webhook', text)
        self.assertEqual(request.call_count, 2)

    def test_malformed_identity_and_envelopes_refuse(self):
        for value in ({'username': 'RAW_PROVIDER_CANARY\n', 'is_bot': True},
                {'username': 'example_shop_bot', 'is_bot': False}, None):
            result, text, request, _, _ = self.run_setup(request=Mock(return_value=value))
            self.assertEqual(result, 1)
            self.assertEqual(request.call_count, 1)
        for value in (None, {'ok': False}, [], {'ok': True, 'result': None}):
            with patch.object(setup, 'telegram_request', return_value=value):
                if isinstance(value, dict) and value.get('ok') is True:
                    self.assertIsNone(setup.api(TOKEN, 'getMe', {}))
                else:
                    with self.assertRaises(setup.TelegramProblem):
                        setup.api(TOKEN, 'getMe', {})

    def test_local_lock_blocks_polling_and_is_released_after_cancel(self):
        with discovery_lock(self.directory.name):
            result, text, request, _, _ = self.run_setup()
            self.assertEqual(result, 1)
            self.assertIn('local process', text)
            self.assertNotIn('getUpdates', [call.args[1] for call in request.call_args_list])
        with discovery_lock(self.directory.name):
            pass

    def test_session_inherits_values_without_changing_parent_or_writing_file(self):
        parent = dict(self.env)
        result, text, _, shell, _ = self.run_setup(env=parent, ask=Mock(return_value='yes'))
        self.assertEqual(result, 0)
        self.assertEqual(parent, self.env)
        child = shell.call_args.args[0]
        self.assertEqual(child['TELEGRAM_BOT_TOKEN'], TOKEN)
        self.assertEqual(child['SHOP_OPERATOR_CHAT_ID'], '77')
        self.assertIn('exit', text)
        self.assertEqual({p.name for p in Path(self.directory.name).iterdir()}, {'run.sqlite3'})

    def test_session_shell_avoids_rc_tracing_and_argv_secrets(self):
        env = {'PATH': '/usr/bin', 'TELEGRAM_BOT_TOKEN': TOKEN, 'SHOP_OPERATOR_CHAT_ID': '77',
            'BASH_ENV': 'RAW_PROVIDER_CANARY', 'SHELLOPTS': 'xtrace', 'PROMPT_COMMAND': 'env',
            'BASH_FUNC_attack%%': 'RAW_PROVIDER_CANARY'}
        with patch.object(setup.subprocess, 'run', return_value=Mock(returncode=3)) as run:
            self.assertEqual(setup.session_shell(env), 3)
        self.assertEqual(run.call_args.args[0], ['/bin/bash', '--noprofile', '--norc', '-i'])
        child = run.call_args.kwargs['env']
        self.assertFalse({'BASH_ENV', 'SHELLOPTS', 'PROMPT_COMMAND', 'BASH_FUNC_attack%%'} & child.keys())
        self.assertNotIn(TOKEN, str(run.call_args.args))
        self.assertEqual(env['BASH_ENV'], 'RAW_PROVIDER_CANARY')

    def test_status_never_polls_or_creates_state_or_prints_values(self):
        env = {**self.env, 'SHOP_STATE_DIR': str(Path(self.directory.name) / 'absent'),
            'TELEGRAM_BOT_TOKEN': TOKEN, 'SHOP_OPERATOR_CHAT_ID': '777777',
            'GOOGLE_TOKEN_JSON': 'RAW_PROVIDER_CANARY', 'SHOP_SHEET_ID': 's' * 25}
        output, request, probe = io.StringIO(), Mock(side_effect=[IDENTITY, {'url': ''}]), Mock(return_value='reachable (metadata read only)')
        self.assertEqual(setup.status(env, request=request, probe=probe, output=output), 0)
        self.assertFalse(Path(env['SHOP_STATE_DIR']).exists())
        self.assertEqual([c.args[1] for c in request.call_args_list], ['getMe', 'getWebhookInfo'])
        for value in (TOKEN, '777777', 'RAW_PROVIDER_CANARY', 's' * 25):
            self.assertNotIn(value, output.getvalue())
        self.assertIn('stopped', output.getvalue())
        self.assertIn('@example_shop_bot', output.getvalue())

    def test_status_missing_failed_and_active_cases(self):
        for state, expected in [('running', 'running'), ('unknown', 'unknown'), ('different', 'different')]:
            output = io.StringIO()
            env = {**self.env, 'TELEGRAM_BOT_TOKEN': TOKEN, 'SHOP_OPERATOR_CHAT_ID': '77'}
            probe = Mock(side_effect=AssertionError('No probe without Google settings'))
            self.assertEqual(setup.status(env, request=Mock(side_effect=[IDENTITY, {'url': ''}]),
                activity=Mock(return_value=state), probe=probe, output=output), 1)
            self.assertIn(expected, output.getvalue())
            self.assertIn('Sheet: settings missing', output.getvalue())
            probe.assert_not_called()
        for error in (setup.TelegramProblem(401), TimeoutError('RAW_PROVIDER_CANARY')):
            output = io.StringIO()
            self.assertEqual(setup.status(self.env, request=Mock(side_effect=error), output=output), 1)
            self.assertNotIn('RAW_PROVIDER_CANARY', output.getvalue())

    def test_activity_matches_only_held_lock_and_clears_discovery_stale_label(self):
        directory = Path(self.directory.name)
        with discovery_lock(directory):
            self.assertEqual(local_activity(directory, TOKEN, '77'), 'unknown')
            with assistant_activity(directory, TOKEN, '77'):
                self.assertEqual(local_activity(directory, TOKEN, '77'), 'running')
                self.assertEqual(local_activity(directory, TOKEN, '88'), 'different')
                self.assertNotIn(TOKEN, (directory / 'activity.json').read_text())
            self.assertFalse((directory / 'activity.json').exists())
        self.assertEqual(local_activity(directory, TOKEN, '77'), 'stopped')
        with discovery_lock(directory):
            (directory / 'activity.json').write_text('stale')
            (directory / 'activity.json').chmod(0o600)
        with discovery_lock(directory):
            self.assertFalse((directory / 'activity.json').exists())

    def test_activity_refuses_symlink_and_nonprivate_state(self):
        directory = Path(self.directory.name)
        other = directory / 'other'
        other.write_text('PRIVATE_TEXT_CANARY')
        (directory / 'run.sqlite3').symlink_to(other)
        with self.assertRaises(OSError):
            local_activity(directory, TOKEN, '77')
        self.assertEqual(other.read_text(), 'PRIVATE_TEXT_CANARY')
        directory.chmod(0o755)
        try:
            with self.assertRaises(PermissionError):
                local_activity(directory, TOKEN, '77')
        finally:
            directory.chmod(0o700)

    def test_sheet_probe_errors_and_timeout_are_sanitized(self):
        env = {**self.env, 'TELEGRAM_BOT_TOKEN': TOKEN, 'SHOP_OPERATOR_CHAT_ID': '77',
            'GOOGLE_TOKEN_JSON': 'RAW_PROVIDER_CANARY', 'SHOP_SHEET_ID': 's' * 25}
        for probe in (Mock(return_value='not reachable; check settings'),
                Mock(side_effect=RuntimeError('RAW_PROVIDER_CANARY'))):
            output = io.StringIO()
            self.assertEqual(setup.status(env, request=Mock(side_effect=[IDENTITY, {'url': ''}]),
                probe=probe, output=output), 1)
            self.assertNotIn('RAW_PROVIDER_CANARY', output.getvalue())
        with patch.object(setup.Path, 'is_file', return_value=True), \
                patch.object(setup.subprocess, 'run', side_effect=TimeoutError('RAW_PROVIDER_CANARY')):
            self.assertIn('did not finish', setup.sheet_status(env))
        with patch.object(setup.Path, 'is_file', return_value=True), \
                patch.object(setup.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            self.assertEqual(setup.sheet_status(env), 'reachable (metadata read only)')
            self.assertIn('shop_demo.status_sheet', run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs['stdout'], setup.subprocess.DEVNULL)
            self.assertEqual(run.call_args.kwargs['stderr'], setup.subprocess.DEVNULL)

    def test_sheet_worker_calls_metadata_only(self):
        settings = SheetSettings(spreadsheet_id='s' * 25, token=SecretStr('RAW_PROVIDER_CANARY'))
        service = Mock()
        service.get_spreadsheet.return_value = Mock(success=True, content={'sheets': [{'properties': {'title': 'private'}}]})
        check(settings, service)
        self.assertEqual(service.method_calls, [unittest.mock.call.get_spreadsheet('s' * 25)])
        service.get_spreadsheet.return_value = Mock(success=False, content={})
        with self.assertRaises(RuntimeError):
            check(settings, service)
