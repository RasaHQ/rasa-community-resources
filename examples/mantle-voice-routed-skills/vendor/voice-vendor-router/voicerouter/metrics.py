"""What the router knows about how its providers are actually performing.

Two jobs, and they are the same data:

* **Routing.** Preferring a provider because it is first in a list is a
  configuration decision, not a routing one. Time-to-first-audio is the number
  that decides whether a voice agent feels alive, so it is what `selection:
  latency` sorts on.
* **Operating.** Rasa already traces voice calls; what it cannot tell you is
  which vendor served them, how often the router failed over, or why. These
  emit as OpenTelemetry metrics through whatever exporter the deployment has
  already configured in `endpoints.yml`, and fall back to no-ops when tracing
  is not set up.

Latency is kept as a small rolling window per provider rather than an average
over all time: a vendor that was slow an hour ago should not be punished for it
now, and a vendor degrading right now should be noticed within a few turns.
"""

from __future__ import annotations

import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

#: Samples kept per provider. Small enough to react within a call, large enough
#: that one slow synthesis does not reorder the whole chain.
WINDOW = 20
#: Below this many samples a provider's latency is not trusted for ordering —
#: otherwise the first provider to be measured wins by default.
MIN_SAMPLES = 3


@dataclass
class ProviderStats:
    label: str
    attempts: int = 0
    successes: int = 0
    failures_by_kind: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    first_audio_ms: Deque[float] = field(default_factory=lambda: deque(maxlen=WINDOW))

    @property
    def p95_first_audio_ms(self) -> Optional[float]:
        """Rolling p95, or None while there is not enough evidence."""
        if len(self.first_audio_ms) < MIN_SAMPLES:
            return None
        ordered = sorted(self.first_audio_ms)
        # quantiles() needs n>=2; with a short window this is the honest p95.
        index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
        return ordered[index]

    @property
    def median_first_audio_ms(self) -> Optional[float]:
        if not self.first_audio_ms:
            return None
        return statistics.median(self.first_audio_ms)


class RouterMetrics:
    """Per-provider counters and latency, plus OTel emission."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._stats: Dict[str, ProviderStats] = {}
        self._otel = _OtelSink(kind)

    def stats(self, label: str) -> ProviderStats:
        if label not in self._stats:
            self._stats[label] = ProviderStats(label=label)
        return self._stats[label]

    def record_attempt(self, label: str) -> None:
        self.stats(label).attempts += 1

    def record_success(self, label: str, first_audio_ms: Optional[float] = None) -> None:
        s = self.stats(label)
        s.successes += 1
        if first_audio_ms is not None:
            s.first_audio_ms.append(first_audio_ms)
            self._otel.record_latency(label, first_audio_ms)
        self._otel.record_success(label)

    def record_failure(self, label: str, kind: str) -> None:
        self.stats(label).failures_by_kind[kind] += 1
        self._otel.record_failure(label, kind)

    def record_failover(self, from_label: str, to_label: str, reason: str) -> None:
        self._otel.record_failover(from_label, to_label, reason)
        logger.info(
            f"voicerouter.{self.kind}.failover",
            from_provider=from_label, to_provider=to_label, reason=reason,
        )

    def snapshot(self) -> list[dict]:
        return [
            {
                "provider": s.label,
                "attempts": s.attempts,
                "successes": s.successes,
                "failures": dict(s.failures_by_kind),
                "p95_first_audio_ms": (
                    round(s.p95_first_audio_ms, 1) if s.p95_first_audio_ms else None
                ),
                "samples": len(s.first_audio_ms),
            }
            for s in self._stats.values()
        ]


class _OtelSink:
    """Emit to OpenTelemetry when it is configured, and shut up when it is not.

    Rasa depends on opentelemetry, so the import is safe; whether anything is
    *exported* depends on the deployment's tracing config. Creating instruments
    against a no-op meter is harmless, which is what keeps this branch-free at
    the call sites.
    """

    def __init__(self, kind: str) -> None:
        self.enabled = False
        try:
            from opentelemetry import metrics as otel_metrics

            meter = otel_metrics.get_meter("voicerouter")
            self._success = meter.create_counter(
                f"voicerouter.{kind}.success", unit="1",
                description="Utterances served, by provider",
            )
            self._failure = meter.create_counter(
                f"voicerouter.{kind}.failure", unit="1",
                description="Provider failures, by provider and failure class",
            )
            self._failover = meter.create_counter(
                f"voicerouter.{kind}.failover", unit="1",
                description="Times the router moved to a different provider",
            )
            self._latency = meter.create_histogram(
                f"voicerouter.{kind}.first_audio", unit="ms",
                description="Time to first audio, by provider",
            )
            self.enabled = True
        except Exception as exc:  # noqa: BLE001 - telemetry must never break a call
            logger.debug("voicerouter.otel_unavailable", error=str(exc))

    def record_success(self, label: str) -> None:
        if self.enabled:
            self._success.add(1, {"provider": label})

    def record_failure(self, label: str, kind: str) -> None:
        if self.enabled:
            self._failure.add(1, {"provider": label, "failure_kind": kind})

    def record_failover(self, from_label: str, to_label: str, reason: str) -> None:
        if self.enabled:
            self._failover.add(
                1, {"from": from_label, "to": to_label, "reason": reason}
            )

    def record_latency(self, label: str, ms: float) -> None:
        if self.enabled:
            self._latency.record(ms, {"provider": label})


_SHARED_METRICS: Dict[str, RouterMetrics] = {}


def shared_metrics(kind: str) -> RouterMetrics:
    """Process-wide metrics, for the same reason health is process-wide.

    Latency learned on one call is exactly what should order providers on the
    next one.
    """
    if kind not in _SHARED_METRICS:
        _SHARED_METRICS[kind] = RouterMetrics(kind)
    return _SHARED_METRICS[kind]


def reset_shared_metrics() -> None:
    _SHARED_METRICS.clear()


class Stopwatch:
    """Milliseconds since construction. Used for time-to-first-audio."""

    def __init__(self) -> None:
        self._t0 = time.monotonic()

    @property
    def ms(self) -> float:
        return (time.monotonic() - self._t0) * 1000.0
