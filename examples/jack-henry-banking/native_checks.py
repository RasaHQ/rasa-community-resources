"""Real archived Rasa turns and authenticated loopback MCP, scripted model only.

Domain fixtures are deliberately not vendor-contract mocks or real identity.
"""
import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from rasa.core.agent import Agent
from rasa.core.channels.channel import CollectingOutputChannel, UserMessage
from rasa.core.config.configuration import Configuration
from rasa.mantle.llm.client import LLMClient
from rasa.mantle.model_archive.snapshot import package_model_archive
from rasa.shared.providers.llm.llm_response import LLMResponse, LLMToolCall


def records(tracker):
    items = []
    for event in tracker.events:
        row = event.as_dict()
        if row.get('event') == 'tool_executed' and row.get('tool_name', '').startswith('banking_'):
            if row.get('is_error'):
                raise AssertionError('Banking tool failed before returning a safe outcome')
            items.append((row['tool_name'], json.loads(row['result'])))
    return items


class Script:
    def __init__(self):
        self.actions = []
        self.counter = 0
        self.model_inputs = []

    async def complete(self, client, messages, tools=None, model_settings=None):
        schemas = {item['function']['name']: item['function'] for item in tools or []}
        self.model_inputs.append(str(messages))
        if {'open_session', 'confirm', 'cancel', 'reset'} & set(schemas):
            raise AssertionError('Private host controls must not be model tools')
        for name, schema in schemas.items():
            if name.startswith('banking_'):
                fields = set(schema.get('parameters', {}).get('properties', {}))
                if fields & {'session', 'principal', 'verified', 'confirmed', 'credential', 'review', 'host_capability'}:
                    raise AssertionError('Host authority must not enter model tool parameters')
        if set(schemas) == {'record_discovered_facts'}:
            return self.response('record_discovered_facts', {'facts': []})
        if self.actions and self.actions[0][0] not in schemas and 'activate' in schemas:
            return self.response('activate', {'target_id': 'banking'})
        if self.actions:
            name, arguments = self.actions.pop(0)
            if name not in schemas:
                raise AssertionError(f'Expected native tool not offered: {name}')
            return self.response(name, arguments)
        return self.response(text='The supplied fictional outcome is recorded above.')

    def response(self, name=None, args=None, text=None):
        self.counter += 1
        return LLMResponse(id=f'fixture-{self.counter}', choices=[text] if text else [], created=0,
            tool_calls=[LLMToolCall(id=f'tool-{self.counter}', tool_name=name, tool_args=args or {})]
            if name else None)


