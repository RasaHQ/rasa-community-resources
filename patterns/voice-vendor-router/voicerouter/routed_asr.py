"""An ASR engine that is really N ASR engines with a failover policy.

    asr:
      name: voicerouter.RoutedASR
      providers:
        - name: deepgram
          language_map: { en: { model: flux-general-en } }
        - name: engines.speechmatics.SpeechmaticsASR
          language_map: { en: { language: en } }

Why this exists: without it, an ASR failure ends the transcript stream at
`logger.warning` and the agent simply stops hearing. The call stays open. The
caller keeps talking to something that has gone deaf.

Honest limit: audio already sent to a provider that then dies is gone. Speech
is not replayable — there is no buffer to hand to the next vendor, and inventing
one would mean holding raw call audio in memory for every session. The router
reconnects to a healthy provider and resumes with the *next* audio, which costs
a few hundred milliseconds of speech, and says so in the log rather than
pretending the turn was clean.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, List, Optional

import structlog
from rasa.core.channels.voice_stream.asr.asr_event import ASREvent
from rasa.core.channels.voice_stream.audio_bytes import AudioFormat, RasaAudioBytes

from voicerouter.base import (
    BuiltProvider,
    ProviderSpec,
    RouterPolicy,
    build_providers,
)
from voicerouter.health import HealthRegistry, shared_registry
from voicerouter.metrics import shared_metrics

logger = structlog.get_logger(__name__)


class RoutedASR:
    """Listens through the first healthy provider, and keeps listening."""

    def __init__(
        self,
        providers: List[BuiltProvider],
        policy: RouterPolicy,
        skipped_labels: Optional[List[str]] = None,
    ) -> None:
        self._providers = providers
        self._policy = policy
        # Process-scoped for the same reason as the TTS side: Rasa builds
        # engines per call, so call-scoped health is forgotten at every hangup.
        self._health = (
            shared_registry("asr", policy.cooldown_seconds, policy.failure_threshold)
            if policy.health_scope == "process"
            else HealthRegistry(
                cooldown_seconds=policy.cooldown_seconds,
                failure_threshold=policy.failure_threshold,
            )
        )
        self._metrics = shared_metrics("asr")
        self._active_index = 0
        self._connected: set[int] = set()
        logger.info(
            "voicerouter.asr.ready",
            providers=[p.spec.label for p in providers],
            skipped=skipped_labels or [],
        )

    @classmethod
    def from_config_dict(
        cls,
        config: Any,
        format: AudioFormat,
        rasa_language: str,
        additional_languages: Optional[List[str]] = None,
    ) -> "RoutedASR":
        from rasa.core.channels.voice_stream.voice_channel import asr_engine_from_config

        config = dict(config or {})
        raw_providers = config.pop("providers", None)
        if not raw_providers:
            raise ValueError(
                "voicerouter.RoutedASR needs a 'providers:' list. Each entry is "
                "an ordinary Rasa ASR config — a built-in name such as "
                "'deepgram' or 'azure', or a dotted path to a custom engine."
            )
        policy = RouterPolicy.from_dict(config.pop("policy", None))
        if config:
            raise ValueError(
                f"unexpected key(s) for RoutedASR: {', '.join(sorted(config))}. "
                f"Per-vendor settings belong inside their provider entry."
            )

        specs = [ProviderSpec.from_dict(raw, i) for i, raw in enumerate(raw_providers)]
        result = build_providers(
            specs,
            asr_engine_from_config,
            (format, rasa_language, additional_languages),
            policy,
            kind="asr",
        )
        return cls(result.built, policy, [s.spec.label for s in result.skipped])

    @classmethod
    def name(cls) -> str:
        return "voicerouter"

    @property
    def current_language_config(self) -> Any:
        return self._active.engine.current_language_config

    @property
    def active_provider(self) -> str:
        return self._active.spec.label

    def health_snapshot(self) -> list[dict]:
        return self._health.snapshot()

    def metrics_snapshot(self) -> list[dict]:
        return self._metrics.snapshot()

    @property
    def _active(self) -> BuiltProvider:
        return self._providers[self._active_index]

    def _candidates(self) -> list[int]:
        """Healthy providers first, then ones merely cooling down.

        Cooling-down providers stay on the list on purpose: a vendor that was
        rate-limited ten seconds ago is still a better bet than a deaf agent.

        Providers *disabled* by a permanent failure are excluded outright. A
        rejected key fails identically every time, so trying one does not buy a
        chance of hearing the caller — it only delays the provider that might.
        """
        healthy, cooling = [], []
        for i, provider in enumerate(self._providers):
            health = self._health.get(provider.spec.label)
            if health.disabled:
                continue
            (healthy if health.is_available() else cooling).append(i)
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

    # ---- lifecycle ----------------------------------------------------------

    async def connect(self) -> None:
        last_error: Optional[BaseException] = None
        for index in self._candidates():
            provider = self._providers[index]
            try:
                await provider.engine.connect()
            except Exception as exc:  # noqa: BLE001
                verdict = self._health.get(provider.spec.label).record_failure(exc)
                self._metrics.record_failure(provider.spec.label, verdict.kind.value)
                logger.warning(
                    "voicerouter.asr.connect_failed",
                    provider=provider.spec.label,
                    error=str(exc),
                    verdict=str(verdict),
                )
                last_error = exc
                continue
            previous = (
                self._providers[self._active_index].spec.label
                if self._active_index != index else None
            )
            self._active_index = index
            self._connected.add(index)
            self._health.get(provider.spec.label).record_success()
            self._metrics.record_success(provider.spec.label)
            if previous and previous != provider.spec.label:
                self._metrics.record_failover(
                    previous, provider.spec.label, "connected after failover"
                )
            logger.info("voicerouter.asr.connected", provider=provider.spec.label)
            return
        raise ConnectionError(
            f"{self._exhausted_message('ASR')}. Last error: {last_error}"
        )

    async def close_connection(self) -> None:
        for index in list(self._connected):
            try:
                await self._providers[index].engine.close_connection()
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "voicerouter.asr.close_failed",
                    provider=self._providers[index].spec.label,
                    error=str(exc),
                )
        self._connected.clear()

    # ---- listening ----------------------------------------------------------

    async def send_audio_chunks(self, chunk: RasaAudioBytes) -> None:
        """Forward audio to the active provider.

        Deliberately does not fail over here. The base engines already drop a
        chunk silently when their socket is closed, and a per-chunk failover
        would thrash providers on a single dropped packet. Recovery belongs to
        the event loop below, which knows whether the stream is really dead.
        """
        await self._active.engine.send_audio_chunks(chunk)

    async def signal_audio_done(self) -> None:
        await self._active.engine.signal_audio_done()

    async def send_keep_alive(self) -> None:
        try:
            await self._active.engine.send_keep_alive()
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "voicerouter.asr.keep_alive_failed",
                provider=self._active.spec.label,
                error=str(exc),
            )

    async def stream_asr_events(self) -> AsyncIterator[ASREvent]:
        """Yield transcripts, moving provider if the stream dies.

        Rasa's own loop swallows a stream error at warning level and simply
        stops yielding, which is what makes the agent go deaf. Here the failure
        is a signal: mark the provider, connect the next one, keep going.
        """
        while True:
            provider = self._active
            health = self._health.get(provider.spec.label)
            try:
                async for event in provider.engine.stream_asr_events():
                    health.record_success()
                    yield event
                return  # clean end of stream: the call is over
            except Exception as exc:  # noqa: BLE001
                verdict = health.record_failure(exc)
                self._metrics.record_failure(provider.spec.label, verdict.kind.value)
                self._connected.discard(self._active_index)
                logger.warning(
                    "voicerouter.asr.stream_failed",
                    provider=provider.spec.label,
                    error=str(exc),
                    verdict=str(verdict),
                )

            remaining = [i for i in self._candidates() if i != self._active_index]
            if not remaining:
                logger.error(
                    "voicerouter.asr.exhausted",
                    note="no ASR provider left; the agent can no longer hear",
                )
                return

            try:
                await self.connect()
            except Exception as exc:  # noqa: BLE001
                logger.error("voicerouter.asr.reconnect_failed", error=str(exc))
                return
            logger.info(
                "voicerouter.asr.resumed",
                provider=self._active.spec.label,
                note="audio sent during the failure was not transcribed",
            )

    async def set_language(self, rasa_language: str) -> Any:
        results = []
        for index, provider in enumerate(self._providers):
            try:
                results.append(await provider.engine.set_language(rasa_language))
            except Exception as exc:  # noqa: BLE001
                self._health.get(provider.spec.label).record_failure(exc)
                self._connected.discard(index)
                logger.warning(
                    "voicerouter.asr.set_language_failed",
                    provider=provider.spec.label,
                    error=str(exc),
                )
                results.append(False)
        return any(bool(r) for r in results)
