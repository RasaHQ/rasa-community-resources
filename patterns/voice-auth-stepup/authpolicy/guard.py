"""Where a tier is RESOLVED: at the moment the action is attempted.

The whole pattern is this function and the decorator that applies it. Both are
deliberately small enough to read in one sitting, because a guard nobody reads
is a guard nobody maintains.

WHY THE CHECK LIVES HERE AND NOT IN THE SKILL PROSE
---------------------------------------------------
Rasa gives you two places to express "you must be authenticated":

    requires: session.project.authenticated        # skill frontmatter
    tool_constraints: [{tool: {requires: ...}}]    # tool frontmatter

Both are real, both are useful, and **neither is sufficient on its own here.**
They are evaluated by the orchestrator against conversation state, which means
they are instructions to a language model about which tool it may select. That
is a routing control. It is not an execution control: it constrains what the
model is *offered*, not what the process will *do* when the function is entered.

This pattern therefore treats the frontmatter as the outer layer — it keeps the
conversation coherent, so the caller gets asked for a passphrase instead of
being told "no" — and puts the decision that actually binds inside the tool, on
the line before the side effect. The prose can be edited, the model can be
swapped, the constraint can be mistyped in YAML and silently ignored; the
function still refuses.

That is also why the guard is testable without an LLM. The negative test in
`tests/test_guard.py` calls the tool directly and asserts it did not act. No
model, no judge, no sampling — a fact about the process.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .actions import reason_for, tier_for
from .tiers import AuthTier, coerce

# Memory key holding the strongest tier satisfied so far in this session.
# Named once, here, so no caller can typo it into a permanently-empty read —
# which would fail closed, but confusingly.
TIER_MEMORY_KEY = "auth_tier"

# How the caller reached the tier they hold, for the audit line. Never a factor
# VALUE — see `redact` below.
METHOD_MEMORY_KEY = "auth_method"


class StepUpRequired(Exception):
    """Raised when an attempted action outranks the auth the caller holds.

    Carries the tiers rather than a formatted string, so the tool layer decides
    how to phrase the refusal and the test layer can assert on the numbers.
    """

    def __init__(self, action: str, required: AuthTier, held: AuthTier) -> None:
        self.action = action
        self.required = required
        self.held = held
        super().__init__(
            f"{action!r} requires {required.value} authentication; "
            f"caller holds {held.value}"
        )


@dataclass(frozen=True)
class Decision:
    """The outcome of one guard evaluation, for logging and for the tests."""

    action: str
    required: AuthTier
    held: AuthTier
    allowed: bool
    reason: str


def evaluate(action: str, held: object) -> Decision:
    """Decide whether `action` may proceed for a caller holding `held`.

    Pure: no memory access, no I/O, no exceptions. Everything the guard knows is
    in the return value, which is what makes the decision table in
    `tests/test_guard.py` exhaustive rather than illustrative.
    """
    required = tier_for(action)
    held_tier = coerce(held)
    return Decision(
        action=action,
        required=required,
        held=held_tier,
        allowed=held_tier.satisfies(required),
        reason=reason_for(action),
    )


def require_tier(action: str, context: Any) -> Decision:
    """Enforce `action`'s declared tier against the tier in session memory.

    Call this as the FIRST statement of any tool with a side effect or a
    disclosure. It raises `StepUpRequired` rather than returning a falsy value,
    because a return value can be ignored by a caller who forgot to check it and
    an exception cannot.

    A missing context is treated as unauthenticated, not as a reason to skip the
    check. `context is None` happens in unit tests and in tool-discovery probes;
    neither is a reason to perform a card reissue.
    """
    held: object = AuthTier.NONE
    if context is not None:
        held = context.memory.get(TIER_MEMORY_KEY)

    decision = evaluate(action, held)
    if not decision.allowed:
        raise StepUpRequired(action, decision.required, decision.held)
    return decision


def grant(context: Any, tier: AuthTier, method: str) -> AuthTier:
    """Record that `tier` has been satisfied, and return the tier now held.

    Monotonic on purpose: granting MEDIUM to a caller who already holds HIGH
    leaves them at HIGH. Auth strength within a session is a high-water mark, so
    a later low-tier interaction can never *weaken* a caller — which is the
    downgrade bug this pattern is partly about. Nothing in this package lowers
    the mark except `revoke`, which is only reached by lockout.
    """
    current = coerce(context.memory.get(TIER_MEMORY_KEY)) if context else AuthTier.NONE
    new = current if current.rank >= tier.rank else tier
    if context is not None:
        context.memory.set(TIER_MEMORY_KEY, new.value)
        context.memory.set(METHOD_MEMORY_KEY, method)
    return new


def revoke(context: Any) -> None:
    """Drop the caller to NONE. Called on lockout, never on an ordinary failure.

    Distinguishing these matters: a caller who fumbles an OTP has not proven
    they are an attacker, but a caller who exhausts the retry budget has stopped
    being someone we will keep guessing with.
    """
    if context is not None:
        context.memory.set(TIER_MEMORY_KEY, AuthTier.NONE.value)
        context.memory.set(METHOD_MEMORY_KEY, "revoked")


def redact(secret: str) -> str:
    """Render a factor for a log line without disclosing it.

    Every string in this package that could be a passphrase or a one-time code
    passes through here before it reaches a log, a tool result, or a tracker
    event. Voice makes this worse than it sounds: an ASR transcript of the turn
    where the caller said their passphrase is a plaintext credential sitting in
    the conversation history, and it will be replayed by anyone debugging the
    call. See the README's "What this is not suitable for".
    """
    if not secret:
        return "<empty>"
    return f"<redacted:{len(secret)} chars>"
