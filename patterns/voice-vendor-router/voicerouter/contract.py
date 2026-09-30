"""Check that the router still covers everything Rasa uses on an engine.

The router is not a `TTSEngine` / `ASREngine` subclass — Rasa resolves engines
by dotted path and never type-checks them, so the router only has to satisfy
the surface the voice channel actually uses. That is a deliberate trade, and it
has one failure mode: a Rasa release starts using something new, and the router
fails on a live call instead of at startup.

"Uses" is more than "calls". The first version of this check scanned for
`tts_engine.<name>(` and `asr_engine.<name>(` and passed on rasa-pro
3.21.0.dev5 while every routed call died, because what broke them was not a
method call:

  * `async with asr_engine, tts_engine:` in `run_audio_streaming` needs the
    async context-manager protocol;
  * `getattr(asr_engine.config, "keep_alive_interval", 5)` reads an attribute;
  * `self.tts_engine.stream_state = ...` writes one.

So the surface has four parts, each derived from the installed Rasa rather
than written down here:

  calls      `<kind>_engine.<name>(` anywhere in the voice-stream package
  reads      `<kind>_engine.<name>` not followed by a call or an assignment,
             plus `engine.<name>` in the voice tracing recorders for that kind
  writes     `<kind>_engine.<name> = ...`
  protocols  `async with` statements that enter a `<kind>_engine`

Attributes are checked on the class, so the router declares them at class
level (a property, a method or a class attribute), and a written attribute
must not be a read-only property. Run it from `make verify`; it needs no
credentials and no network.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

KINDS = ("tts", "asr")

ASYNC_CONTEXT_MANAGER = "async context manager"

# Uses the scan cannot see or that belong to the engine's lifecycle rather than
# to a call site. `from_config_dict` is reached through `class_from_module_path`,
# and the base classes' `__aenter__` / `__aexit__` call `connect` and
# `close_connection`, so the router must provide them however it enters.
_FLOOR = {
    kind: {
        "calls": {"connect", "close_connection", "name", "from_config_dict"},
        "reads": set(),
        "writes": set(),
        "protocols": set(),
    }
    for kind in KINDS
}

_NAME = r"([a-z_][A-Za-z0-9_]*)"


def _patterns(kind: str) -> dict[str, re.Pattern]:
    ref = rf"\b{kind}_engine\.{_NAME}"
    return {
        "call": re.compile(ref + r"\s*\("),
        "write": re.compile(ref + r"\s*=(?!=)"),
        "any": re.compile(ref),
        "async_with": re.compile(rf"\basync\s+with\b[^:\n]*\b{kind}_engine\b"),
    }


_TRACING_REF = re.compile(rf"\bengine\.{_NAME}(\s*\()?")


@dataclass
class Surface:
    """What the installed Rasa uses on one kind of engine, and where."""

    kind: str
    calls: set[str] = field(default_factory=set)
    reads: set[str] = field(default_factory=set)
    writes: set[str] = field(default_factory=set)
    protocols: set[str] = field(default_factory=set)
    #: (part, item) -> ["core/channels/voice_stream/voice_channel.py:1489", ...]
    sources: dict[tuple[str, str], list[str]] = field(default_factory=dict)

    def note(self, part: str, item: str, where: str) -> None:
        getattr(self, part).add(item)
        self.sources.setdefault((part, item), []).append(where)

    def where(self, part: str, item: str) -> str:
        places = self.sources.get((part, item), [])
        shown = ", ".join(places[:2])
        return shown + (f" and {len(places) - 2} more" if len(places) > 2 else "")

    @property
    def label(self) -> str:
        return f"{'an' if self.kind == 'asr' else 'a'} {self.kind.upper()} engine"

    @property
    def size(self) -> int:
        return len(self.calls) + len(self.reads) + len(self.writes) + len(self.protocols)


def _rasa_dir() -> Optional[Path]:
    try:
        import rasa
    except ImportError:
        return None
    return Path(rasa.__file__).parent


def scan(kind: str, rasa_dir: Optional[Path] = None) -> Surface:
    """The surface found in the installed Rasa's source, without the floor."""
    surface = Surface(kind)
    rasa_dir = rasa_dir or _rasa_dir()
    if rasa_dir is None:
        return surface
    patterns = _patterns(kind)

    voice_stream = rasa_dir / "core" / "channels" / "voice_stream"
    for path in sorted(voice_stream.rglob("*.py")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for number, line in enumerate(lines, 1):
            where = f"{path.relative_to(rasa_dir)}:{number}"
            called = set(patterns["call"].findall(line))
            written = set(patterns["write"].findall(line))
            for name in called:
                surface.note("calls", name, where)
            for name in written:
                surface.note("writes", name, where)
            for name in set(patterns["any"].findall(line)) - called - written:
                surface.note("reads", name, where)
            if patterns["async_with"].search(line):
                surface.note("protocols", ASYNC_CONTEXT_MANAGER, where)

    recorders = rasa_dir / "tracing" / "voice" / "recorders" / kind
    for path in sorted(recorders.glob("*.py")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for number, line in enumerate(lines, 1):
            where = f"{path.relative_to(rasa_dir)}:{number}"
            for name, call in _TRACING_REF.findall(line):
                surface.note("calls" if call else "reads", name, where)

    # A name both read and called is a method; one both read and written only
    # needs to be settable, which the write check already demands.
    surface.reads -= surface.calls
    return surface


def required_surface(kind: str, rasa_dir: Optional[Path] = None) -> Surface:
    """Everything the router must provide for this kind of engine."""
    surface = scan(kind, rasa_dir)
    for part, items in _FLOOR[kind].items():
        for item in items:
            if item not in getattr(surface, part):
                surface.note(part, item, "voicerouter.contract (lifecycle)")
    surface.reads -= surface.calls
    return surface


def missing(engine_cls: type, surface: Surface) -> list[str]:
    """One line per part of the surface this class does not provide."""
    problems: list[str] = []

    for name in sorted(surface.calls):
        if not callable(getattr(engine_cls, name, None)):
            problems.append(f"method {name}() (called at {surface.where("calls", name)})")

    for name in sorted(surface.reads):
        if not hasattr(engine_cls, name):
            problems.append(f"attribute {name} (read at {surface.where("reads", name)})")

    for name in sorted(surface.writes):
        declared = inspect.getattr_static(engine_cls, name, None)
        if declared is None and not hasattr(engine_cls, name):
            problems.append(
                f"attribute {name} (written at {surface.where('writes', name)}). "
                f"Undeclared, the write would land on the router and never "
                f"reach a provider"
            )
        elif isinstance(declared, property) and declared.fset is None:
            problems.append(
                f"settable attribute {name}: it is a read-only property "
                f"(written at {surface.where("writes", name)})"
            )
        elif callable(declared) and not isinstance(declared, property):
            problems.append(
                f"attribute {name}: it is a method, and Rasa assigns to it "
                f"(written at {surface.where("writes", name)})"
            )

    if ASYNC_CONTEXT_MANAGER in surface.protocols:
        if not all(
            inspect.iscoroutinefunction(getattr(engine_cls, dunder, None))
            for dunder in ("__aenter__", "__aexit__")
        ):
            problems.append(
                "the async context-manager protocol (async __aenter__ and "
                f"__aexit__; entered at {surface.where('protocols', ASYNC_CONTEXT_MANAGER)})"
            )
    return problems


def check(verbose: bool = True) -> list[str]:
    """Return a list of problems; empty means the contract holds."""
    from voicerouter.routed_asr import RoutedASR
    from voicerouter.routed_tts import RoutedTTS

    problems: list[str] = []
    for kind, cls in (("tts", RoutedTTS), ("asr", RoutedASR)):
        surface = required_surface(kind)
        gaps = missing(cls, surface)
        if verbose:
            print(
                f"  {cls.__name__}: {surface.size - len(gaps)}/{surface.size} of the "
                f"surface Rasa uses on {surface.label} "
                f"({len(surface.calls)} calls, {len(surface.reads)} reads, "
                f"{len(surface.writes)} writes, {len(surface.protocols)} protocol)"
            )
        for gap in gaps:
            problems.append(
                f"{cls.__name__} lacks {gap}. The installed Rasa uses it on "
                f"{surface.label}."
            )
    if verbose:
        for p in problems:
            print(f"  MISSING: {p}")
        if not problems:
            print("  contract holds against the installed rasa-pro")
    return problems


def format_surface() -> Iterable[str]:
    """Human-readable dump of what was detected, for the README and for debugging."""
    for kind in KINDS:
        surface = required_surface(kind)
        yield f"{kind}:"
        for part in ("calls", "reads", "writes", "protocols"):
            for item in sorted(getattr(surface, part)):
                yield f"  {part[:-1]:<8} {item:<36} {surface.where(part, item)}"


if __name__ == "__main__":
    import sys

    if "--surface" in sys.argv:
        print("\n".join(format_surface()))
        raise SystemExit(0)
    raise SystemExit(1 if check() else 0)
