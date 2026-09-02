"""Check that the router still covers everything Rasa calls on an engine.

The router is not a `TTSEngine` / `ASREngine` subclass — Rasa resolves engines
by dotted path and never type-checks them, so the router only has to satisfy the
methods the voice channel actually uses. That is a deliberate trade, and it has
one failure mode: a future Rasa release starts calling something new, and the
router raises `AttributeError` on a live call instead of at startup.

So the surface is derived from the installed Rasa rather than written down here.
Run it from `make verify`; it needs no credentials and no network.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

# Lifecycle calls the channel makes through other paths (context managers,
# setup) that a plain call-site scan does not see.
_ALWAYS_REQUIRED = {
    "tts": {"connect", "close_connection", "name", "from_config_dict"},
    "asr": {"connect", "close_connection", "name", "from_config_dict"},
}

_CALL_RE = {
    "tts": re.compile(r"tts_engine\.([a-z_]+)\("),
    "asr": re.compile(r"asr_engine\.([a-z_]+)\("),
}


def _voice_stream_dir() -> Path | None:
    try:
        import rasa.core.channels.voice_stream as vs
    except ImportError:
        return None
    return Path(vs.__file__).parent


def required_methods(kind: str) -> set[str]:
    """Every method the installed Rasa calls on an engine of this kind."""
    directory = _voice_stream_dir()
    if directory is None:
        return set(_ALWAYS_REQUIRED[kind])
    found: set[str] = set()
    for path in directory.rglob("*.py"):
        found |= set(_CALL_RE[kind].findall(path.read_text(encoding="utf-8", errors="replace")))
    return found | _ALWAYS_REQUIRED[kind]


def missing_methods(engine_cls: type, kind: str) -> list[str]:
    """Methods Rasa calls that this router does not implement."""
    return sorted(m for m in required_methods(kind) if not hasattr(engine_cls, m))


def check(verbose: bool = True) -> list[str]:
    """Return a list of problems; empty means the contract holds."""
    from voicerouter.routed_asr import RoutedASR
    from voicerouter.routed_tts import RoutedTTS

    problems: list[str] = []
    for kind, cls in (("tts", RoutedTTS), ("asr", RoutedASR)):
        required = required_methods(kind)
        missing = missing_methods(cls, kind)
        if verbose:
            print(f"  {cls.__name__}: {len(required) - len(missing)}/{len(required)} of the "
                  f"surface Rasa calls")
        if missing:
            problems.append(
                f"{cls.__name__} is missing {', '.join(missing)} — the installed "
                f"Rasa calls {'it' if len(missing) == 1 else 'them'} on a {kind} "
                f"engine, so a live call would raise AttributeError."
            )
    if verbose:
        for p in problems:
            print(f"  MISSING: {p}")
        if not problems:
            print("  contract holds against the installed rasa-pro")
    return problems


def format_surface() -> Iterable[str]:
    """Human-readable dump of what was detected, for the README and for debugging."""
    for kind in ("tts", "asr"):
        yield f"{kind}: {', '.join(sorted(required_methods(kind)))}"


if __name__ == "__main__":
    raise SystemExit(1 if check() else 0)