class NativeFlowTests(unittest.IsolatedAsyncioTestCase):
    PROJECT = None

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'OPENAI_API_KEY': 'placeholder-native-test-only',
            'RASA_LICENSE': '', 'RASA_PRO_LICENSE': '', 'DEEPGRAM_API_KEY': '',
            'RASA_TELEMETRY_ENABLED': 'false', 'PYTHON_DOTENV_DISABLED': 'true',
            'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'LLM_API_HEALTH_CHECK': 'false',
            'DO_NOT_TRACK': '1'})
        self.env.start()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.origin = f'http://127.0.0.1:{port}'
        os.environ['BANKING_HOST_URL'] = self.origin
        os.environ['BANKING_HOST_CAPABILITY'] = secrets.token_urlsafe(32)
        profile = json.loads((self.PROJECT / 'demo.json').read_text())['profile']
        self.profile = profile
        self.transfer_outcome = 'accepted' if profile == 'fiserv' else 'queued'
        self.log = tempfile.TemporaryFile()
        command = [sys.executable, '-m', 'banking_demo.server',
            '--profile', profile, '--port', str(port), '--domain-fixture']
        if self._testMethodName == 'test_unknown_outcome_blocks_retries_even_after_logout':
            command += ['--fault', 'transfer-response-lost']
        self.server = subprocess.Popen(command,
            stdout=self.log, stderr=self.log)
        for _ in range(200):
            if self.server.poll() is not None:
                raise AssertionError('Owned banking server exited before readiness')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1):
                    break
            except OSError:
                await asyncio.sleep(.05)
        else:
            raise AssertionError('Owned banking server did not become ready')
        result = package_model_archive(str(self.PROJECT / 'agent.yml'), str(self.root / 'models'),
                                       fixed_model_name='banking-test', validate=True)
        self.assertEqual(result.code, 0)
        self.previous = Path.cwd()
        os.chdir(self.PROJECT)
        Configuration.initialise_endpoints(None)
        self.agent = Agent.load(result.model)
        await self.agent.prepare_runtime_integrations()
        self.script = Script()
        async def complete(client, *args, **kwargs):
            return await self.script.complete(client, *args, **kwargs)
        self.model = patch.object(LLMClient, 'acompletion', complete)
        self.model.start()
        self.sender = uuid4().hex
        self.output = CollectingOutputChannel()

    async def asyncTearDown(self):
        try:
            if hasattr(self, 'model'):
                self.model.stop()
                combined = ' '.join(self.script.model_inputs)
                self.assertNotIn(os.environ['BANKING_HOST_CAPABILITY'], combined)
                from banking_demo import rasa_adapter
                for (origin, sender), host in rasa_adapter._conversations.items():
                    if origin == self.origin:
                        self.assertNotIn(host.session.credential, combined)
                        if host.last_review:
                            self.assertNotIn(host.last_review, combined)
        finally:
            if hasattr(self, 'agent'):
                await self.agent.close()
            if hasattr(self, 'previous'):
                os.chdir(self.previous)
            self.server.terminate()
            self.server.wait(timeout=10)
            self.log.close()
            self.env.stop()
            self.temp.cleanup()

    async def turn(self, text, *actions):
        self.script.actions = list(actions)
        await self.agent.handle_message(UserMessage(text, self.output, sender_id=self.sender))
        self.assertEqual(self.script.actions, [], 'Every scripted action must actually run')
        return records(await self.agent.tracker_store.retrieve(self.sender))

    async def review(self):
        return await self.turn('Move ten fictional dollars from checking to savings.',
            ('banking_review_transfer', {'source': 'checking-A', 'destination': 'savings-A',
                                         'amount': '10.00', 'currency': 'USD'}))

    async def test_scoped_read_and_other_account_nondisclosure(self):
        rows = await self.turn('List my accounts.', ('banking_accounts', {}))
        self.assertEqual(rows[-1][1]['accounts'], ['checking-A', 'loan-A', 'savings-A'])
        rows = await self.turn('Read my balance.', ('banking_balance', {'account': 'checking-A'}))
        self.assertEqual(rows[-1][1]['amount'], '200.00' if self.profile == 'fiserv' else '100.00')
        rows = await self.turn('Read another account.', ('banking_balance', {'account': 'checking-B'}))
        self.assertEqual(rows[-1][1], {'state': 'refused', 'reason': 'account_unavailable',
                                     'fixture': 'shared-banking-contract'})

    async def test_next_explicit_raw_confirmation_queues_once(self):
        rows = await self.review()
        self.assertEqual(rows[-1][1]['state'], 'pending')
        self.assertNotIn('review', rows[-1][1])
        self.assertTrue(any('USD 10.00' in row.get('text', '') for row in self.output.messages))
        rows = await self.turn('Confirm transfer.', ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], self.transfer_outcome)
        rows = await self.turn('Confirm transfer.', ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], 'refused')
        rows = await self.turn('Check the original result.', ('banking_transfer_status', {}))
        self.assertEqual(rows[-1][1]['state'], self.transfer_outcome)

    async def test_model_self_confirmation_in_review_turn_refuses(self):
        rows = await self.turn('Review a transfer.',
            ('banking_review_transfer', {'source': 'checking-A', 'destination': 'savings-A',
                                         'amount': '10.00', 'currency': 'USD'}),
            ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], 'refused')
        rows = await self.turn('Check status.', ('banking_transfer_status', {}))
        self.assertEqual(rows[-1][1]['state'], 'canceled')

    async def test_denial_and_intervening_turn_cannot_be_relabelled_confirmation(self):
        await self.review()
        rows = await self.turn('No, do not transfer.', ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], 'refused')
        rows = await self.turn('confirm transfer', ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], 'refused')
        await self.review()
        await self.turn('Which currency is that?')
        rows = await self.turn('confirm transfer', ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], 'refused')

    async def test_missing_host_interface_refuses_even_a_scripted_submit(self):
        with patch.dict(os.environ, {'BANKING_HOST_CAPABILITY': ''}):
            rows = await self.turn('confirm transfer', ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], 'refused')

    async def test_logout_without_model_tool_invalidates_the_cached_host_session(self):
        for command in ('logout', 'Log   out.', 'logout!', 'reset?'):
            with self.subTest(command=command):
                await self.turn('List my accounts.', ('banking_accounts', {}))
                await self.turn(command)
                rows = await self.turn('Read my balance.', ('banking_balance', {'account': 'checking-A'}))
                self.assertEqual(rows[-1][1]['state'], 'unavailable')

    async def test_other_conversation_cannot_confirm_a_pending_review(self):
        await self.review()
        original = self.sender
        self.sender = uuid4().hex
        rows = await self.turn('confirm transfer', ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], 'refused')
        self.sender = original
        rows = await self.turn('Confirm transfer.', ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], self.transfer_outcome)

    async def test_supplied_ledger_history_pages_payment_and_dated_payoff(self):
        rows = await self.turn('Read the ledger balance.',
            ('banking_balance', {'account': 'checking-A', 'balance_type': 'ledger'}))
        self.assertEqual(rows[-1][1]['amount'], '220.00' if self.profile == 'fiserv' else '110.00')
        self.assertEqual(rows[-1][1]['balance_type'], 'ledger')
        rows = await self.turn('Read history.', ('banking_history', {'account': 'checking-A'}))
        self.assertEqual(rows[-1][1]['entries'][0]['amount'], '-5.00')
        self.assertEqual(rows[-1][1]['page'], 1)
        self.assertTrue(rows[-1][1]['more'])
        rows = await self.turn('Read the next page.', ('banking_history', {'account': 'checking-A', 'page': 2}))
        self.assertEqual(rows[-1][1]['entries'][0]['amount'], '20.00')
        self.assertFalse(rows[-1][1]['more'])
        rows = await self.turn('Read my next payment.', ('banking_loan_payment', {'account': 'loan-A'}))
        self.assertEqual(rows[-1][1]['due_date'], '2026-01-20')
        self.assertEqual(rows[-1][1]['amount'], '75.00')
        rows = await self.turn('Read the supplied payoff quote.',
            ('banking_payoff', {'account': 'loan-A', 'date': '2026-01-15'}))
        self.assertEqual(rows[-1][1]['as_of'], '2026-01-15')
        self.assertEqual(rows[-1][1]['amount'], '650.50' if self.profile == 'fiserv' else '500.25')
        rows = await self.turn('Read a different date.',
            ('banking_payoff', {'account': 'loan-A', 'date': '2026-01-16'}))
        self.assertEqual(rows[-1][1]['state'], 'unsupported')

    async def test_loan_transfer_and_insufficient_funds_refuse(self):
        rows = await self.turn('Transfer from the loan.',
            ('banking_review_transfer', {'source': 'loan-A', 'destination': 'checking-A',
                                         'amount': '10.00', 'currency': 'USD'}))
        self.assertEqual(rows[-1][1]['state'], 'refused')
        rows = await self.turn('Review an overdrawn transfer.',
            ('banking_review_transfer', {'source': 'checking-A', 'destination': 'savings-A',
                                         'amount': '9999.00', 'currency': 'USD'}))
        self.assertEqual(rows[-1][1]['state'], 'pending')
        rows = await self.turn('confirm transfer', ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], 'refused')

    async def test_unknown_outcome_blocks_retries_even_after_logout(self):
        await self.review()
        rows = await self.turn('confirm transfer', ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], 'unknown')
        rows = await self.turn('Check the original outcome.', ('banking_transfer_status', {}))
        self.assertEqual(rows[-1][1]['state'], 'unknown')
        rows = await self.turn('confirm transfer', ('banking_submit_transfer', {}))
        self.assertEqual(rows[-1][1]['state'], 'refused')
        rows = await self.review()
        self.assertEqual(rows[-1][1]['state'], 'refused')
        await self.turn('logout!')
        await self.turn('List accounts.', ('banking_accounts', {}))
        rows = await self.review()
        self.assertEqual(rows[-1][1]['state'], 'refused')


