"""The fixture agent desk — the RECEIVING side of the handoff.

A package nothing consumes is not a transfer. It is a data structure with good
intentions. So this module is the other half of the pattern: it takes a
serialised package off a queue and reconstructs the caller's state well enough
that a human can open the conversation with the answer rather than with
"can I take your name?".

**This is a fixture and it is meant to be.** There is no Genesys, no Twilio
Flex, no Zendesk, no ticket API. What a real contact-centre integration replaces
is exactly :func:`deliver` — one function, ~10 lines — and the tutorial says so.
What it must NOT be handed is anything that did not come through
``handoffpkg.redaction.build_package_from_session``.

The reconstruction test the desk is built to answer is narrow and checkable:

    Can the human agent, reading ONLY this, avoid every question the caller has
    already answered?

:func:`unanswered_questions` answers it mechanically, by diffing the questions
the desk would normally ask against ``do_not_repeat.questions_answered``. That
diff is what makes "the caller is never asked twice" a property with a test
rather than a claim in a README.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from handoffpkg.schema import (
    HandoffPackage,
    TIER_MEANING,
    package_from_dict,
    tier_at_least,
)

# The script a desk agent works from when NOTHING was transferred — i.e. the
# current state of the catalog, where a handoff carries one free-text reason.
# Every line here is a question the caller has already answered once.
DESK_OPENING_SCRIPT: tuple[str, ...] = (
    "Can I take your name?",
    "Can you confirm your date of birth?",
    "Which account is this about?",
    "What are you calling about today?",
    "Have you tried anything already?",
)

# Which of those questions each package section makes unnecessary. The mapping
# is what turns the package from a document into a state transfer: a section
# that retires no question is a section carrying nothing the desk needed.
_QUESTION_RETIRED_BY: dict[str, str] = {
    "Can I take your name?": "identity.display_name",
    "Can you confirm your date of birth?": "identity.verified_tier",
    "Which account is this about?": "intent.details.account_id",
    "What are you calling about today?": "intent.goal",
    "Have you tried anything already?": "attempts",
}


@dataclass(frozen=True)
class DeskView:
    """What the human agent actually sees when the call lands."""

    header: str
    caller: str
    trust: str
    asking_for: str
    already_tried: tuple[str, ...]
    do_not_ask: tuple[str, ...]
    withheld: tuple[str, ...]
    permitted_actions: tuple[str, ...]
    summary: str

    def render(self) -> str:
        """Plain-text screen. A terminal is a legitimate agent desk for a demo."""
        lines = [
            "=" * 72,
            self.header,
            "=" * 72,
            f"CALLER      {self.caller}",
            f"TRUST       {self.trust}",
            f"ASKING FOR  {self.asking_for}",
            "",
            "ALREADY TRIED (do not retry these):",
        ]
        lines.extend(f"  · {item}" for item in self.already_tried or ("(nothing)",))
        lines.append("")
        lines.append("DO NOT ASK — the caller already answered these:")
        lines.extend(f"  · {item}" for item in self.do_not_ask or ("(nothing)",))
        lines.append("")
        lines.append("YOU MAY:")
        lines.extend(f"  · {item}" for item in self.permitted_actions)
        if self.withheld:
            lines.append("")
            lines.append("WITHHELD BY POLICY (present in the session, not transferred):")
            lines.extend(f"  · {item}" for item in self.withheld)
            lines.append("  Do not ask the caller to read these out to you.")
        lines.append("=" * 72)
        return "\n".join(lines)


def permitted_actions(package: HandoffPackage) -> tuple[str, ...]:
    """What the desk may do, derived from the verification tier.

    Derived, not carried. The package records the tier that was reached; the
    desk decides what that tier licenses. Shipping a permissions list inside the
    package would let an upstream agent grant the desk authority it does not
    have, which is the wrong direction for that decision to flow.
    """
    tier = package.identity.verified_tier
    actions = ["Answer general questions", "Explain what the agent already did"]
    if tier_at_least(tier, "medium"):
        actions.append("Discuss account-specific details")
    else:
        actions.append("DO NOT discuss account-specific details — identity not established")
    if tier_at_least(tier, "high"):
        actions.append("Action irreversible changes (transfers, card reissue, SIM swap)")
    else:
        actions.append("DO NOT action irreversible changes — step the caller up first")
    return tuple(actions)


def reconstruct(package: HandoffPackage) -> DeskView:
    """Rebuild the caller's state from the package alone.

    Note what this function is NOT given: the conversation, the transcript, the
    session, the agent. Only the package. If the desk view is complete, the
    package was a real state transfer; if it is thin, the package was a ticket
    with extra steps. Constraining the input is what makes the demonstration
    honest.
    """
    identity = package.identity
    intent = package.intent

    caller = identity.display_name or identity.customer_id or "UNIDENTIFIED"
    if identity.customer_id and identity.display_name:
        caller = f"{identity.display_name} ({identity.customer_id})"
    if identity.channel:
        caller += f" via {identity.channel}"

    trust = f"tier={identity.verified_tier} — {TIER_MEANING.get(identity.verified_tier, 'unknown tier')}"

    asking_for = intent.goal_label or intent.goal
    if intent.details:
        rendered = ", ".join(f"{k}={v}" for k, v in sorted(intent.details.items()))
        asking_for += f" [{rendered}] (stage: {intent.stage})"
    else:
        asking_for += f" (stage: {intent.stage})"

    already_tried = tuple(
        f"{a.action} → {a.outcome}" + (f" ({a.detail})" if a.detail else "")
        for a in package.attempts
    )

    do_not_ask = (
        tuple(package.do_not_repeat.questions_answered)
        + tuple(f"verified: {f}" for f in package.do_not_repeat.factors_verified)
        + tuple(f"confirmed: {f}" for f in package.do_not_repeat.confirmed_facts)
    )

    return DeskView(
        header=f"INBOUND HANDOFF {package.handoff_id} — {package.reason}",
        caller=caller,
        trust=trust,
        asking_for=asking_for,
        already_tried=already_tried,
        do_not_ask=do_not_ask,
        withheld=package.withheld_fields,
        permitted_actions=permitted_actions(package),
        # Derived at read time from the package's own fields — the desk does not
        # store a summary either.
        summary=package.summary,
    )


def unanswered_questions(package: HandoffPackage) -> tuple[str, ...]:
    """Questions from :data:`DESK_OPENING_SCRIPT` the desk STILL has to ask.

    The measurable form of the teaching claim. With the catalog's current
    one-string handoff this returns the whole script; with a real context
    package it returns the empty tuple, and the difference is a number a test
    can assert on rather than a sentence a README can assert.
    """
    still_needed: list[str] = []
    for question in DESK_OPENING_SCRIPT:
        source = _QUESTION_RETIRED_BY[question]
        if not _package_answers(package, source):
            still_needed.append(question)
    return tuple(still_needed)


def _package_answers(package: HandoffPackage, source: str) -> bool:
    """Is ``source`` actually populated in ``package``?

    Written as a function rather than a getattr because "populated" is not the
    same question for every section, and the differences are load-bearing.

    The attempts case is the one worth spelling out. It is tempting to say that
    an empty attempts list answers "have you tried anything already?" — the
    answer is "no". But an empty list is also exactly what a package built from
    a session that never recorded attempts looks like, and the two are
    indistinguishable from the far side. Reading emptiness as an answer would
    let a package that transferred nothing claim to have retired the question.
    So emptiness is treated as absence of information, and the desk still asks.
    """
    if source == "identity.display_name":
        return bool(package.identity.display_name)
    if source == "identity.verified_tier":
        # A tier of "unverified" genuinely does not retire the DOB question:
        # the desk still has to establish who it is talking to.
        return package.identity.verified_tier != "unverified"
    if source == "intent.details.account_id":
        # `details` is typed dict but arrives from JSON, where it can be null.
        # This runs on the handoff tool's hot path, so it degrades rather than
        # raising: the desk asks one question it need not have, which is a far
        # better failure than the handoff dying mid-transfer.
        details = package.intent.details
        return bool(details.get("account_id")) if isinstance(details, dict) else False
    if source == "intent.goal":
        return package.intent.goal not in ("", "unknown")
    if source == "attempts":
        # Non-empty only. See the docstring: an empty tuple cannot be
        # distinguished from a package that carried no attempts section, and a
        # transfer that carried nothing must not read as having answered
        # anything. The desk asks, which is the safe direction to be wrong in.
        return bool(package.attempts)
    return False


def deliver(package: HandoffPackage, path: str) -> dict[str, Any]:
    """Hand the package to the desk. **This is the seam.**

    A real contact-centre integration replaces this function and nothing else:
    write to a Genesys interaction, a Twilio Flex task attribute, a Zendesk
    ticket field. Two rules survive that swap, and they are the tutorial's whole
    point about integrations:

    1. What is handed over is a package produced by
       ``build_package_from_session`` — never raw session state, never a dict
       assembled at the call site.
    2. Whatever the destination stores, it inherits this package's boundary. A
       CRM field that ends up holding a PIN is a leak regardless of how careful
       the allowlist upstream was.
    """
    payload = package.to_dict()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    return payload


def receive(path: str) -> DeskView:
    """Read a delivered package back off the queue and reconstruct from it.

    Round-tripping through JSON is not ceremony. It is how the summary's
    derivation gets proven under the condition that actually matters: the desk
    reconstructs from bytes that crossed a boundary, and it recomputes the
    summary from the fields in those bytes rather than trusting the summary that
    travelled with them.
    """
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return reconstruct(package_from_dict(data))
