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
from voicerouter.health import HealthRegistry

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
    ) -> None:
        self._providers = providers
        self._policy = policy
        self._health = HealthRegistry(
            cooldown_seconds=policy.cooldown_seconds,
            failure_threshold=policy.failure_threshold,
        )
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
        policy = RouterPolicy.from_dict(config.pop("policy", None))
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
        return cls(result.built, policy, [s.spec.label for s in result.skipped])

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

    # ---- provider selection -------------------------------------------------

    @property
    def _active(self) -> BuiltProvider:
        return self._providers[self._active_index]

    def _candidates(self) -> list[int]:
        """Healthy providers first, in configured order, then the rest.

        The unhealthy ones stay on the list deliberately: a provider in cooldown
        is still better than silence, so if every circuit is open the router
        tries anyway rather than giving up.
        """
        healthy, unhealthy = [], []
        for i, provider in enumerate(self._providers):
            target = healthy if self._health.get(provider.spec.label).is_available() else unhealthy
            target.append(i)
        return healthy + unhealthy

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
                self._health.get(provider.spec.label).record_failure(exc)
                logger.warning(
                    "voicerouter.tts.connect_failed",
                    provider=provider.spec.label,
                    error=str(exc),
                )
                last_error = exc
                continue
            self._active_index = index
            self._health.get(provider.spec.label).record_success()
            logger.info("voicerouter.tts.connected", provider=provider.spec.label)
            return
        raise TTSError(
            f"voicerouter: no TTS provider could connect. Last error: {last_error}"
        )

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

        for index in self._candidates():
            provider = self._providers[index]
            health = self._health.get(provider.spec.label)
            attempts += 1
            emitted = False
            try:
                await self._ensure_connected(index)
                stream = provider.engine.synthesize(text)
                async for chunk in stream:
                    if not emitted:
                        # First byte is the moment the provider has proven
                        # itself; only now is it safe to call this a success.
                        emitted = True
                        self._active_index = index
                        health.record_success()
                    yield chunk
            except Exception as exc:  # noqa: BLE001 - any vendor failure is a failover
                health.record_failure(exc)
                self._connected.discard(index)
                last_error = exc
                if emitted:
                    logger.error(
                        "voicerouter.tts.failed_mid_stream",
                        provider=provider.spec.label,
                        error=str(exc),
                        note="sentence truncated; provider marked unhealthy",
                    )
                    return
                logger.warning(
                    "voicerouter.tts.failing_over",
                    from_provider=provider.spec.label,
                    error=str(exc),
                    attempt=attempts,
                )
                continue
            return

        raise TTSError(
            f"voicerouter: every TTS provider failed for this utterance "
            f"({attempts} attempted). Last error: {last_error}"
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
