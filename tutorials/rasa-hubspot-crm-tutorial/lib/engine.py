"""Engine imports, resolved in one place.

Rasa renamed the Mantle engine package from ``rasa.calm_v2`` to ``rasa.mantle``
in 3.20.0.dev1, and the old path is gone rather than aliased. This project is
pinned to a release that ships the new name, so the first import wins; the
fallback is what lets the same code run against an older pin.

Drop the fallback once nothing you care about runs on 3.19 or earlier.

The re-exported objects are the real ones, not wrappers: the tool loader finds
tools by looking for the ``_tool_description`` attribute the decorator sets, so
where you imported it from makes no difference to discovery.
"""

from __future__ import annotations

try:  # 3.20.0.dev1 and later
    from rasa.mantle.tools.decorator import ToolContext, tool
    from rasa.mantle.tools.result import ToolResult

    ENGINE_PACKAGE = "rasa.mantle"
except ImportError:  # 3.19.x and earlier
    from rasa.calm_v2.tools.decorator import ToolContext, tool
    from rasa.calm_v2.tools.result import ToolResult

    ENGINE_PACKAGE = "rasa.calm_v2"

__all__ = ["ENGINE_PACKAGE", "ToolContext", "ToolResult", "tool"]
