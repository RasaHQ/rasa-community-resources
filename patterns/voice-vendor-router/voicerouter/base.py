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

    @classmethod
    def from_dict(cls, raw: Optional[dict[str, Any]]) -> "RouterPolicy":
        raw = raw or {}
        unknown = set(raw) - {"cooldown_seconds", "failure_threshold", "skip_unconfigured"}
        if unknown:
            raise ValueError(
                f"unknown policy key(s): {', '.join(sorted(unknown))}. "
                f"Supported: cooldown_seconds, failure_threshold, skip_unconfigured."
            )
        return cls(
            cooldown_seconds=float(raw.get("cooldown_seconds", 30.0)),
            failure_threshold=int(raw.get("failure_threshold", 1)),
            skip_unconfigured=bool(raw.get("skip_unconfigured", True)),
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
    and engines that read os.environ directly raise KeyError. Both mean the same
    thing to an operator: this vendor is not configured here.
    """
    if isinstance(exc, KeyError):
        return True
    name = type(exc).__name__
    if name == "ProviderClientValidationError":
        return True
    text = str(exc).lower()
    return "environment variable" in text and "missing" in text


def env_present(*names: str) -> bool:
    """True when every named environment variable is set and non-empty."""
    return all(os.environ.get(n, "").strip() for n in names)
