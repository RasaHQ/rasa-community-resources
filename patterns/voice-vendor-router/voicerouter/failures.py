"""Deciding what a vendor failure *means*, so re-routing can be sensible.

A wrapper treats every exception the same: something broke, wait a bit, try
again. A router cannot afford that, because the failures are not alike.

    401 bad key          retrying is pointless — it will be wrong every time
    402 out of credits   pointless for a while; the account has to be topped up
    429 rate limited     retry, but only after the window the vendor told you
    400 bad request      pointless forever — the config is wrong, not the vendor
    503 / timeout        very likely fine in a second

Parking a rate-limited vendor for the same duration as a permanently
misconfigured one wastes the good vendor. Retrying a 401 every thirty seconds
for the length of a call wastes everything. So each failure is classified, and
the classification decides how long — if ever — that provider is skipped.

Everything here is derived from exception types that are actually raised by the
libraries this package uses: aiohttp, websockets, botocore and google-api-core.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Any, Optional


class FailureKind(enum.Enum):
    """Why a provider failed, in terms a routing decision can use."""

    AUTH = "auth"              # credentials rejected
    CONFIG = "config"          # the request itself is wrong
    QUOTA = "quota"            # credits or quota exhausted
    RATE_LIMIT = "rate_limit"  # too fast, slow down
    TRANSIENT = "transient"    # the vendor wobbled
    UNAVAILABLE = "unavailable"  # could not reach it at all
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Verdict:
    kind: FailureKind
    #: Seconds to skip this provider. None means "use the default cooldown".
    retry_after: Optional[float]
    #: True when retrying can never help without human intervention.
    permanent: bool
    reason: str

    def __str__(self) -> str:
        window = "permanently" if self.permanent else (
            f"for {self.retry_after:.0f}s" if self.retry_after else "briefly"
        )
        return f"{self.kind.value} ({self.reason}) — skipping {window}"


# Default cooldowns per class, in seconds. A quota failure is parked for long
# enough that the router stops asking, but not so long that a topped-up account
# stays shut out for the rest of the process's life.
# Only the kinds whose right answer comes from the vendor's own semantics, not
# from the operator's taste. A quota window is a billing period; a rate limit is
# a short apology; a 5xx is usually over in seconds. Nobody tuning a deployment
# knows better than that.
#
# UNAVAILABLE and UNKNOWN are deliberately absent, and that absence is the
# feature: "how long do I skip a vendor that went dark" is exactly the question
# `policy.cooldown_seconds` exists to answer, and it can only answer it for
# kinds that are not already spoken for here. Adding an entry for them would
# make the knob configurable and inert, which is worse than not having it.
DEFAULT_COOLDOWNS: dict[FailureKind, float] = {
    FailureKind.AUTH: 0.0,         # permanent; cooldown unused
    FailureKind.CONFIG: 0.0,       # permanent; cooldown unused
    FailureKind.QUOTA: 900.0,      # 15 minutes
    FailureKind.RATE_LIMIT: 20.0,  # overridden by Retry-After when present
    FailureKind.TRANSIENT: 15.0,
}

_PERMANENT = {FailureKind.AUTH, FailureKind.CONFIG}

# Failures that justify handing the caller to a different voice.
#
# Switching provider mid-call means the person on the phone hears someone else
# start speaking. That is worth doing when the current provider genuinely
# cannot serve — the credits are gone, the key is rejected, the API is
# unreachable — and not worth doing because a vendor asked us to slow down for
# two seconds. The rest are retried on the same provider first, so the voice
# stays put whenever staying put is possible.
_JUSTIFIES_VOICE_CHANGE = {
    FailureKind.AUTH,
    FailureKind.CONFIG,
    FailureKind.QUOTA,
    FailureKind.UNAVAILABLE,
}


def justifies_voice_change(verdict: "Verdict") -> bool:
    """True when this failure is worth a different voice."""
    return verdict.kind in _JUSTIFIES_VOICE_CHANGE


def should_retry_same_provider(verdict: "Verdict") -> bool:
    """True when the same provider deserves another go before we switch.

    A rate limit or a 503 is a "not right now", not a "not ever". Retrying the
    provider that already owns the call's voice is nearly always better for the
    listener than swapping mid-sentence.
    """
    return not justifies_voice_change(verdict)

# Text signals, for vendors that return a generic status with the real reason in
# the body. Checked only after status codes, which are more reliable.
_QUOTA_RE = re.compile(
    r"quota|insufficient[_ ]?(funds|credit|balance)|out of credit|billing|"
    r"payment required|exceeded your current|credit balance",
    re.I,
)
_AUTH_RE = re.compile(
    r"unauthor|forbidden|invalid[_ ]?api[_ ]?key|authentication|not authenticated|"
    r"invalid[_ ]?token|access denied|signature",
    re.I,
)
_RATE_RE = re.compile(r"rate.?limit|too many requests|throttl|slow ?down", re.I)


#: Wrapped exceptions often keep the status only in their message — Rasa's own
#: "Connection to Rime TTS failed with status 400" is exactly that shape, and
#: reading it as a connectivity blip would retry a permanently broken config
#: every thirty seconds for the length of the call.
_STATUS_IN_TEXT_RE = re.compile(r"\b(?:status(?:[ _]code)?|HTTP)\D{0,3}(\d{3})\b", re.I)


def _status_in_text(text: str) -> Optional[int]:
    match = _STATUS_IN_TEXT_RE.search(text)
    if not match:
        return None
    status = int(match.group(1))
    return status if 100 <= status <= 599 else None


def _status_of(exc: BaseException) -> Optional[int]:
    """Pull an HTTP/gRPC status out of whatever the vendor raised."""
    # aiohttp
    status = getattr(exc, "status", None)
    if isinstance(status, int):
        return status
    # websockets (both the old InvalidStatusCode and the newer InvalidStatus)
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    response = getattr(exc, "response", None)
    if response is not None:
        nested = getattr(response, "status_code", None)
        if isinstance(nested, int):
            return nested
        # botocore keeps it in a dict
        if isinstance(response, dict):
            meta = response.get("ResponseMetadata") or {}
            http = meta.get("HTTPStatusCode")
            if isinstance(http, int):
                return http
    # google-api-core exceptions carry `code` as a class attribute
    gcode = getattr(exc, "code", None)
    if isinstance(gcode, int):
        return gcode
    return None


def _retry_after_of(exc: BaseException) -> Optional[float]:
    """Honour the vendor's own back-off hint when it gives one."""
    headers = getattr(exc, "headers", None) or {}
    try:
        value = headers.get("Retry-After") or headers.get("retry-after")
    except AttributeError:
        value = None
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        # Retry-After may be an HTTP date; a fixed fallback beats a crash.
        return None


