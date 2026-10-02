"""Project-global list_accounts tool used by the fixture agent.

Runtime Mantle tools use ``from rasa.mantle.tools.decorator import tool, ToolContext``.
This fixture is parsed by static checks only and does not import rasa-pro.
"""


def list_accounts() -> list[str]:
    """Return fixture account ids."""
    return ["acc-1"]
