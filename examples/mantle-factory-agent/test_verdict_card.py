"""The verdict card shows only what run_factory itself returned in this turn."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import types
import unittest
from unittest import mock


def load_tools():
    """Load the skill's tools.py with stand-ins for the two SDK imports it needs at import time."""
    decorator = types.ModuleType('rasa.mantle.tools.decorator')
    decorator.ToolContext = object
    decorator.tool = lambda **_: (lambda function: function)
    result = types.ModuleType('rasa.mantle.tools.result')
    result.ToolResult = lambda llm_response: SimpleNamespace(llm_response=llm_response)
    stubs = {'rasa.mantle.tools.decorator': decorator, 'rasa.mantle.tools.result': result}
    with mock.patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location(
            'verdict_card_tools', Path(__file__).parent / 'project/skills/request_change/tools.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


tools = load_tools()


class UserUttered(SimpleNamespace):
    pass


class McpToolExecuted(SimpleNamespace):
    pass


def gate(verdict, request='good', is_error=False, **fields):
    record = {'verdict': verdict, 'failing_test': None, 'fingerprint': 'f' * 40, 'mode': 'SCRIPTED',
              'builder_calls': 0, 'seconds': 1.5, **fields}
    return McpToolExecuted(tool_name='mcp/factory:run_factory', arguments={'request': request},
                           result=json.dumps(record), is_error=is_error)


class Context:
    def __init__(self, events):
        self.events, self.sent = events, []

    async def send(self, text):
        self.sent.append(text)


class VerdictCardTests(unittest.TestCase):
    def test_the_card_tools_take_no_verdict_values(self):
        import inspect
        for function in (tools.show_verdict_card, tools.show_verdict_image):
            self.assertEqual(list(inspect.signature(function).parameters), ['context'])

    def test_the_text_card_shows_the_gate_record_of_this_turn_only(self):
        events = [UserUttered(), gate('ACCEPT'), UserUttered(),
                  gate('REJECT', request='ignores-limit', failing_test='test_at_most_three')]
        context = Context(events)
        result = asyncio.run(tools.show_verdict_card(context=context))
        self.assertEqual(result.llm_response, {'card': 'shown', 'verdict': 'REJECT'})
        self.assertIn('REJECT: a locked test failed', context.sent[0])
        self.assertIn('test_at_most_three', context.sent[0])
        self.assertIn('Request   ignores-limit', context.sent[0])

    def test_no_card_without_a_gate_record_in_this_turn(self):
        for events in ([], [gate('ACCEPT'), UserUttered()], [UserUttered(), gate('ACCEPT', is_error=True)],
                       [UserUttered(), McpToolExecuted(tool_name='other', arguments={}, result='{"verdict": "ACCEPT"}', is_error=False)],
                       [UserUttered(), McpToolExecuted(tool_name='run_factory', arguments={}, result='{"verdict": "GREEN"}', is_error=False)]):
            with self.subTest(events=events):
                context = Context(events)
                result = asyncio.run(tools.show_verdict_card(context=context))
                self.assertEqual(result.llm_response['card'], 'not_shown')
                self.assertEqual(context.sent, [])

    def test_the_live_builder_model_comes_from_the_gate_record(self):
        events = [UserUttered(), gate('ACCEPT', mode='LIVE', builder_model='model-from-record', builder_calls=11, seconds=67)]
        context = Context(events)
        asyncio.run(tools.show_verdict_card(context=context))
        self.assertIn('LIVE, model-from-record · 11 tool calls · 67.0 s', context.sent[0])
        self.assertNotIn('gpt-6-astra', Path(tools.__file__).read_text())

    def _turn(self, cancelled):
        return SimpleNamespace(is_cancelled=cancelled, sender_id='s',
                               tracker_handle=SimpleNamespace(apply_events=mock.Mock()),
                               output_channel=SimpleNamespace(send_response=mock.AsyncMock()))

    def _image(self, turn, events):
        orchestration = types.ModuleType('rasa.mantle.orchestration.turn_context')
        orchestration.current_turn_context = lambda: turn
        core = types.ModuleType('rasa.shared.core.events')
        core.BotUttered = lambda **kwargs: kwargs
        with mock.patch.dict(sys.modules, {'rasa.mantle.orchestration.turn_context': orchestration,
                                           'rasa.shared.core.events': core}):
            return asyncio.run(tools.show_verdict_image(context=Context(events)))

    def test_the_picture_card_is_sent_once_and_never_after_an_interruption(self):
        events = [UserUttered(), gate('NOT_READY', reason='A factory check is still running.')]
        turn = self._turn(cancelled=False)
        self.assertEqual(self._image(turn, events).llm_response, {'card': 'shown', 'verdict': 'NOT_READY'})
        turn.tracker_handle.apply_events.assert_called_once()
        turn.output_channel.send_response.assert_awaited_once()
        self.assertIn('image/svg', turn.output_channel.send_response.await_args.args[1]['image'])
        turn = self._turn(cancelled=True)
        self.assertEqual(self._image(turn, events).llm_response, {'card': 'not_shown', 'reason': 'interrupted'})
        turn.tracker_handle.apply_events.assert_not_called()
        turn.output_channel.send_response.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