def _aws_code_of(exc: BaseException) -> Optional[str]:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error") or {}
        code = error.get("Code")
        if isinstance(code, str):
            return code
    return None


def _safe_str(exc: BaseException) -> str:
    """`str(exc)` can itself raise — aiohttp's does on a partly-built error.

    A classifier that crashes would take the call down, which is precisely the
    outcome it exists to prevent, so the text signal is best-effort.
    """
    try:
        return str(exc)
    except Exception:  # noqa: BLE001
        return type(exc).__name__


def classify(exc: BaseException) -> Verdict:
    """Map a vendor exception onto a routing decision."""
    text = _safe_str(exc)
    # Attribute first, then the message: a wrapped exception loses the
    # attribute but usually keeps the number in its text.
    status = _status_of(exc) or _status_in_text(text)
    retry_after = _retry_after_of(exc)
    aws_code = _aws_code_of(exc)

    # AWS names its failures, which is more reliable than the status it pairs
    # them with — ThrottlingException can arrive as 400.
    if aws_code:
        if aws_code in {"ThrottlingException", "TooManyRequestsException",
                        "RequestThrottled", "SlowDown"}:
            return Verdict(FailureKind.RATE_LIMIT, retry_after, False, f"aws {aws_code}")
        if aws_code in {"UnrecognizedClientException", "InvalidSignatureException",
                        "AccessDeniedException", "AuthFailure",
                        "IncompleteSignature", "MissingAuthenticationToken"}:
            return Verdict(FailureKind.AUTH, None, True, f"aws {aws_code}")
        if aws_code in {"ServiceQuotaExceededException", "LimitExceededException"}:
            return Verdict(FailureKind.QUOTA, retry_after, False, f"aws {aws_code}")
        if aws_code in {"ValidationException", "BadRequestException",
                        "InvalidParameterException", "InvalidParameterValue"}:
            return Verdict(FailureKind.CONFIG, None, True, f"aws {aws_code}")

    if status is not None:
        if status in (401, 403):
            return Verdict(FailureKind.AUTH, None, True, f"HTTP {status}")
        if status == 402:
            return Verdict(FailureKind.QUOTA, retry_after, False, f"HTTP {status}")
        if status == 429:
            # A 429 is sometimes billing dressed as throttling; the body says which.
            if _QUOTA_RE.search(text):
                return Verdict(FailureKind.QUOTA, retry_after, False, "HTTP 429, quota text")
            return Verdict(FailureKind.RATE_LIMIT, retry_after, False, "HTTP 429")
        if status in (400, 404, 405, 415, 422):
            return Verdict(FailureKind.CONFIG, None, True, f"HTTP {status}")
        if 500 <= status <= 599:
            return Verdict(FailureKind.TRANSIENT, retry_after, False, f"HTTP {status}")

    # Connectivity failures never reach a status code.
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return Verdict(FailureKind.UNAVAILABLE, None, False, type(exc).__name__)
    if isinstance(exc, ModuleNotFoundError):
        return Verdict(FailureKind.CONFIG, None, True, "optional package missing")

    # Fall back to the message. Wrapped exceptions (Rasa's TTSError, for one)
    # often carry the vendor's words but none of its attributes.
    if _AUTH_RE.search(text):
        return Verdict(FailureKind.AUTH, None, True, "auth text")
    if _QUOTA_RE.search(text):
        return Verdict(FailureKind.QUOTA, retry_after, False, "quota text")
    if _RATE_RE.search(text):
        return Verdict(FailureKind.RATE_LIMIT, retry_after, False, "rate-limit text")
    if re.search(r"timed? ?out|connection|unreachable|refused|reset", text, re.I):
        return Verdict(FailureKind.UNAVAILABLE, None, False, "connectivity text")

    return Verdict(FailureKind.UNKNOWN, None, False, type(exc).__name__)


def cooldown_for(verdict: Verdict, default: float) -> float:
    """How long to skip a provider given this verdict."""
    if verdict.permanent:
        return float("inf")
    if verdict.retry_after is not None:
        # Trust the vendor's own hint over any local default.
        return max(float(verdict.retry_after), 1.0)
    configured = DEFAULT_COOLDOWNS.get(verdict.kind)
    return default if configured is None else configured


def is_permanent(verdict: Verdict) -> bool:
    return verdict.kind in _PERMANENT
