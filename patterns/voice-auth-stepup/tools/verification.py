"""The tools that GRANT a tier. The only writers of `auth_tier`.

Kept apart from `banking.py` so the read is unambiguous: everything that grants
strength is in this file, everything that spends it is in that one. If you are
auditing this pattern for "what can raise a caller's tier", this file is the
complete answer, and it is 150 lines.

WHAT A REAL DEPLOYMENT REPLACES
-------------------------------
`verify_passphrase` and `verify_one_time_code` are the seams. Both compare
against a hard-coded fixture. A real integration swaps the comparison — and
nothing else in the pattern moves, because the tier lattice, the action table
and the guard never see a factor value.

`tutorial/TUTORIAL.md` chapter 5 covers what the real versions must not do. The
short form: never log the code, never put it in a tool result, never write it to
memory, and never let it into the tracker — which on a voice channel means
thinking about the ASR transcript, not just your own logging calls.
"""

from __future__ import annotations

import logging

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from authpolicy import (
    RETRY_BUDGET,
    AuthTier,
    Outcome,
    check_otp,
    check_passphrase,
    coerce,
    factor_for,
    grant,
    redact,
    revoke,
)

logger = logging.getLogger(__name__)


def _attempts(context: ToolContext | None, key: str) -> int:
    """Read an attempt counter out of memory, treating anything odd as zero."""
    if context is None:
        return 0
    try:
        return int(float(context.memory.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def _locked_out(context: ToolContext | None) -> ToolResult:
    """Terminal state: budget exhausted, tier revoked, human required.

    `revoke` is called here and only here. Note the ordering — the caller is
    dropped to NONE *before* the result is returned, so there is no window in
    which a locked-out caller still holds a tier.
    """
    revoke(context)
    if context is not None:
        context.memory.set("locked_out", True)

    return ToolResult(
        llm_response={
            "ok": False,
            "outcome": "locked_out",
            "attempts_remaining": 0,
            "handoff_required": True,
            "hint": (
                "Verification has failed too many times. Do NOT retry and do "
                "NOT complete the request. Hand off to a human with "
                "@skill.human_handoff."
            ),
        }
    )


@tool(
    description=(
        "Check the caller's spoken passphrase. Grants medium verification, "
        "which is enough for account information but never for an irreversible "
        "action."
    )
)
async def verify_passphrase(
    spoken_passphrase: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Knowledge factor. Ceiling is MEDIUM by construction.

    Args:
        spoken_passphrase: What the caller said, as transcribed.
    """
    used = _attempts(context, "passphrase_attempts")
    result = check_passphrase(spoken_passphrase, used)

    # The factor is redacted at the boundary. `redact` returns a length, not the
    # text, so this line is safe to leave on in production.
    logger.info(
        "passphrase_attempt outcome=%s value=%s",
        result.outcome.value,
        redact(spoken_passphrase),
    )

    if context is not None:
        context.memory.set("passphrase_attempts", float(result.attempts_used))

    if result.outcome is Outcome.LOCKED_OUT:
        return _locked_out(context)

    if result.outcome is Outcome.RETRY:
        return ToolResult(
            llm_response={
                "ok": False,
                "outcome": "retry",
                "attempts_remaining": result.attempts_remaining,
                "hint": "Passphrase did not match. Ask them to try once more.",
            }
        )

    held = grant(context, result.granted, "passphrase")
    return ToolResult(
        llm_response={
            "ok": True,
            "outcome": "passed",
            "tier_granted": result.granted.value,
            "tier_held": held.value,
            "note": (
                "This is enough for account information. It is NOT enough for "
                "card reissue or transfers — those need the one-time code."
            ),
        }
    )


@tool(
    description=(
        "Check the caller's spoken one-time code. Grants high verification, "
        "required for irreversible actions like card reissue and transfers."
    )
)
async def verify_one_time_code(
    spoken_code: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Possession factor. Grants HIGH.

    Args:
        spoken_code: The code the caller read out, as transcribed.
    """
    if context is not None and context.memory.get("locked_out"):
        # A locked-out caller does not get a fresh budget by switching factors.
        return _locked_out(context)

    used = _attempts(context, "otp_attempts")
    result = check_otp(spoken_code, used)

    logger.info(
        "otp_attempt outcome=%s value=%s",
        result.outcome.value,
        redact(spoken_code),
    )

    if context is not None:
        context.memory.set("otp_attempts", float(result.attempts_used))

    if result.outcome is Outcome.LOCKED_OUT:
        return _locked_out(context)

    if result.outcome is Outcome.RETRY:
        return ToolResult(
            llm_response={
                "ok": False,
                "outcome": "retry",
                "attempts_remaining": result.attempts_remaining,
                "hint": (
                    "Code did not match. Ask them to try once more. The "
                    "requested action has NOT been performed."
                ),
            }
        )

    held = grant(context, result.granted, "otp")
    return ToolResult(
        llm_response={
            "ok": True,
            "outcome": "passed",
            "tier_granted": result.granted.value,
            "tier_held": held.value,
            "note": "The caller may now retry the action that was refused.",
        }
    )


@tool(
    description=(
        "Send a one-time code to the caller's registered device. Call this "
        "before asking them to read a code back."
    )
)
async def send_one_time_code(context: ToolContext = None) -> ToolResult:
    """Pretend to deliver an OTP out of band.

    Sends nothing. In a real deployment this is an SMS or push provider call,
    and the response must not echo the code back into the conversation — see the
    tutorial. The fixture code is in `authpolicy.challenges.DEMO_OTP` and the
    tutorial tells the reader what to say; the agent must not.
    """
    return ToolResult(
        llm_response={
            "ok": True,
            "delivered": True,
            "destination": "the mobile number ending 3140",
            "hint": (
                "Tell the caller a code was sent and ask them to read it back. "
                "Do NOT state the code yourself — you do not know it."
            ),
        }
    )


@tool(
    description=(
        "Report which verification tier the caller currently holds and what "
        "the pending action still requires."
    )
)
async def check_auth_status(context: ToolContext = None) -> ToolResult:
    """Read-only view of the caller's auth state, for the step-up skill."""
    held = coerce(context.memory.get("auth_tier")) if context else AuthTier.NONE
    pending_action = context.memory.get("pending_action") if context else None
    pending_tier = coerce(context.memory.get("pending_tier")) if context else AuthTier.NONE

    return ToolResult(
        llm_response={
            "ok": True,
            "tier_held": held.value,
            "pending_action": pending_action,
            "required_tier": pending_tier.value,
            "factor_needed": factor_for(pending_tier),
            "satisfied": held.satisfies(pending_tier),
            "retry_budget": RETRY_BUDGET,
        }
    )
