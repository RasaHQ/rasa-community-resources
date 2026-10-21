"""No-network checks for worker capability refusal and native call boundaries."""
from types import SimpleNamespace
from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import Mock, patch

import class_doctor

from briefing.native_runtime import UnsupportedAgentsSDK, native_turn


class NativeRuntimeTests(unittest.TestCase):
    def test_live_service_refuses_base_override_before_client_or_listener_without_echo(self):
        import briefing.__main__ as service
        for name in ('OPENAI_BASE_URL', 'ANTHROPIC_BASE_URL'):
            with self.subTest(variable=name):
                client = Mock()
                with patch.dict('os.environ', {name: 'https://canary-custom-endpoint.invalid/private-value',
                        'BRIEFING_MCP_TOKEN': 'invented-transport-token-for-test',
                        'BRIEFING_AGENTS_MODEL': 'offline-fixture'}, clear=True), \
                        patch.dict('sys.modules', {'openai': type('SDK', (), {'OpenAI': client})}), \
                        patch('sys.argv', ['briefing', '--live-model']), \
                        patch.object(service.uvicorn, 'run') as listener:
                    with self.assertRaises(SystemExit) as caught:
                        service.main()
                client.assert_not_called()
                listener.assert_not_called()
                self.assertIn('Refused: custom provider base URL', str(caught.exception))
                self.assertNotIn('canary', str(caught.exception))
                self.assertNotIn('private-value', str(caught.exception))

    def test_scripted_service_does_not_use_provider_client_when_override_is_present(self):
        import briefing.__main__ as service
        client = Mock()
        app = object()
        with patch.dict('os.environ', {'OPENAI_BASE_URL': 'https://canary.invalid',
                'BRIEFING_MCP_TOKEN': 'invented-transport-token-for-test'}, clear=True), \
                patch.dict('sys.modules', {'openai': type('SDK', (), {'OpenAI': client})}), \
                patch('sys.argv', ['briefing']), \
                patch.object(service, 'Jobs'), patch.object(service, 'create_app', return_value=app), \
                patch.object(service.uvicorn, 'run') as listener:
            service.main()
        client.assert_not_called()
        listener.assert_called_once_with(app, host='127.0.0.1', port=8942, log_level='warning')

    def test_service_rejects_unknown_arguments_without_echo(self):
        from briefing.__main__ import main
        with patch('sys.argv', ['briefing', '--invented-option', 'sk-canary-do-not-echo']):
            with self.assertRaises(SystemExit) as caught:
                main()
        self.assertNotIn('sk-canary', str(caught.exception))

    def test_doctor_missing_sdk_refusal_is_plain_and_does_not_echo_error(self):
        output = io.StringIO()
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'invented-canary-for-offline-test'}, clear=True), \
                patch.object(class_doctor, 'probe_agents', side_effect=UnsupportedAgentsSDK('private diagnostic')), \
                redirect_stdout(output):
            status = class_doctor.main(['--probe-agents'])
        self.assertEqual(status, 2)
        self.assertIn('Refused: the worker SDK lacks client.beta.agents.sessions;', output.getvalue())
        self.assertNotIn('private diagnostic', output.getvalue())
        self.assertNotIn('invented-canary', output.getvalue())

    def test_missing_or_noncallable_sessions_refuses_before_invocation(self):
        clients = [object(), SimpleNamespace(beta=SimpleNamespace(agents=object())),
                   SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(
                       sessions=SimpleNamespace(create=None))))]
        for client in clients:
            with self.subTest(client=type(client).__name__):
                with self.assertRaises(UnsupportedAgentsSDK):
                    native_turn(client, agent={}, text='request',
                                invoke=lambda *a, **k: self.fail('provider called before capability refusal'))

    def test_native_receives_caps_and_returns_actual_core_result(self):
        client = SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(
            sessions=SimpleNamespace(create=lambda **kw: None))))
        result = object()
        calls = []
        def invoke(got, **kwargs):
            calls.append((got, kwargs))
            return result
        handlers = {'read_weather': lambda arguments: {}}
        self.assertIs(native_turn(client, agent={'model': 'fixture'}, text='prior validated brief',
                                  handlers=handlers, invoke=invoke), result)
        self.assertIs(calls[0][0], client)
        self.assertEqual(calls[0][1], dict(agent={'model': 'fixture'},
            environment={'type': 'openai_hosted'}, text='prior validated brief', handlers=handlers,
            max_calls=16, max_events=10000, deadline_seconds=60, timeout=20))
        self.assertNotIn('session_id', calls[0][1])


if __name__ == '__main__':
    unittest.main()
