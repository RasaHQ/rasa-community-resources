"""Turning stored values into something a text-to-speech voice reads correctly.

A date like ``2026-09-12`` is read out by TTS as "two thousand and twenty-six
dash zero nine dash twelve", and a reference like ``CIV1006`` comes out as
"civ one thousand and six". Both are useless on a phone call, and both are the
one piece of information the caller actually needs to write down.
"""

from __future__ import annotations

import re
from datetime import date

_DIGITS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
           "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}

_ORDINALS = [
    "", "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
    "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
    "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
    "nineteenth", "twentieth", "twenty first", "twenty second",
    "twenty third", "twenty fourth", "twenty fifth", "twenty sixth",
    "twenty seventh", "twenty eighth", "twenty ninth", "thirtieth",
    "thirty first",
]

_MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def say_reference(complaint_id: str) -> str:
    """"CIV1006" -> "C I V one zero zero six"."""
    return " ".join(_DIGITS.get(ch, ch.upper()) for ch in str(complaint_id))


def say_date(iso: str) -> str:
    """"2026-09-12" -> "the twelfth of September".

    No year: every date this line reads out is within a few weeks, and a year
    read aloud is three extra syllables that tell the caller nothing.
    """
    try:
        day = date.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return str(iso)
    return f"the {_ORDINALS[day.day]} of {_MONTHS[day.month]}"


def hear_reference(spoken: str) -> str:
    """"C I V one zero zero two" -> "CIV1002".

    The mirror of :func:`say_reference`. The agent reads a reference out one
    character at a time, so that is how callers read it back — and the model,
    unsure whether to transcribe or to convert, would sometimes pass the words
    straight through and then apologise when the lookup missed.

    Converting here rather than instructing the model to convert is the same
    trade this whole project is built on: it is a fixed transformation, so it
    belongs in code, where it happens every time.
    """
    words = {v: k for k, v in _DIGITS.items()}
    words.update({"oh": "0", "o": "0", "to": "2", "too": "2", "for": "4",
                  "fore": "4", "ate": "8", "won": "1"})
    # Speech recognition hears spoken letters as the words they sound like:
    # "C I V" comes back as "see eye vee" more often than not.
    words.update({"see": "C", "sea": "C", "eye": "I", "aye": "I", "vee": "V",
                  "bee": "B", "dee": "D", "ess": "S", "are": "R", "you": "U",
                  "why": "Y", "jay": "J", "kay": "K", "cue": "Q", "queue": "Q"})
    out = []
    for token in re.findall(r"[A-Za-z]+|\d+", str(spoken or "")):
        lower = token.lower()
        if lower in words:
            out.append(words[lower])
        elif token.isdigit():
            out.append(token)
        else:
            out.append(token.upper())
    return "".join(out)


def say_days(count: int) -> str:
    """A day count, phrased for speech rather than as a bare number."""
    count = int(count)
    if count == 0:
        return "today"
    if count == 1:
        return "one day"
    return f"{count} days"
