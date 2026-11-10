"""Inspect both history choices across two real native wrapper invocations."""
import json
from strands import Agent
from .scripted_model import ScriptedTextModel


def inspect_pair(preserve_context, record_direct_tool_call):
    model = ScriptedTextModel()
    specialist = Agent(model=model, name="network_specialist", callback_handler=None, load_tools_from_directory=False)
    orchestrator_model = ScriptedTextModel()
    wrapper = specialist.as_tool(preserve_context=preserve_context)
    caller = Agent(model=orchestrator_model, tools=[wrapper], callback_handler=None, load_tools_from_directory=False)
    for text in ("Caller A private fixture", "Caller B private fixture"):
        result = caller.tool.network_specialist(input=text, record_direct_tool_call=record_direct_tool_call)
        if result["status"] != "success":
            raise AssertionError(result)
    assert len(model.inputs) == 2
    assert orchestrator_model.inputs == []
    second = json.dumps(model.inputs[1])
    return {
        "preserve_context": preserve_context,
        "record_direct_tool_call": record_direct_tool_call,
        "caller_messages": len(caller.messages),
        "second_input_includes_A": "Caller A private fixture" in second,
        "second_input_includes_B": "Caller B private fixture" in second,
    }
