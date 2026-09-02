"""Per-provider health, so a dead vendor is tried once and then left alone.

A voice call cannot afford to rediscover that a provider is down on every
utterance. Each failure opens a circuit for a cooldown window; the next attempt
after that window is a probe, and one success closes it again.

Deliberately small: no background tasks, no metrics server, no persistence. The
state lives for the life of the call, which is the only span that matters for
deciding who speaks the next sentence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


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

    def is_available(self, now: float | None = None) -> bool:
        """True when this provider may be tried.

        An open circuit becomes available again once the cooldown elapses — the
        attempt after that is a probe, not a guarantee.
        """
        if self.opened_at is None:
            return True
        now = time.monotonic() if now is None else now
        return (now - self.opened_at) >= self.cooldown_seconds

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.opened_at = None
        self.total_successes += 1

    def record_failure(self, error: BaseException) -> None:
        self.consecutive_failures += 1
        self.total_failures += 1
        self.last_error = f"{type(error).__name__}: {error}"
        if self.consecutive_failures >= self.failure_threshold:
            self.opened_at = time.monotonic()

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "half-open" if self.is_available() else "open"


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
            }
            for h in self._by_name.values()
        ]
