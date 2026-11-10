"""Native model fixture for context inspection; never calls a provider."""
import copy
from strands.models.model import Model

class ScriptedTextModel(Model):
    def __init__(self):
        self.inputs = []
    def update_config(self, **kwargs):
        pass
    def get_config(self):
        return {}
    async def structured_output(self, *args, **kwargs):
        raise AssertionError("Not used")
        yield
    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.inputs.append(copy.deepcopy(messages))
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Synthetic read-only reply."}}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}
