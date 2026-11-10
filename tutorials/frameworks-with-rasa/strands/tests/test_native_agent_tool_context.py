"""Native agent-as-tool context controls with scripted text, not provider evidence."""
import json
import unittest
from strands import Agent

from network_specialist.scripted_model import ScriptedTextModel

class NativeAgentToolContexts(unittest.TestCase):
    def call_pair(self, preserve_context=False):
        model = ScriptedTextModel()
        specialist = Agent(model=model, name="network_specialist", callback_handler=None, load_tools_from_directory=False)
        tool = specialist.as_tool(preserve_context=preserve_context)
        orchestrator = Agent(model=ScriptedTextModel(), tools=[tool], callback_handler=None, load_tools_from_directory=False)
        first = orchestrator.tool.network_specialist(input="Caller A private fixture", record_direct_tool_call=False)
        second = orchestrator.tool.network_specialist(input="Caller B private fixture", record_direct_tool_call=False)
        self.assertEqual(first["status"], "success", first)
        self.assertEqual(second["status"], "success", second)
        return model, orchestrator, first, second

    def test_default_agent_as_tool_resets_specialist_history(self):
        model, _, first, second = self.call_pair()
        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "success")
        self.assertEqual(len(model.inputs), 2)
        self.assertIn("Caller A private fixture", json.dumps(model.inputs[0]))
        self.assertNotIn("Caller A private fixture", json.dumps(model.inputs[1]))
        self.assertIn("Caller B private fixture", json.dumps(model.inputs[1]))

    def test_preserved_context_includes_previous_caller_fixture(self):
        model, orchestrator, _, _ = self.call_pair(preserve_context=True)
        self.assertEqual(orchestrator.messages, [])
        self.assertIn("Caller A private fixture", json.dumps(model.inputs[1]))
        self.assertIn("Caller B private fixture", json.dumps(model.inputs[1]))

    def test_history_matrix_keeps_parent_recording_separate_from_specialist_context(self):
        from network_specialist.context_exercise import inspect_pair
        for preserve in (False, True):
            for record in (False, True):
                with self.subTest(preserve_context=preserve, record_direct_tool_call=record):
                    result = inspect_pair(preserve, record)
                    self.assertEqual(result["caller_messages"], 8 if record else 0)
                    self.assertEqual(result["second_input_includes_A"], preserve)
                    self.assertTrue(result["second_input_includes_B"])

    def test_nonrecording_wrapper_leaves_orchestrator_history_empty(self):
        _, orchestrator, _, _ = self.call_pair()
        self.assertEqual(orchestrator.messages, [])

if __name__ == "__main__":
    unittest.main()
