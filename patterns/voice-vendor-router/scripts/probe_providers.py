#!/usr/bin/env python3
"""Report which voice vendors this machine can actually reach.

Reads the real `integrations.yml`, builds each provider through Rasa's own
factory, and reports what happened. No audio is synthesised and no call is
placed; this answers "which of these will the router have available?" before you
find out mid-conversation.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GREEN, RED, YELLOW, DIM, RESET = (
    ("\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m")
    if sys.stdout.isatty() else ("", "", "", "", "")
)


def _load_env() -> None:
    for candidate in (ROOT / ".env", ROOT.parent.parent / ".env"):
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


# ---------------------------------------------------------------------------
# Reachability, as a library.
#
# `make probe` prints this; `make bench` replays audio through it. Both need
# the same question answered — "which of these will actually build here?" — and
# it is answered in exactly one place, through Rasa's own factory, so the two
# can never disagree about what is reachable.
# ---------------------------------------------------------------------------


@dataclass
class Reachability:
    """One provider entry, and what happened when it was built."""

    label: str
    name: str
    #: The constructed engine, or None when it could not be built.
    engine: Any
    #: Why it could not be built. Empty when it was.
    reason: str = ""
    #: True when the failure is "not usable here" rather than "misconfigured".
    #: A skip is expected and reported; an error is a defect worth seeing.
    skipped: bool = False

    @property
    def reachable(self) -> bool:
        return self.engine is not None


def load_inspector(kind: str) -> dict:
    """The `providers:` section for one kind, straight from integrations.yml."""
    import yaml

    inspector = (yaml.safe_load((ROOT / "integrations.yml").read_text())
                 .get("channels", {}).get("inspector", {}))
    return inspector.get(kind) or {}


def probe(
    kind: str,
    audio_format: Any = None,
    overrides: dict[str, dict] | None = None,
) -> Iterator[Reachability]:
    """Build every configured provider of `kind` through Rasa's own factory.

    Nothing is cached and nothing is guessed from environment variables: a
    provider is reachable exactly when its constructor returns, which is the
    same test the router itself applies at call time.

    `overrides` maps a provider's dotted name to extra config merged over its
    `integrations.yml` entry. It exists so a caller can supply a path it
    discovered at runtime — a downloaded local model, say — without editing the
    committed configuration or rebuilding provider construction elsewhere.
    """
    from rasa.core.channels.voice_stream.audio_bytes import L16_24KHZ
    from rasa.core.channels.voice_stream.voice_channel import (
        asr_engine_from_config,
        tts_engine_from_config,
    )
    from voicerouter.base import ProviderSpec, _looks_like_missing_credentials

    factory = {"asr": asr_engine_from_config, "tts": tts_engine_from_config}[kind]
    fmt = audio_format or L16_24KHZ

    for i, raw in enumerate(load_inspector(kind).get("providers") or []):
        spec = ProviderSpec.from_dict(raw, i)
        extra = (overrides or {}).get(spec.name, {})
        try:
            engine = factory({"name": spec.name, **spec.config, **extra}, fmt, "en", None)
        except Exception as exc:  # noqa: BLE001 - vendor constructors vary widely
            if _looks_like_missing_credentials(exc):
                reason = str(exc).split("\n")[0]
                if "environment variable" in reason.lower():
                    reason = f"no {reason.rsplit(':', 1)[-1].strip()} — not configured here"
                yield Reachability(spec.label, spec.name, None, reason, skipped=True)
            else:
                yield Reachability(
                    spec.label, spec.name, None,
                    f"{type(exc).__name__}: {exc}", skipped=False,
                )
            continue
        yield Reachability(spec.label, spec.name, engine)


def main() -> int:
    _load_env()

    print(f"\n{DIM}Which vendors can this machine reach?{RESET}\n")
    available = {"asr": 0, "tts": 0}

    for kind in ("asr", "tts"):
        section = load_inspector(kind)
        print(f"{kind.upper()}  {DIM}(router: {section.get('name', '—')}){RESET}")
        for result in probe(kind):
            if result.reachable:
                available[kind] += 1
                print(f"  {GREEN}ok{RESET}    {result.label:<16} configured")
            elif result.skipped:
                # Report the vendor's own words. "No credentials" is wrong
                # for a local provider, which has none to be missing.
                print(f"  {YELLOW}skip{RESET}  {result.label:<16} {result.reason[:82]}")
            else:
                print(f"  {RED}error{RESET} {result.label:<16} {result.reason[:76]}")
        print()

    import yaml

    inspector = (yaml.safe_load((ROOT / "integrations.yml").read_text())
                 .get("channels", {}).get("inspector", {}))

    for kind in ("asr", "tts"):
        if available[kind] == 0:
            print(f"{RED}No usable {kind.upper()} provider — a call cannot start.{RESET}")
            return 1
        if available[kind] == 1:
            print(f"{YELLOW}Only one {kind.upper()} provider is configured — "
                  f"there is nothing to fail over to.{RESET}")
    print(f"{GREEN}Routing is live: {available['asr']} ASR, {available['tts']} TTS.{RESET}\n")

    _print_shelf(inspector)
    return 0


def _print_shelf(inspector: dict) -> None:
    """Enumerate catalogued adapters this config does not use — the CATALOGUE's
    stated purpose. Data only: nothing here imports a vendor or its SDK."""
    from voicerouter.providers import CATALOGUE

    configured = {
        str(raw.get("name", ""))
        for kind in ("asr", "tts")
        for raw in ((inspector.get(kind) or {}).get("providers") or [])
        if isinstance(raw, dict)
    }
    shelf = [e for e in CATALOGUE if e.dotted_path not in configured]
    if not shelf:
        return
    print(f"{DIM}Also on the shelf — catalogued adapters this config does not use.")
    print(f"Add one as a provider entry in integrations.yml to route through it:{RESET}")
    for e in shelf:
        live = "verified live" if e.verified_live else "unverified   "
        print(f"  {e.kind}  {e.dotted_path:<48} {DIM}{e.env_var:<24} "
              f"{live}  {e.note}{RESET}")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
