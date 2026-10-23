"""Prevent accidental tool recalls after invalid gate results."""
import unittest
from scripted import ScriptedClient

TOOLS = [{'type': 'function', 'function': {'name': 'mcp/factory:run_factory'}}]


class ScriptedTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_gate_result_does_not_retry(self):
        messages = [
            {'role': 'user', 'content': 'Show at most three currencies on the market card'},
            {'role': 'assistant', 'tool_calls': [{'id': 'gate1', 'function': {'name': 'mcp/factory:run_factory'}}]},
            {'role': 'tool', 'tool_call_id': 'gate1', 'content': 'MCP timeout'},
        ]
        result = await ScriptedClient().acompletion(messages, tools=TOOLS)
        self.assertFalse(result.tool_calls)
        self.assertIn('NOT_READY', result.choices[0])

    async def test_skill_activation_does_not_prevent_one_gate_call(self):
        messages = [
            {'role': 'user', 'content': 'Show at most three currencies on the market card'},
            {'role': 'assistant', 'tool_calls': [{'id': 'activate1', 'function': {'name': 'activate'}}]},
            {'role': 'tool', 'tool_call_id': 'activate1', 'content': 'Activated Request a Change'},
        ]
        result = await ScriptedClient().acompletion(messages, tools=TOOLS)
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].tool_name, 'mcp/factory:run_factory')

    async def test_gate_verdict_does_not_trigger_another_call(self):
        result = await ScriptedClient().acompletion([
            {'role': 'user', 'content': 'Use the attempt that ignores the limit'},
            {'role': 'tool', 'content': '{"verdict":"REJECT","failing_test":"test_b1","fingerprint":"abc","mode":"SCRIPTED"}'},
        ], tools=TOOLS)
        self.assertFalse(result.tool_calls)
        self.assertIn('REJECT', result.choices[0])
