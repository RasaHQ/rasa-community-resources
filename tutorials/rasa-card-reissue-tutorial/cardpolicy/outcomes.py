"""The vocabulary of results, including the ones that must stay failures.

WHY OUTCOMES ARE A TYPE AND NOT A DICT
--------------------------------------
The failure mode this module prevents is subtle and common: a tool returns
`{"ok": False, "message": "..."}`, the model reads the message, finds it
sympathetic, and tells the caller their card is on its way. Nothing crashed.
The log says the tool refused. The caller heard a promise.

Making the outcome a closed set with an explicit `terminal` flag means the
skill prose can be written against categories rather than against message text,
and the test suite can assert on a category rather than on a sentence somebody
will reword next month.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Result(str, Enum):
    """Every way a reissue attempt can end. There are no others."""

    OK = "ok"
    """A card was ordered. A reference exists. This is the ONLY value that
    licenses the agent to say a card is coming."""

    STEP_UP_REQUIRED = "step_up_required"
    """Nothing happened. The caller can fix this by verifying further."""

    COOLING_OFF = "cooling_off"
    """Nothing happened, and the caller cannot fix it on this call. A new
    address was added too recently for a card to be sent to it."""

    DUPLICATE = "duplicate"
    """Nothing NEW happened. An identical request already succeeded, and this
    call returns that same reference rather than posting a second card."""

    REFUSED = "refused"
    """Nothing happened and nothing the caller can say changes that. The
    correct next move is a human, not a workaround."""


@dataclass(frozen=True)
class Outcome:
    """What a reissue attempt did, in a form prose can be written against."""

    result: Result
    message: str
    """One sentence, safe to paraphrase aloud. Never contains a factor value,
    a full card number, or a one-time code."""

    reference: str | None = None
    """Present if and only if `result is Result.OK` or `Result.DUPLICATE`."""

    detail: dict[str, str] = field(default_factory=dict)
    """Structured context for logs and tests. Not for reading aloud."""

    @property
    def acted(self) -> bool:
        """True only when a card is actually going to be posted.

        Read this, not `result != REFUSED`. Every non-OK branch has at some
        point been mistaken for a soft success by somebody in a hurry, and the
        purpose of a single named property is that there is one thing to get
        right instead of five.
        """
        return self.result in (Result.OK, Result.DUPLICATE)


def succeeded(reference: str, *, duplicate: bool = False) -> Outcome:
    """A card is on its way — or already was."""
    if duplicate:
        return Outcome(
            result=Result.DUPLICATE,
            message=(
                "That replacement card was already ordered on this call and is "
                "on its way. No second card has been sent."
            ),
            reference=reference,
        )
    return Outcome(
        result=Result.OK,
        message="The replacement card has been ordered.",
        reference=reference,
    )


def refused(result: Result, message: str, **detail: str) -> Outcome:
    """Nothing happened. Say so.

    Guards against the one mistake worth guarding against here: a refusal
    carrying a reference number. A reference is a promise that something
    exists, and nothing does.
    """
    if result in (Result.OK, Result.DUPLICATE):
        raise ValueError(
            f"{result.value!r} is not a refusal; build it with succeeded()"
        )
    return Outcome(result=result, message=message, reference=None, detail=detail)
