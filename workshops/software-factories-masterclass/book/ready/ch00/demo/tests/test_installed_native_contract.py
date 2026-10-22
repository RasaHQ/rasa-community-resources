"""Actual installed Core native adapter with an offline SDK-shaped stream."""
from pathlib import Path
from importlib.util import find_spec
from importlib.metadata import version
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'project')]
try:
    from zeo_core.integrations.agents import run_native
except ImportError:
    run_native = None
from briefing.native_runtime import native_turn


class Stream:
    # There is deliberately no public session_id attribute on this SDK stream.
    def __init__(self, handlers, repeat):
        self.handlers, self.repeat = handlers, repeat
        self.closed = False
        self.final_collected = False

    def with_result_collection(self):
        return self

    def __iter__(self):
        yield {'type': 'agent.session.turn.created', 'turn': {'id': 'synthetic-turn'}}
        for handler in self.handlers.values():
            for _ in range(self.repeat):
                try:
                    handler({})
                except Exception:
                    # Mirror the real SDK's dispatcher swallowing handler errors.
                    pass
                yield {'type': 'synthetic.callback-dispatched'}
        yield {'type': 'agent.session.turn.completed', 'turn_id': 'synthetic-turn'}
        yield {'type': 'agent.session.idle'}
        raise AssertionError('A persistent session stream was read beyond the turn boundary')

    def get_final_result(self):
        self.final_collected = True
        return SimpleNamespace(session_id='synthetic-session', output_text='READY')

    def close(self):
        self.closed = True


class Sessions:
    def __init__(self, repeat=1):
        self.repeat = repeat
        self.stream = None

    def create(self, *, agent, environment, input, stream, tool_handlers, timeout, **optional):
        if stream is not True or timeout != 20 or environment != {'type': 'openai_hosted', 'network': {'access': 'disabled'}} or 'spend_control' in optional:
            raise AssertionError('Unexpected native SDK invocation')
        self.stream = Stream(tool_handlers, self.repeat)
        return self.stream


@unittest.skipUnless(run_native is not None, 'separate live-worker dev20 interpreter required')
class InstalledNativeContract(unittest.TestCase):
    @unittest.skipUnless(find_spec("openai") is not None and version("openai") == "3.36.1",
                         "separate live-worker OpenAI 3.36.1 interpreter required")
    def test_installed_sdk_exposes_the_exact_native_create_surface_without_a_request(self):
        from importlib.metadata import version
        from inspect import signature
        from openai import OpenAI
        self.assertEqual(version('openai'), '3.36.1')
        with OpenAI(api_key='invented-offline-constructor-canary', max_retries=0) as client:
            parameters = signature(client.beta.agents.sessions.create).parameters
            self.assertTrue({'agent', 'environment', 'input', 'stream', 'tool_handlers', 'timeout', 'spend_control'} <= parameters.keys())

    def test_actual_core_dispatches_handler_and_stops_at_persistent_stream_boundary(self):
        sessions = Sessions()
        client = SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(sessions=sessions)))
        called = []
        result = native_turn(client, agent={'model': 'offline-fixture'}, text='constructed request',
                             handlers={'read': lambda arguments: called.append(arguments) or {'ok': True}})
        self.assertTrue(result.ok)
        self.assertEqual(called, [{}])
        self.assertEqual(result.tools_called, ('read',))
        self.assertEqual(result.session_id, 'synthetic-session')
        self.assertTrue(sessions.stream.final_collected)

    def test_swallowed_handler_cap_never_becomes_success(self):
        sessions = Sessions(repeat=17)
        client = SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(sessions=sessions)))
        called = []
        result = native_turn(client, agent={'model': 'offline-fixture'}, text='constructed request',
                             handlers={'read': lambda arguments: called.append(arguments) or {'ok': True}})
        self.assertFalse(result.ok)
        self.assertEqual(result.status, 'incomplete')
        self.assertTrue(result.error_code)
        self.assertEqual(len(called), 16)
        self.assertTrue(sessions.stream.closed)
        self.assertFalse(sessions.stream.final_collected)


if __name__ == '__main__':
    unittest.main()
