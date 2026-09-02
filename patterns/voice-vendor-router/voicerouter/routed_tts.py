"""A TTS engine that is really N TTS engines with a failover policy.

Configured like any other engine, because it is one:

    tts:
      name: voicerouter.RoutedTTS
      policy:
        cooldown_seconds: 30
      providers:
        - name: rime
          language_map: { en: { voice: cove, language: eng } }
          model_id: mistv2
        - name: deepgram
          language_map: { en: { model: aura-2-andromeda-en } }

Why this exists: without it, a TTS failure is not a degradation. Rasa
substitutes generated silence and logs an error — the caller simply hears
nothing, and there is an upstream `TODO` on that line. One vendor blip kills
the call.

What this does not do: recover a stream that has already emitted audio. If a
provider dies halfway through a sentence, those bytes are already on the wire
and the sentence is lost. It is marked unhealthy so the *next* sentence comes
from someone else. Failing over mid-sentence would mean the caller hears the
first half twice, in two voices, which is worse than the sentence being cut.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, AsyncIterator, List, Optional

import structlog
from rasa.core.channels.voice_stream.audio_bytes import AudioFormat, RasaAudioBytes
from rasa.core.channels.voice_stream.tts.tts_engine import TTSEngine, TTSError

from voicerouter.base import (
    BuiltProvider,
    ProviderSpec,
    RouterPolicy,
    build_providers,
)
from voicerouter.failures import should_retry_same_provider
from voicerouter.health import HealthRegistry, shared_registry
from voicerouter.metrics import Stopwatch, shared_metrics
from voicerouter.utterance import UtterancePolicy

#: Longest we will make a caller wait in silence to keep the same voice. Beyond
#: this, a different voice sooner beats the right voice late — a vendor that
#: says "come back in seven seconds" is telling you to route around it.
MAX_SAME_PROVIDER_WAIT_S = 1.0

logger = structlog.get_logger(__name__)


class RoutedTTS:
    """Speaks through the first healthy provider, and keeps speaking.

    Not a `TTSEngine` subclass on purpose. The base class carries per-connection
    state — response runtimes, locks, a resolved config — that would have to be
    kept in step with whichever child is currently active. Rasa resolves engines
    by dotted path and never type-checks them, so satisfying the surface it
    actually calls is both sufficient and less fragile.

    The surface Rasa uses is asserted by a contract test, so a future release
    that starts calling something new fails loudly here rather than at 3am on a
    live call.
    """

    def __init__(
        self,
        providers: List[BuiltProvider],
        policy: RouterPolicy,
        skipped_labels: Optional[List[str]] = None,
        utterance_policy: Optional[UtterancePolicy] = None,
    ) -> None:
        self._utterance = utterance_policy or UtterancePolicy()
        self._providers = providers
        self._policy = policy
        # Process-scoped by default: Rasa builds engines per call, so a
        # registry owned by this object would forget everything at hangup and
        # make the next caller pay for the same discovery.
        self._health = (
            shared_registry("tts", policy.cooldown_seconds, policy.failure_threshold)
            if policy.health_scope == "process"
            else HealthRegistry(
                cooldown_seconds=policy.cooldown_seconds,
                failure_threshold=policy.failure_threshold,
            )
        )
        self._metrics = shared_metrics("tts")
        self._active_index = 0
        self._connected: set[int] = set()
        logger.info(
            "voicerouter.tts.ready",
            providers=[p.spec.label for p in providers],
            skipped=skipped_labels or [],
        )

    # ---- construction -------------------------------------------------------

    @classmethod
    def from_config_dict(
        cls,
        config: Any,
        format: AudioFormat,
        rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "RoutedTTS":
        from rasa.core.channels.voice_stream.voice_channel import tts_engine_from_config

        config = dict(config or {})
        raw_providers = config.pop("providers", None)
        if not raw_providers:
            raise ValueError(
                "voicerouter.RoutedTTS needs a 'providers:' list. Each entry is "
                "an ordinary Rasa TTS config — a built-in name such as "
                "'deepgram' or 'rime', or a dotted path to a custom engine."
            )
        raw_policy = config.pop("policy", None) or {}
        utterance_policy = UtterancePolicy.from_dict(
            raw_policy.pop("utterance_classes", None)
        )
        policy = RouterPolicy.from_dict(raw_policy)
        if config:
            raise ValueError(
                f"unexpected key(s) for RoutedTTS: {', '.join(sorted(config))}. "
                f"Per-vendor settings belong inside their provider entry."
            )

        specs = [ProviderSpec.from_dict(raw, i) for i, raw in enumerate(raw_providers)]
        result = build_providers(
            specs,
            tts_engine_from_config,
            (format, rasa_language, additional_languages),
            policy,
            kind="tts",
        )
        return cls(
            result.built, policy,
            [s.spec.label for s in result.skipped],
            utterance_policy=utterance_policy,
        )

    @classmethod
    def name(cls) -> str:
        return "voicerouter"

    # ---- what tracing reads -------------------------------------------------

    @property
    def current_language_config(self) -> Any:
        return self._active.engine.current_language_config

    @property
    def active_provider(self) -> str:
        """Label of the provider currently serving. Useful in logs and tests."""
        return self._active.spec.label

    def health_snapshot(self) -> list[dict]:
        return self._health.snapshot()

    def metrics_snapshot(self) -> list[dict]:
        """Per-provider attempts, successes, failures by class and p95 latency."""
        return self._metrics.snapshot()

    # ---- provider selection -------------------------------------------------

    @property
    def _active(self) -> BuiltProvider:
        return self._providers[self._active_index]

    def _candidates_for(self, text: str) -> list[int]:
        """Candidates, with this utterance's preferred providers moved to front.

        Preference is a reordering, never a restriction: if the cheap voice for
        filler is down, the caller still hears the filler in the expensive one
        rather than hearing nothing.
        """
        order = self._candidates()
        prefer = self._utterance.preferred(text)
        if not prefer:
            return order
        rank = {label: i for i, label in enumerate(prefer)}
        return sorted(
            order,
            key=lambda i: (
                rank.get(self._providers[i].spec.label, len(rank)),
                order.index(i),
            ),
        )

    def _candidates(self) -> list[int]:
        """Healthy providers first, then ones merely cooling down.

        Cooling-down providers stay on the list on purpose: a vendor that was
        rate-limited ten seconds ago is still a better bet than silence, so if
        every circuit is open the router tries anyway rather than giving up.

        Providers *disabled* by a permanent failure are excluded outright. A
        rejected key or a malformed request fails identically every time, so
        trying one does not buy a chance of audio — it only spends the caller's
        patience before the next provider gets its turn.
        """
        healthy, cooling = [], []
        for i, provider in enumerate(self._providers):
            health = self._health.get(provider.spec.label)
            if health.disabled:
                continue
            (healthy if health.is_available() else cooling).append(i)

        if self._policy.selection == "latency":
            # Order by measured time-to-first-audio, which is the number that
            # decides whether the agent feels alive. Providers without enough
            # samples keep their configured position rather than being ranked
            # on one lucky or unlucky call.
            def key(i: int) -> tuple:
                p95 = self._metrics.stats(self._providers[i].spec.label).p95_first_audio_ms
                return (0, p95) if p95 is not None else (1, float(i))

            healthy.sort(key=key)

            # Occasionally try the runner-up, so its measurement does not go
            # stale and the router can notice it becoming the better choice.
            if (
                self._policy.explore_rate > 0
                and len(healthy) > 1
                and random.random() < self._policy.explore_rate
            ):
                healthy[0], healthy[1] = healthy[1], healthy[0]
                logger.debug(
                    "voicerouter.tts.exploring",
                    provider=self._providers[healthy[0]].spec.label,
                )
        return healthy + cooling

    def _exhausted_message(self, what: str) -> str:
        """Say which providers are out and why, not just that none are left."""
        parts = []
        for provider in self._providers:
            h = self._health.get(provider.spec.label)
            kind = h.last_verdict.kind.value if h.last_verdict else "unused"
            if h.disabled:
                parts.append(f"{provider.spec.label}: disabled ({kind})")
            elif h.opened_at is not None:
                parts.append(f"{provider.spec.label}: {kind}, retry in {h.reopens_in:.0f}s")
            else:
                parts.append(f"{provider.spec.label}: {kind}")
        return f"voicerouter: no {what} provider available — " + "; ".join(parts)

    async def _ensure_connected(self, index: int) -> None:
        if index in self._connected:
            return
        await self._providers[index].engine.connect()
        self._connected.add(index)

    # ---- lifecycle ----------------------------------------------------------

    async def connect(self, config: Optional[Any] = None) -> None:
        """Connect the first provider that will have us.

        Only one is connected up front. Opening five vendor websockets for a
        call that will use one is latency and quota spent on nothing; the rest
        connect if and when they are needed.
        """
        last_error: Optional[BaseException] = None
        for index in self._candidates():
            provider = self._providers[index]
            try:
                await self._ensure_connected(index)
            except Exception as exc:  # noqa: BLE001 - vendor clients vary
                verdict = self._health.get(provider.spec.label).record_failure(exc)
                logger.warning(
                    "voicerouter.tts.connect_failed",
                    provider=provider.spec.label,
                    error=str(exc),
                    verdict=str(verdict),
                )
                last_error = exc
                continue
            self._active_index = index
            self._health.get(provider.spec.label).record_success()
            logger.info("voicerouter.tts.connected", provider=provider.spec.label)
            return
        raise TTSError(f"{self._exhausted_message('TTS')}. Last error: {last_error}")

    async def close_connection(self) -> None:
        for index in list(self._connected):
            try:
                await self._providers[index].engine.close_connection()
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "voicerouter.tts.close_failed",
                    provider=self._providers[index].spec.label,
                    error=str(exc),
                )
        self._connected.clear()

    # ---- speaking -----------------------------------------------------------

    async def synthesize(
        self, text: str, config: Optional[Any] = None
    ) -> AsyncIterator[RasaAudioBytes]:
        """Yield audio, moving to another provider if one fails to start.

        Failover happens before the first byte. Once audio is flowing the
        provider owns the sentence; a mid-stream death is recorded and ends the
        sentence rather than restarting it in a different voice.
        """
        attempts = 0
        last_error: Optional[BaseException] = None
        previous_label: Optional[str] = None

        for index in self._candidates_for(text):
            provider = self._providers[index]
            health = self._health.get(provider.spec.label)
            label = provider.spec.label
            tries_here = 0

            while True:
                attempts += 1
                tries_here += 1
                emitted = False
                self._metrics.record_attempt(label)
                watch = Stopwatch()
                try:
                    await self._ensure_connected(index)
                    async for chunk in provider.engine.synthesize(text):
                        if not emitted:
                            # First byte is the moment the provider has proven
                            # itself, and the latency worth recording.
                            emitted = True
                            self._active_index = index
                            health.record_success()
                            self._metrics.record_success(label, watch.ms)
                            if previous_label and previous_label != label:
                                self._metrics.record_failover(
                                    previous_label, label, "served after failover"
                                )
                        yield chunk
                except Exception as exc:  # noqa: BLE001 - any vendor failure routes
                    verdict = health.record_failure(exc)
                    self._metrics.record_failure(label, verdict.kind.value)
                    self._connected.discard(index)
                    last_error = exc

                    if emitted:
                        logger.error(
                            "voicerouter.tts.failed_mid_stream",
                            provider=label, error=str(exc), verdict=str(verdict),
                            note="sentence truncated; provider marked unhealthy",
                        )
                        return

                    # Keeping the caller's voice is worth a retry when the
                    # failure says "not right now" rather than "not ever" — and
                    # only while the wait stays shorter than the silence a
                    # voice change would cost.
                    wait = (
                        verdict.retry_after
                        if verdict.retry_after is not None
                        else self._policy.retry_backoff_ms / 1000.0
                    )
                    if (
                        should_retry_same_provider(verdict)
                        and tries_here <= self._policy.same_provider_retries
                        and wait <= MAX_SAME_PROVIDER_WAIT_S
                    ):
                        logger.info(
                            "voicerouter.tts.retrying_same_provider",
                            provider=label, verdict=str(verdict),
                            wait_s=round(wait, 3),
                            note="keeping the caller's voice",
                        )
                        await asyncio.sleep(wait)
                        continue

                    logger.warning(
                        "voicerouter.tts.failing_over",
                        from_provider=label, verdict=str(verdict), attempt=attempts,
                        voice_changes=True,
                    )
                    previous_label = label
                    break
                else:
                    return

        raise TTSError(
            f"{self._exhausted_message('TTS')} — {attempts} attempted for this "
            f"utterance. Last error: {last_error}"
        )

    async def start_response(self, *args: Any, **kwargs: Any) -> Any:
        return await self._active.engine.start_response(*args, **kwargs)

    def interrupt(self) -> Any:
        return self._active.engine.interrupt()

    async def signal_interrupt(self) -> None:
        await self._active.engine.signal_interrupt()

    async def set_language(self, rasa_language: str) -> bool:
        """Switch language on every provider, not just the active one.

        A provider that is idle now may serve the next sentence, and it must not
        still be speaking the previous language when it does.
        """
        results = []
        for index, provider in enumerate(self._providers):
            try:
                results.append(bool(await provider.engine.set_language(rasa_language)))
            except Exception as exc:  # noqa: BLE001
                self._health.get(provider.spec.label).record_failure(exc)
                self._connected.discard(index)
                logger.warning(
                    "voicerouter.tts.set_language_failed",
                    provider=provider.spec.label,
                    language=rasa_language,
                    error=str(exc),
                )
                results.append(False)
        return any(results)
