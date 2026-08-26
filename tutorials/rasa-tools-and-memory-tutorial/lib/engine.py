"""Engine imports, resolved in one place.

Rasa is renaming the Mantle engine package from ``rasa.calm_v2`` to
``rasa.mantle``. The documentation already shows the new path, but no release
published so far ships it — including 3.19.0.dev7 and 3.19.1 — so importing it
directly fails today.

Every tool in this project imports the decorator from here instead. When a
release lands ``rasa.mantle``, this file starts resolving to it and no tool
changes. Delete the fallback once the old path is gone.

The re-exported objects are the real ones, not wrappers: the tool loader finds
tools by looking for the ``_tool_description`` attribute the decorator sets, so
where you imported it from makes no difference to discovery.
"""

from __future__ import annotations

try:  # Mantle after the rename
    from rasa.mantle.tools.decorator import ToolContext, tool
    from rasa.mantle.tools.result import ToolResult

    ENGINE_PACKAGE = "rasa.mantle"
except ImportError:  # every release published so far
    from rasa.calm_v2.tools.decorator import ToolContext, tool
    from rasa.calm_v2.tools.result import ToolResult

    ENGINE_PACKAGE = "rasa.calm_v2"

__all__ = ["ENGINE_PACKAGE", "ToolContext", "ToolResult", "tool"]
