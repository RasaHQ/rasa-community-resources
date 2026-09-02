"""Per-provider health, so a dead vendor is tried once and then left alone.

A voice call cannot afford to rediscover that a provider is down on every
utterance. Each failure opens a circuit; the next attempt after it expires is a
probe, and one success closes it again.

How long the circuit stays open is not a constant — it comes from what the
failure *was*. A rate limit reopens in seconds, and in the vendor's own
Retry-After when it supplies one. Exhausted credits park the provider for
minutes. A rejected key or a malformed request never reopens at all, because no
amount of waiting fixes either. See `failures.py`.

Deliberately small: no background tasks, no metrics server, no persistence. The
state lives for the life of the call, which is the span that decides who speaks
the next sentence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from voicerouter.failures import Verdict, classify, cooldown_for, is_permanent


@dataclass
class ProviderHealth:
    """Circuit state for one provider."""

    name: str
    cooldown_seconds: float = 30.0
    failure_threshold: int = 1

    consecutive_failures: int = 0
    opened_at: float | None = None
    total_failures: int = 0
    total_successes: int = 0
    last_error: str | None = None
    #: Cooldown for the *current* open circuit, set by the last failure's class.
    current_cooldown: float = 30.0
    #: True once a failure arrives that waiting cannot fix.
    disabled: bool = False
    last_verdict: Optional[Verdict] = None

    def is_available(self, now: float | None = None) -> bool:
        """True when this provider may be tried.

        An open circuit becomes available again once its cooldown elapses — the
        attempt after that is a probe, not a guarantee. A provider disabled by a
        permanent failure never becomes available on its own.
        """
        if self.disabled:
            return False
        if self.opened_at is None:
            return True
        now = time.monotonic() if now is None else now
        return (now - self.opened_at) >= self.current_cooldown

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.opened_at = None
        self.total_successes += 1
        # A success does not clear `disabled`: a rejected key is not fixed by a
        # later request succeeding, because a later request cannot happen.

    def record_failure(self, error: BaseException) -> Verdict:
        """Record a failure and return what the router should conclude from it."""
        verdict = classify(error)
        self.consecutive_failures += 1
        self.total_failures += 1
        self.last_error = f"{type(error).__name__}: {error}"
        self.last_verdict = verdict

        if is_permanent(verdict):
            # No threshold for these. One 401 is enough to know.
            self.disabled = True
            self.opened_at = time.monotonic()
            self.current_cooldown = float("inf")
            return verdict

        if self.consecutive_failures >= self.failure_threshold:
            self.opened_at = time.monotonic()
            self.current_cooldown = cooldown_for(verdict, self.cooldown_seconds)
        return verdict

    @property
    def state(self) -> str:
        if self.disabled:
            return "disabled"
        if self.opened_at is None:
            return "closed"
        return "half-open" if self.is_available() else "open"

    @property
    def reopens_in(self) -> float:
        """Seconds until this provider may be tried again."""
        if self.disabled:
            return float("inf")
        if self.opened_at is None:
            return 0.0
        return max(0.0, self.current_cooldown - (time.monotonic() - self.opened_at))


@dataclass
class HealthRegistry:
    """Health for every provider in one router."""

    cooldown_seconds: float = 30.0
    failure_threshold: int = 1
    _by_name: dict[str, ProviderHealth] = field(default_factory=dict)

    def get(self, name: str) -> ProviderHealth:
        if name not in self._by_name:
            self._by_name[name] = ProviderHealth(
                name=name,
                cooldown_seconds=self.cooldown_seconds,
                failure_threshold=self.failure_threshold,
            )
        return self._by_name[name]

    def snapshot(self) -> list[dict]:
        """Current state of every provider, for logging or a status endpoint."""
        return [
            {
                "provider": h.name,
                "state": h.state,
                "failures": h.total_failures,
                "successes": h.total_successes,
                "last_error": h.last_error,
                "last_failure_kind": (
                    h.last_verdict.kind.value if h.last_verdict else None
                ),
                "reopens_in": (
                    None if h.reopens_in in (0.0, float("inf")) else round(h.reopens_in, 1)
                ),
            }
            for h in self._by_name.values()
        ]


# ------------------------------------------------------------------------------
# Health that outlives a call
# ------------------------------------------------------------------------------
# Rasa builds ASR and TTS engines *per call* — `_get_asr_and_tts_engines` runs
# inside "run streaming tasks and teardown for one call". A registry owned by
# the engine therefore dies at hangup, and the next caller rediscovers the same
# dead vendor from scratch. At any real call volume that means paying the
# failover cost on the first utterance of every conversation, forever.
#
# So the default registry is process-scoped: what one call learns, the next one
# starts with. Circuits opened by a rejected key stay open; a quota window
# parked for fifteen minutes stays parked across the calls that arrive during
# it.
#
# Deliberately in-process only. A shared store (Redis) would extend this across
# workers and is the obvious next step, but it introduces a dependency and a
# failure mode of its own, and process scope already removes the large majority
# of the waste.

_SHARED: dict[str, "HealthRegistry"] = {}


def shared_registry(
    kind: str, cooldown_seconds: float = 30.0, failure_threshold: int = 1
) -> "HealthRegistry":
    """The process-wide registry for `kind` ("tts" / "asr").

    The first caller's cooldown and threshold win; later callers reuse the
    existing registry rather than replacing it, because replacing it would
    discard exactly the history this exists to keep.
    """
    if kind not in _SHARED:
        _SHARED[kind] = HealthRegistry(
            cooldown_seconds=cooldown_seconds, failure_threshold=failure_threshold
        )
    return _SHARED[kind]


def reset_shared_registries() -> None:
    """Forget everything. For tests, and for an operator escape hatch.

    A provider disabled by a rejected key stays disabled for the life of the
    process, which is right until someone fixes the key — at which point there
    has to be a way to say so without a restart.
    """
    _SHARED.clear()
