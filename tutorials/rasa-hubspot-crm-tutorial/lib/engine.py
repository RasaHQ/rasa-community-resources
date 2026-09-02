"""Engine imports, resolved in one place.

Rasa renamed the Mantle engine package from ``rasa.calm_v2`` to ``rasa.mantle``
in 3.20.0.dev1, and the old path is gone rather than aliased. This project is
pinned to a release that ships the new name, so it imports it directly; the
try/except fallback that once covered 3.19.x pins was dropped when the catalog
moved wholly onto the 3.20 line (nothing here runs on the old name any more).

Keeping this module is still worth it: every tool imports the engine from here
and nowhere else, so the next rename is a one-file change.

The re-exported objects are the real ones, not wrappers: the tool loader finds
tools by looking for the ``_tool_description`` attribute the decorator sets, so
where you imported it from makes no difference to discovery.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

ENGINE_PACKAGE = "rasa.mantle"

__all__ = ["ENGINE_PACKAGE", "ToolContext", "ToolResult", "tool"]
