"""SIM swap policy: the number being replaced cannot vouch for itself.

Pure policy. No database, no memory, no network, no logging. Everything the
decision depends on is in its two arguments, and everything it concludes is in
the return value, which is what lets `tests/test_sim_swap.py` assert on it
without an agent, a model or a key.

THE RULE
--------
A SIM swap moves a phone number onto a new SIM. The classic attack is a caller
who says they lost their phone and asks to move "their" number to a SIM they
already hold. Two verification habits fail against it:

* **A one-time code sent by SMS or voice call to the line being replaced.** It
  is circular: the line being replaced cannot be the only witness to its own
  replacement. And if the attacker already controls the line (a forwarded
  number, an earlier port-out, a compromised voicemail), the code hands them
  the approval.
* **Knowledge factors** (account PIN, date of birth, security answers). These
  can be phished, bought, or read off a social profile. They never authorise
  this action on their own, however correct they are.

Independence is a property of the verification channel RELATIVE TO THE ACTION'S
TARGET, not of the factor type. An SMS code is a reasonable factor for many
things; it is worthless for moving the number it was sent to.

This policy recognises exactly two independent channels:

* ``app_push`` to a device that was registered on the account BEFORE this call.
  A device enrolled during the call was enrolled on the strength of the same
  unverified caller, so it proves nothing.
* ``store_id_check``: a person with photo ID in a store. A voice agent cannot
  produce one; the store's system would record it. The policy accepts it so the
  rule is complete, and the voice skill stops remote activation instead.

REASON CODES
------------
Exactly five, and every refusal carries one:

``no_verification``
    No usable verification exists. This covers "never verified" and also every
    malformed or unrecognised record: a missing field, ``passed="true"`` as a
    string, an unknown channel, a failed attempt, an app push to a device that
    was not registered before the call, or a code sent to some other number.
    None of those is a verification this policy accepts, so it does not invent
    a more specific name for them.
``knowledge_only``
    The only factor was a PIN, a date of birth or a security answer.
``target_changed``
    The verification was issued for a different line than the one now being
    swapped. A caller who verified line A and then asks to move line B has not
    verified line B.
``circular_verification``
    An SMS or voice-call code delivered to the target line itself.
``allowed``
    An independent channel, issued for this line, passed.

The order of checks is structural refusals first (knowledge, wrong target,
circular), then whether it passed, then independence. A circular code is
refused as circular whether or not the caller read it back correctly.

This is a teaching policy for a fictional carrier. It is not any real carrier's
SIM swap procedure and does not describe one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Reason codes. Written once, here, so no caller can typo one into a string the
# tests would never match.
# ---------------------------------------------------------------------------

NO_VERIFICATION = "no_verification"
KNOWLEDGE_ONLY = "knowledge_only"
CIRCULAR_VERIFICATION = "circular_verification"
TARGET_CHANGED = "target_changed"
ALLOWED = "allowed"

REASON_CODES = frozenset(
    {NO_VERIFICATION, KNOWLEDGE_ONLY, CIRCULAR_VERIFICATION, TARGET_CHANGED, ALLOWED}
)

# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

#: Things the caller knows. Never sufficient for this action.
KNOWLEDGE_CHANNELS = frozenset({"pin", "dob", "security_answer"})

#: Codes delivered to a phone number. Circular when the number is the target.
LINE_CHANNELS = frozenset({"sms", "voice_call"})

#: The two independent channels, named once. `evaluate_swap` and the send tool
#: in skills/sim_swap/tools.py each branch on these names explicitly.
APP_PUSH = "app_push"
STORE_ID_CHECK = "store_id_check"

#: The only channels that can authorise a swap. This set is a declaration, not
#: a router: adding a name here does NOT create an approval path, because no
#: code allows a channel merely for being in it. A new channel needs its own
#: explicit branch in `evaluate_swap` and in the send tool.
INDEPENDENT_CHANNELS = frozenset({APP_PUSH, STORE_ID_CHECK})

KNOWN_CHANNELS = KNOWLEDGE_CHANNELS | LINE_CHANNELS | INDEPENDENT_CHANNELS


@dataclass(frozen=True)
class SwapVerification:
    """One verification attempt, as recorded when it was issued.

    Holds no code. A record that carried the code would put it wherever the
    record goes: memory, logs, a tool result read aloud by TTS.
    """

    channel: str
    """How the verification was delivered: one of ``KNOWN_CHANNELS``."""

    destination: str
    """Where it was delivered: a phone number for ``sms``/``voice_call``.

    For ``app_push`` the tools store the neutral token ``registered_device``,
    never a device id or label, because memory can reach the model and the
    model is talking to a caller who is not yet verified.
    """

    issued_for_line: str
    """The line the caller said they wanted to swap when this was issued."""

    passed: bool
    """True only once the challenge was actually completed."""

    registered_before_call: bool = False
    """For ``app_push``: the device's ``registered_at`` is earlier than the
    call start. The tools compute it; this policy only reads it."""

    def to_json(self) -> str:
        """Serialise for memory, which stores text."""
        return json.dumps(
            {
                "channel": self.channel,
                "destination": self.destination,
                "issued_for_line": self.issued_for_line,
                "passed": self.passed,
                "registered_before_call": self.registered_before_call,
            },
            sort_keys=True,
        )


@dataclass(frozen=True)
class SwapDecision:
    """The outcome of one evaluation. ``allowed`` is True only for ``allowed``."""

    allowed: bool
    reason: str
    target_line: str
    channel: str | None = None


def line_digits(value: object) -> str:
    """Compare phone numbers by their digits, so "555-0142" equals "5550142".

    Deliberately not smarter than that. "+1 555 0142" does NOT equal
    "555-0142" here. For the circular check that means a padded number slips
    past the circular rule, but it still fails the independence rule and is
    refused as ``no_verification``. A mismatch can only ever refuse.
    """
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value if ch.isdigit())


def coerce_verification(value: object) -> SwapVerification | None:
    """Read a verification out of whatever memory handed back, failing CLOSED.

    Accepts a ``SwapVerification``, a mapping, or a JSON string of a mapping.
    Returns None for anything else, and for any record with a missing field or a
    field of the wrong type. ``passed`` must be the boolean ``True``, not
    ``"true"``, ``1`` or ``"yes"``: a guard that coerces truthy strings is a
    guard an LLM can talk past by writing one into memory.

    Never raises. A guard that throws on odd input gets wrapped in a bare
    ``except`` that lets the action through.
    """
    if isinstance(value, SwapVerification):
        record: Any = {
            "channel": value.channel,
            "destination": value.destination,
            "issued_for_line": value.issued_for_line,
            "passed": value.passed,
            "registered_before_call": value.registered_before_call,
        }
    elif isinstance(value, str):
        try:
            record = json.loads(value)
        except (TypeError, ValueError):
            return None
    elif isinstance(value, Mapping):
        record = dict(value)
    else:
        return None

    if not isinstance(record, dict):
        return None

    channel = record.get("channel")
    destination = record.get("destination")
    issued_for = record.get("issued_for_line")
    passed = record.get("passed")
    registered = record.get("registered_before_call", False)

    if not isinstance(channel, str) or channel not in KNOWN_CHANNELS:
        return None
    if not isinstance(destination, str) or not destination.strip():
        return None
    if not isinstance(issued_for, str) or not line_digits(issued_for):
        return None
    # `type(...) is bool` rather than isinstance: True is also an int, and 1 is
    # not a verification outcome.
    if type(passed) is not bool or type(registered) is not bool:
        return None

    return SwapVerification(
        channel=channel,
        destination=destination,
        issued_for_line=issued_for,
        passed=passed,
        registered_before_call=registered,
    )


def evaluate_swap(target_line: object, verification: object) -> SwapDecision:
    """Decide whether a swap of ``target_line`` may proceed on ``verification``.

    Pure: same inputs, same decision, no side effects. Never raises.
    """
    target = target_line if isinstance(target_line, str) else ""
    record = coerce_verification(verification)

    if record is None or not line_digits(target):
        return SwapDecision(False, NO_VERIFICATION, target)

    def refuse(reason: str) -> SwapDecision:
        return SwapDecision(False, reason, target, record.channel)

    if record.channel in KNOWLEDGE_CHANNELS:
        return refuse(KNOWLEDGE_ONLY)

    if line_digits(record.issued_for_line) != line_digits(target):
        return refuse(TARGET_CHANGED)

    if record.channel in LINE_CHANNELS and line_digits(record.destination) == line_digits(
        target
    ):
        return refuse(CIRCULAR_VERIFICATION)

    if not record.passed:
        return refuse(NO_VERIFICATION)

    if record.channel == APP_PUSH and record.registered_before_call:
        return SwapDecision(True, ALLOWED, target, record.channel)

    if record.channel == STORE_ID_CHECK:
        return SwapDecision(True, ALLOWED, target, record.channel)

    # A code to some other number, or a push to a device enrolled during this
    # call. Not circular, not knowledge, and not independent either.
    return refuse(NO_VERIFICATION)
