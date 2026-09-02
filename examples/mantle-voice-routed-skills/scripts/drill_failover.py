#!/usr/bin/env python3
"""Watch Vela lose a vendor mid-call, without losing one.

`make inspect` proves the routed stack speaks. It cannot show you the part you
are actually buying — what the caller hears at the moment Rime runs out of
credits — because you would have to run a vendor out of credits to see it.

This drill reads *this project's* configuration, builds the real router from it,
and then fails vendors on a schedule. Provider order, policy, cooldowns,
utterance classes and the voice-change rule are the ones in the file. Only the
vendor call itself is stubbed, so no key and no network are needed.

    make drill                       # every scenario, against integrations.yml
    make drill SCENARIO=credits      # just one
    make drill STACK=cost-tiered     # against a stack you have not switched to

What it cannot tell you: whether Deepgram actually sounds acceptable in Vela's
place. Run `make inspect` for that; it is a listening decision, not a logic one.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Iterator
from unittest import mock

import yaml

PROJECT = Path(__file__).resolve().parent.parent
# The router is an installed dependency (see pyproject.toml). Falling back to
# the in-repo path keeps the drill runnable straight after a clone, before sync.
try:
    import voicerouter  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - convenience path
    sys.path.insert(0, str(PROJECT.parent.parent / "patterns" / "voice-vendor-router"))

from voicerouter.base import BuiltProvider, ProviderSpec, RouterPolicy  # noqa: E402
from voicerouter.health import reset_shared_registries  # noqa: E402
from voicerouter.metrics import reset_shared_metrics  # noqa: E402
from voicerouter.routed_tts import RoutedTTS  # noqa: E402
from voicerouter.utterance import UtterancePolicy  # noqa: E402

# A real banking turn, in the order a caller would hear it.
SCRIPT = [
    "Hi, you're through to Northwind. This is Vela.",
    "One moment.",
    "Your current balance is two thousand four hundred fifty dollars.",
    "Transferring four hundred pounds to Sam Rivera - shall I go ahead?",
    "Okay, got it.",
    "That's done. Is there anything else?",
]


def http_error(status: int, message: str = "", headers: dict | None = None):
    """An aiohttp error shaped like the ones vendors actually raise."""
    import aiohttp

    return aiohttp.ClientResponseError(
        mock.Mock(real_url="https://vendor.example/v1"),
        (),
        status=status,
        message=message,
        headers=headers or {},
    )


# Each scenario says what the *first* provider in the chain does. The rest of the
# chain stays healthy — the question being asked is what the caller hears, not
# how many vendors can break at once.
#
# A fault is called once per attempt and returns the exception to raise, or None
# to succeed. Being per *attempt* rather than per turn is what lets `rate-limit`
# model the case that matters: a blip that clears when the router tries the same
# provider again, so nobody has to change voice over it.


def once(exc):
    """Fail the first attempt, then behave. A transient error, transiently."""
    fired = []

    def fault(turn: int, attempt: int):
        if turn == 3 and not fired:
            fired.append(True)
            return exc
        return None

    return fault


def _from(turn_from: int, exc):
    return lambda turn, attempt: exc if turn >= turn_from else None


SCENARIOS = {
    "credits": (
        "Primary runs out of credits (HTTP 402) from turn 3",
        lambda: _from(3, http_error(402, "Payment Required")),
    ),
    "unreachable": (
        "Primary's API stops answering from turn 3",
        lambda: _from(3, ConnectionRefusedError("connection refused")),
    ),
    "rate-limit": (
        "Primary rate-limits turn 3 once (HTTP 429), then recovers",
        lambda: once(http_error(429, "Too Many Requests")),
    ),
    "bad-key": (
        "Primary's key is rejected (HTTP 401) from turn 1",
        lambda: _from(1, http_error(401, "Unauthorized")),
    ),
}


class FakeEngine:
    """Speaks, or raises whatever the scenario says it should."""

    def __init__(self, label: str, fault=None) -> None:
        self.label = label
        self._fault = fault or (lambda turn, attempt: None)
        self.turn = 0
        self.attempt = 0
        self.current_language_config = {}

    async def connect(self) -> None:
        exc = self._fault(self.turn, self.attempt + 1)
        # A connection error is how an unreachable API presents itself first.
        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            self.attempt += 1
            raise exc

    async def close_connection(self) -> None:
        return None

    async def synthesize(self, text: str, config=None):
        self.attempt += 1
        exc = self._fault(self.turn, self.attempt)
        if exc is not None:
            raise exc
        yield b"\x00\x00" * 8
        return
        # noinspection PyUnreachableCode
        yield  # pragma: no cover - keeps this an async generator


def load_tts_config(stack: str | None) -> dict:
    path = PROJECT / "integrations.yml" if not stack else PROJECT / "stacks" / f"{stack}.yml"
    if not path.exists():
        raise SystemExit(f"no such stack: {path}")
    raw = yaml.safe_load(path.read_text())
    try:
        return raw["channels"]["inspector"]["tts"], path
    except (KeyError, TypeError):
        raise SystemExit(f"{path} has no channels.inspector.tts block")


def build_router(cfg: dict, fault) -> RoutedTTS:
    """The real router over stub engines, from the real configuration."""
    policy_raw = dict(cfg.get("policy") or {})
    utterance = UtterancePolicy.from_dict(policy_raw.pop("utterance_classes", None))
    policy = RouterPolicy.from_dict(policy_raw)

    specs = [ProviderSpec.from_dict(raw, i) for i, raw in enumerate(cfg["providers"])]
    providers = [
        BuiltProvider(spec, FakeEngine(spec.label, fault if i == 0 else None))
        for i, spec in enumerate(specs)
    ]
    return RoutedTTS(providers, policy, [], utterance_policy=utterance)


async def run_scenario(name: str, cfg: dict) -> None:
    description, make_fault = SCENARIOS[name]
    reset_shared_registries()
    reset_shared_metrics()

    router = build_router(cfg, make_fault())
    primary = router._providers[0].spec.label
    print(f"\n\033[1m{name}\033[0m — {description}")
    print(f"  chain: {' > '.join(p.spec.label for p in router._providers)}")
    print()

    heard: str | None = None
    for turn, line in enumerate(SCRIPT, start=1):
        for provider in router._providers:
            provider.engine.turn = turn
            provider.engine.attempt = 0
        try:
            async for _ in router.synthesize(line):
                pass
            spoke = router.active_provider
        except Exception as exc:  # noqa: BLE001 - the drill reports, never dies
            print(f"  {turn}. SILENT — {type(exc).__name__}: {exc}")
            continue

        # Two very different things both look like "a different voice" from the
        # outside, and only one of them is a failure. Say which.
        change = ""
        if heard is not None and spoke != heard:
            klass = router._utterance.classify(line)
            deliberate = spoke in router._utterance.preferred(line)
            why = f"by utterance class '{klass}'" if deliberate else "failover"
            change = f"   <- {heard} -> {spoke}, {why}"
        heard = spoke
        print(f"  {turn}. [{spoke:<16}] {line}{change}")

    health = {h["provider"]: h for h in router.health_snapshot()}
    state = health.get(primary)
    if not state or not state["failures"]:
        print(f"\n  after the call, {primary}: healthy, {state['successes'] if state else 0} turns served")
    else:
        # reopens_in is None both for a circuit that will never reopen and for
        # one that already has, so the state is what distinguishes them.
        reopens = state["reopens_in"]
        if state["state"] == "disabled":
            when = "never tried again until restart"
        elif reopens is None:
            when = "already serving again"
        else:
            when = f"retried in {reopens}s"
        print(
            f"\n  after the call, {primary}: {state['state']}, "
            f"{state['failures']} failure(s), last was {state['last_failure_kind']}, {when}"
        )


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", choices=[*SCENARIOS, "all"], default="all")
    ap.add_argument("--stack", help="a file under stacks/, e.g. cost-tiered")
    args = ap.parse_args()

    cfg, path = load_tts_config(args.stack)
    print(f"Routing rules read from {path.relative_to(PROJECT.parent.parent)}")
    print("Vendor calls are stubbed — the routing decisions below are the real ones.")

    names = [*SCENARIOS] if args.scenario == "all" else [args.scenario]
    for name in names:
        await run_scenario(name, cfg)

    print(
        "\nThe rule being demonstrated: a rate limit is served by the same voice "
        "after a short\nwait, because a caller notices a new person more than a "
        "250 ms pause. Running out\nof credits, a rejected key, and an "
        "unreachable API are the three that change it."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
