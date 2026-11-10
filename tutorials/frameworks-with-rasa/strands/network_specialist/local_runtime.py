"""Direct-tool demo runtime. Generation is deliberately unavailable."""
from strands import Agent
from strands.models.model import Model
from .tools import inspect_network

class DirectToolsOnlyModel(Model):
    def update_config(self, **kwargs):
        pass
    def get_config(self):
        return {}
    async def structured_output(self, *args, **kwargs):
        raise RuntimeError("This demo exposes existing tools, not specialist generation")
        yield
    async def stream(self, *args, **kwargs):
        raise RuntimeError("This demo exposes existing tools, not specialist generation")
        yield


def create_specialist():
    return Agent(model=DirectToolsOnlyModel(), tools=[inspect_network], callback_handler=None, load_tools_from_directory=False)
