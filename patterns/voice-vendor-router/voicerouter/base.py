"""Shared plumbing for the routed engines.

The router does not reimplement a single vendor. Each entry under `providers:`
is an ordinary Rasa engine config, handed to Rasa's own
`asr_engine_from_config` / `tts_engine_from_config`. That is the whole trick:

  * every engine Rasa ships works immediately — deepgram, azure, cartesia, rime
  * every engine Rasa adds later works with no change here
  * every custom engine works too, because those factories already accept a
    dotted path (`engines.speechmatics.SpeechmaticsASR`)

So "swap any vendor" is not a list of adapters this package has to keep up to
date. It is a property of delegating resolution to Rasa.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import structlog

logger = structlog.get_logger(__name__)

# Keys the router consumes; everything else in a provider entry is passed
# through to the underlying engine untouched.
_ROUTER_KEYS = frozenset({"name", "label"})


@dataclass
class ProviderSpec:
    """One entry from the `providers:` list."""

    name: str
    label: str
    config: dict[str, Any]

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int) -> "ProviderSpec":
        if "name" not in raw:
            raise ValueError(
                f"providers[{index}] has no 'name'. Each provider entry is an "
                f"ordinary Rasa engine config: a built-in name like 'deepgram', "
                f"or a dotted path to a custom engine class."
            )
        name = str(raw["name"])
        return cls(
            name=name,
            # A label keeps logs readable when the same vendor appears twice
            # with different voices or regions.
            label=str(raw.get("label", name)),
            config={k: v for k, v in raw.items() if k not in _ROUTER_KEYS},
        )


@dataclass
class RouterPolicy:
    """How the router behaves when a provider misbehaves."""

    cooldown_seconds: float = 30.0
    failure_threshold: int = 1
    # Providers whose credentials are absent are skipped rather than raising.
    # That is what lets one configuration name five vendors and run on whichever
    # keys this deployment actually has.
    skip_unconfigured: bool = True
    # "process" keeps what one call learned for the next one; "call" throws it
    # away at hangup, which is Rasa's own engine lifetime.
    health_scope: str = "process"
    # Retries on the *same* provider before considering a different voice, for
    # failures that do not justify one (rate limits, transient errors).
    same_provider_retries: int = 1
    # Pause before such a retry.
    retry_backoff_ms: int = 250
    # "order" follows the configured list; "latency" prefers the provider with
    # the best measured time-to-first-audio.
    selection: str = "order"
    # Fraction of utterances that deliberately try a provider other than the
    # best-ranked one, to keep its latency measurement fresh.
    #
    # Zero by default, and that default is a judgement rather than laziness:
    # exploring costs a real caller a possibly-worse voice on a real turn. With
    # it off, `selection: latency` learns only from providers it was forced to
    # use by a failover — which prevents flapping back to a slow primary, but
    # cannot discover that provider #2 was faster all along. Turn it up if you
    # would rather pay a little quality to find out.
    explore_rate: float = 0.0

    @classmethod
    def from_dict(cls, raw: Optional[dict[str, Any]]) -> "RouterPolicy":
        raw = raw or {}
        unknown = set(raw) - {
            "cooldown_seconds", "failure_threshold", "skip_unconfigured",
            "health_scope", "same_provider_retries", "retry_backoff_ms",
            "selection", "explore_rate",
        }
        if unknown:
            raise ValueError(
                f"unknown policy key(s): {', '.join(sorted(unknown))}. "
                f"Supported: cooldown_seconds, failure_threshold, skip_unconfigured."
            )
        health_scope = str(raw.get("health_scope", "process"))
        if health_scope not in ("process", "call"):
            raise ValueError(
                f"policy.health_scope must be 'process' or 'call', got "
                f"{health_scope!r}."
            )
        selection = str(raw.get("selection", "order"))
        if selection not in ("order", "latency"):
            raise ValueError(
                f"policy.selection must be 'order' or 'latency', got {selection!r}."
            )
        return cls(
            cooldown_seconds=float(raw.get("cooldown_seconds", 30.0)),
            failure_threshold=int(raw.get("failure_threshold", 1)),
            skip_unconfigured=bool(raw.get("skip_unconfigured", True)),
            health_scope=health_scope,
            same_provider_retries=int(raw.get("same_provider_retries", 1)),
            retry_backoff_ms=int(raw.get("retry_backoff_ms", 250)),
            selection=selection,
            explore_rate=float(raw.get("explore_rate", 0.0)),
        )


@dataclass
class BuiltProvider:
    """A provider spec that successfully produced an engine."""

    spec: ProviderSpec
    engine: Any


@dataclass
class SkippedProvider:
    """A provider that could not be built, and why."""

    spec: ProviderSpec
    reason: str


@dataclass
class BuildResult:
    built: list[BuiltProvider] = field(default_factory=list)
    skipped: list[SkippedProvider] = field(default_factory=list)


def build_providers(
    specs: list[ProviderSpec],
    factory: Callable[..., Any],
    factory_args: tuple,
    policy: RouterPolicy,
    kind: str,
) -> BuildResult:
    """Turn provider specs into engines via Rasa's own factory.

    A provider whose API key is absent raises at construction — Rasa validates
    `required_env_vars` in the engine constructor. With `skip_unconfigured`
    (the default) that is a skip and a log line, not a crash, so a configuration
    can name every vendor you might use and still boot on a laptop that has one
    key.
    """
    result = BuildResult()
    for spec in specs:
        try:
            engine = factory({"name": spec.name, **spec.config}, *factory_args)
        except Exception as exc:  # noqa: BLE001 - vendor constructors vary widely
            reason = f"{type(exc).__name__}: {exc}"
            if _looks_like_missing_credentials(exc) and policy.skip_unconfigured:
                logger.info(
                    f"voicerouter.{kind}.provider_skipped",
                    provider=spec.label,
                    reason="credentials not configured",
                    detail=reason,
                )
                result.skipped.append(SkippedProvider(spec, "credentials not configured"))
                continue
            if policy.skip_unconfigured:
                logger.warning(
                    f"voicerouter.{kind}.provider_unavailable",
                    provider=spec.label,
                    detail=reason,
                )
                result.skipped.append(SkippedProvider(spec, reason))
                continue
            raise
        result.built.append(BuiltProvider(spec, engine))

    if not result.built:
        detail = "; ".join(f"{s.spec.label}: {s.reason}" for s in result.skipped)
        raise ValueError(
            f"voicerouter: no usable {kind} provider. Every entry was skipped "
            f"({detail or 'none configured'}). Set at least one provider's API "
            f"key, or set policy.skip_unconfigured to false to see the original "
            f"error."
        )
    return result


def _looks_like_missing_credentials(exc: BaseException) -> bool:
    """Distinguish "no key" from "broken config".

    Rasa raises ProviderClientValidationError for a missing required env var,
    and engines that read os.environ directly raise KeyError. A local provider
    raises ModuleNotFoundError when its optional package is absent, and
    ValueError when its required files are not configured. All four mean the
    same thing to an operator: this vendor is not usable here.
    """
    if isinstance(exc, KeyError):
        return True
    if isinstance(exc, ModuleNotFoundError):
        # A provider whose optional package is not installed is unavailable in
        # exactly the way a provider without a key is: configured, not usable
        # here, and not a reason to fail the call.
        return True
    name = type(exc).__name__
    if name == "ProviderClientValidationError":
        return True
    text = str(exc).lower()
    if "environment variable" in text and "missing" in text:
        return True
    # Local providers report their own unconfigured state this way.
    return "not configured here" in text


def env_present(*names: str) -> bool:
    """True when every named environment variable is set and non-empty."""
    return all(os.environ.get(n, "").strip() for n in names)
