"""Find and remove payment-card details in what a caller said. No Rasa imports.

The speech-to-text engine (``engines/deepgram_pci.py``) runs every transcript
through ``redact`` before Rasa sees it, so a card number the caller reads out
never reaches the tracker, the model request, Mantle memory or the server
log. The tools run ``contains_payment_secret`` over the caller's messages as
a second check.

What counts as a payment secret here, on purpose broader than a card number:

- any run of 8 or more digits, said as digits ("4111 1111"), as number words
  ("four one one one") or mixed, with spaces, hyphens, commas, full stops,
  slashes or fillers ("uh", "um") between them. This build's order numbers
  have 5 digits and its references 6, so nothing the agent needs is removed.
  A long phone number would be; the agent never asks for one.
- a run of 3 or more digits within a few words after a card cue: "card
  number", "security code", "CVV", "expiry", "expires", "the back" and the
  like. That covers a security code or an expiry date said on its own.
- in the final transcript right after one that had card digits removed, any
  run of 3 or 4 digits: a caller who reads a card in two breaths, a group at
  a time. A 5-digit order number said next is kept.

It over-removes by design: a false removal costs the caller one "please use
the link", a missed one puts a card number in the conversation record.
Apostrophes are matched straight and curly ("card's", "card’s").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PLACEHOLDER = "[card details removed]"
MIN_DIGITS_ANYWHERE = 8
MIN_DIGITS_AFTER_CUE = 3
CUE_WINDOW_WORDS = 5
# A card read in two breaths goes on in groups of four (or a 3-digit code).
# A 5-digit order number in the next breath is kept.
CONTINUATION_GROUP_DIGITS = (3, 4)

_UNITS = {"zero": 0, "oh": 0, "o": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
          "seven": 7, "eight": 8, "nine": 9}
_TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
          "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
         "ninety": 90}
_REPEAT = {"double": 2, "triple": 3}
_FILLERS = {"uh", "um", "er", "erm", "hmm"}
_SEPARATORS = {"-", ",", ".", "/", "–", "—"}

# Straight and curly apostrophes are one character class everywhere below.
_APOS = "'’‘"
_TOKEN_RE = re.compile(rf"[A-Za-z]+(?:[{_APOS}][A-Za-z]+)*|\d+|[^\sA-Za-z\d]")

# Word sequences that announce card data. Matched on lower-cased words with
# apostrophes normalised, so "card’s" and "card's" both become "card's".
_CUES = [tuple(c.split()) for c in (
    "card number", "card numbers", "card no", "card is", "card's", "card it's", "number on the card",
    "long number", "security code", "security number", "cvv", "cvc", "csc",
    "cvv2", "three digits", "three digit", "four digits", "on the back", "the back is", "expiry",
    "expiry date", "expiration", "expiration date", "expires", "expire", "exp", "valid thru",
    "valid through", "valid until",
)]


@dataclass(frozen=True)
class _Token:
    text: str
    start: int
    end: int

    @property
    def word(self) -> str:
        return re.sub(f"[{_APOS}]", "'", self.text.lower())


def _digits_of_word_run(words: list[str]) -> str | None:
    """Digits for a run of number words ("forty one" -> "41", "double four" -> "44"), or None."""
    out, i, repeat = "", 0, 1
    while i < len(words):
        w = words[i]
        if w in _REPEAT:
            repeat = _REPEAT[w]
            i += 1
            continue
        if w in _UNITS:
            out += str(_UNITS[w]) * repeat
        elif w in _TEENS:
            out += str(_TEENS[w]) * repeat
        elif w in _TENS:
            value = _TENS[w]
            if i + 1 < len(words) and words[i + 1] in _UNITS and _UNITS[words[i + 1]] > 0 \
                    and words[i + 1] not in ("oh", "o"):
                value += _UNITS[words[i + 1]]
                i += 1
            out += str(value) * repeat
        else:
            return None
        repeat = 1
        i += 1
    return out


def _is_number(tok: _Token) -> bool:
    w = tok.word
    return tok.text.isdigit() or w in _UNITS or w in _TEENS or w in _TENS or w in _REPEAT


def _runs(tokens: list[_Token]) -> list[tuple[int, int, str]]:
    """(first token, last token, digits) for every run of number tokens.

    Separators and fillers may sit between numbers but never start or end a
    run. "oh", "o", "double" and "triple" start a run only when a number
    follows straight after them ("oh four", "double one").
    """
    def can_start(i: int) -> bool:
        if not _is_number(tokens[i]):
            return False
        if tokens[i].word in ("oh", "o", "double", "triple"):
            return i + 1 < len(tokens) and _is_number(tokens[i + 1])
        return True

    runs = []
    i = 0
    while i < len(tokens):
        if not can_start(i):
            i += 1
            continue
        j, last, parts, words = i, i, [], []
        while j < len(tokens):
            tok = tokens[j]
            if _is_number(tok):
                if tok.text.isdigit():
                    if words:
                        parts.append(_digits_of_word_run(words) or "")
                        words = []
                    parts.append(tok.text)
                else:
                    words.append(tok.word)
                last = j
            elif not (tok.text in _SEPARATORS or tok.word in _FILLERS):
                break
            elif words:
                parts.append(_digits_of_word_run(words) or "")
                words = []
            j += 1
        if words:
            parts.append(_digits_of_word_run(words) or "")
        digits = "".join(parts)
        if digits:
            runs.append((i, last, digits))
        i = last + 1
    return runs


def _cue_ends(tokens: list[_Token]) -> list[int]:
    """Index of the last token of every card cue."""
    words = [t.word for t in tokens]
    ends = []
    for cue in _CUES:
        n = len(cue)
        for i in range(len(words) - n + 1):
            if tuple(words[i:i + n]) == cue:
                ends.append(i + n - 1)
    return sorted(set(ends))


def _word_distance(tokens: list[_Token], a: int, b: int) -> int:
    return sum(1 for t in tokens[a + 1:b] if re.match(r"[A-Za-z\d]", t.text))


def redact(text: str, continuation: bool = False) -> tuple[str, int]:
    """(text with card details replaced by PLACEHOLDER, number of spans replaced).

    ``continuation`` marks the transcript right after one that had card digits
    removed: then a run of 3 or 4 digits is removed too.
    """
    if not text:
        return text, 0
    tokens = [_Token(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]
    cues = _cue_ends(tokens)
    spans = []
    for first, last, digits in _runs(tokens):
        after_cue = any(c < first and _word_distance(tokens, c, first) <= CUE_WINDOW_WORDS for c in cues)
        if len(digits) >= MIN_DIGITS_ANYWHERE or (after_cue and len(digits) >= MIN_DIGITS_AFTER_CUE) or (
                continuation and len(digits) in CONTINUATION_GROUP_DIGITS):
            spans.append((tokens[first].start, tokens[last].end))
    if not spans:
        return text, 0
    out, cursor = [], 0
    for start, end in spans:
        out.append(text[cursor:start])
        out.append(PLACEHOLDER)
        cursor = end
    out.append(text[cursor:])
    return "".join(out), len(spans)


def contains_payment_secret(text: str) -> bool:
    """True when ``text`` still holds something ``redact`` would remove."""
    return redact(text)[1] > 0


def digits_only(text: str) -> str:
    """Every digit in ``text``, number words included, for scanning records for a known card number."""
    tokens = [_Token(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(text or "")]
    return "".join(d for _, _, d in _runs(tokens))
