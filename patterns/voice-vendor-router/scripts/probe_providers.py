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
from pathlib import Path

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


def main() -> int:
    _load_env()
    import yaml
    from rasa.core.channels.voice_stream.audio_bytes import L16_24KHZ
    from rasa.core.channels.voice_stream.voice_channel import (
        asr_engine_from_config,
        tts_engine_from_config,
    )
    from voicerouter.base import ProviderSpec, _looks_like_missing_credentials

    inspector = (yaml.safe_load((ROOT / "integrations.yml").read_text())
                 .get("channels", {}).get("inspector", {}))

    print(f"\n{DIM}Which vendors can this machine reach?{RESET}\n")
    available = {"asr": 0, "tts": 0}

    for kind, factory in (("asr", asr_engine_from_config), ("tts", tts_engine_from_config)):
        section = inspector.get(kind) or {}
        print(f"{kind.upper()}  {DIM}(router: {section.get('name', '—')}){RESET}")
        for i, raw in enumerate(section.get("providers") or []):
            spec = ProviderSpec.from_dict(raw, i)
            try:
                factory({"name": spec.name, **spec.config}, L16_24KHZ, "en", None)
            except Exception as exc:  # noqa: BLE001
                if _looks_like_missing_credentials(exc):
                    # Report the vendor's own words. "No credentials" is wrong
                    # for a local provider, which has none to be missing.
                    reason = str(exc).split("\n")[0]
                    if "environment variable" in reason.lower():
                        reason = f"no {reason.rsplit(':', 1)[-1].strip()} — not configured here"
                    print(f"  {YELLOW}skip{RESET}  {spec.label:<16} {reason[:82]}")
                else:
                    print(f"  {RED}error{RESET} {spec.label:<16} {type(exc).__name__}: {str(exc)[:70]}")
                continue
            available[kind] += 1
            print(f"  {GREEN}ok{RESET}    {spec.label:<16} configured")
        print()

    for kind in ("asr", "tts"):
        if available[kind] == 0:
            print(f"{RED}No usable {kind.upper()} provider — a call cannot start.{RESET}")
            return 1
        if available[kind] == 1:
            print(f"{YELLOW}Only one {kind.upper()} provider is configured — "
                  f"there is nothing to fail over to.{RESET}")
    print(f"{GREEN}Routing is live: {available['asr']} ASR, {available['tts']} TTS.{RESET}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