class VoiceRequestTests(unittest.IsolatedAsyncioTestCase):
    PROJECT = None

    async def test_asr_opt_out_is_on_the_constructed_request(self):
        from urllib.parse import parse_qs, urlsplit
        from unittest.mock import AsyncMock
        from rasa.core.channels.voice_stream.audio_bytes import L16_16KHZ
        from rasa.core.channels.voice_stream.voice_channel import asr_engine_from_config
        from rasa.shared.utils.yaml import read_yaml_file
        settings = read_yaml_file(self.PROJECT / 'integrations.yml', expand_env_vars=False)
        config = settings['channels']['inspector']['asr']
        with patch.dict(os.environ, {'DEEPGRAM_API_KEY': 'fictional-transport-test'}), patch(
                'rasa.core.channels.voice_stream.asr.deepgram.engine.connect', new_callable=AsyncMock) as connect:
            engine = asr_engine_from_config(config, L16_16KHZ, 'en')
            await engine.open_websocket_connection()
            url = connect.await_args.args[0]
            self.assertEqual(parse_qs(urlsplit(url).query)['mip_opt_out'], ['true'])
            self.assertEqual(urlsplit(url).hostname, 'api.deepgram.com')
            self.assertNotIn('fictional-transport-test', url)

    async def test_tts_opt_out_is_on_the_constructed_request(self):
        from types import SimpleNamespace
        from urllib.parse import parse_qs, urlsplit
        from unittest.mock import AsyncMock
        from rasa.core.channels.voice_stream.audio_bytes import L16_24KHZ
        from rasa.core.channels.voice_stream.voice_channel import tts_engine_from_config
        from rasa.shared.utils.yaml import read_yaml_file
        settings = read_yaml_file(self.PROJECT / 'integrations.yml', expand_env_vars=False)
        config = settings['channels']['inspector']['tts']
        session = SimpleNamespace(closed=False, ws_connect=AsyncMock(return_value=SimpleNamespace()))
        with patch.dict(os.environ, {'DEEPGRAM_API_KEY': 'fictional-transport-test'}), patch(
                'rasa.core.channels.voice_stream.tts.deepgram.create_ssl_client_session', return_value=session):
            engine = tts_engine_from_config(config, L16_24KHZ, 'en')
            await engine.connect()
            url = session.ws_connect.await_args.args[0]
            self.assertEqual(parse_qs(urlsplit(url).query)['mip_opt_out'], ['true'])
            self.assertEqual(urlsplit(url).hostname, 'api.deepgram.com')
            self.assertNotIn('fictional-transport-test', url)


