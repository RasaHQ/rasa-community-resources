"""Handoff with context transfer — the package, its allowlist, and the desk.

Three modules, one boundary:

    schema      the typed package; ``summary`` is a derived property, not a field
    redaction   the allowlist, and the only supported session → package builder
    desk        the fixture receiving side that reconstructs the caller's state

Import order matters only in that ``schema`` imports ``summary``; nothing else
is cyclic.
"""

from handoffpkg.desk import DeskView, reconstruct, unanswered_questions
from handoffpkg.redaction import (
    SESSION_ALLOWLIST,
    build_package_from_session,
    filter_session,
    scan_freetext_risk,
)
from handoffpkg.schema import (
    Attempt,
    DoNotRepeat,
    HandoffPackage,
    Identity,
    Intent,
    TIER_MEANING,
    TIER_ORDER,
    package_from_dict,
    tier_at_least,
)

__all__ = [
    "Attempt",
    "DeskView",
    "DoNotRepeat",
    "HandoffPackage",
    "Identity",
    "Intent",
    "SESSION_ALLOWLIST",
    "TIER_MEANING",
    "TIER_ORDER",
    "build_package_from_session",
    "filter_session",
    "package_from_dict",
    "reconstruct",
    "scan_freetext_risk",
    "tier_at_least",
    "unanswered_questions",
]