class LauncherTests(unittest.TestCase):
    PROJECT = None

    def test_missing_secrets_names_only_and_never_starts_a_service(self):
        import io
        from banking_demo import launcher
        with patch.dict(os.environ, {'RASA_PRO_LICENSE': '', 'OPENAI_API_KEY': '',
                                     'DEEPGRAM_API_KEY': '', 'PYTHON_DOTENV_DISABLED': 'true'}), \
                patch.object(sys, 'argv', ['run_demo.py']), \
                patch.object(launcher.subprocess, 'Popen') as spawn, \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(launcher.main(self.PROJECT), 2)
            self.assertIn('RASA_PRO_LICENSE', output.getvalue())
            spawn.assert_not_called()

    def test_real_archive_and_private_forwarded_origin_with_owned_service_cleanup(self):
        from banking_demo import launcher
        import io
        children = []
        real_spawn = subprocess.Popen
        class Child:
            def __init__(self, done=False):
                self.done = done
                self.returncode = 0 if done else None
                self.terminated = False
            def poll(self):
                return self.returncode
            def terminate(self):
                self.terminated = True
                self.returncode = 0
            def wait(self, timeout=None):
                return self.returncode
        def spawn(command, **kwargs):
            if command[0] != sys.executable or len(command) < 3 or command[2] not in {'rasa', 'banking_demo.launcher'}:
                return real_spawn(command, **kwargs)
            if command[2] == 'rasa':
                self.assertTrue(Path(command[command.index('--model') + 1]).is_file())
                from rasa.shared.utils.yaml import read_yaml_file
                config = read_yaml_file(Path(kwargs['cwd']) / 'integrations.yml', expand_env_vars=False)
                self.assertEqual(config['channels']['inspector']['server_url'],
                                 'https://fictional-space-5005.app.github.dev')
                self.assertEqual(config['model_groups'][0]['models'][0]['api_key'], '${OPENAI_API_KEY}')
                child = Child(done=True)
            else:
                for key in ('RASA_PRO_LICENSE', 'OPENAI_API_KEY', 'DEEPGRAM_API_KEY', 'RASA_LICENSE'):
                    self.assertNotIn(key, kwargs['env'])
                self.assertEqual(kwargs['pass_fds'], (int(command[4]),))
                # A real backend must consume the retained socket and pass readiness.
                child = real_spawn(command, **kwargs)
            if command[2] == 'rasa':
                self.assertTrue(kwargs['env']['BANKING_HOST_URL'].startswith('http://127.0.0.1:'))
            self.assertGreaterEqual(len(kwargs['env']['BANKING_HOST_CAPABILITY']), 32)
            children.append(child)
            return child
        with patch.dict(os.environ, {'RASA_PRO_LICENSE': 'placeholder-license-test',
                'OPENAI_API_KEY': 'placeholder-model-test', 'DEEPGRAM_API_KEY': 'placeholder-speech-test',
                'PYTHON_DOTENV_DISABLED': 'true', 'CODESPACE_NAME': 'fictional-space',
                'GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN': 'app.github.dev'}), \
                patch.object(sys, 'argv', ['run_demo.py']), \
                patch.object(launcher.subprocess, 'Popen', side_effect=spawn), \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(launcher.main(self.PROJECT), 0)
            self.assertEqual(len(children), 2)
            self.assertIsNotNone(children[0].poll())
            self.assertNotIn('placeholder-', output.getvalue())
