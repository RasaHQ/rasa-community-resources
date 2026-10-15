"""Shared spoken-list choice parsing for packaged skill tools."""

import re


#: How people actually pick from a spoken list.
_ORDINAL_WORDS = {
    "first": 1, "one": 1, "1st": 1,
    "second": 2, "two": 2, "2nd": 2,
    "third": 3, "three": 3, "3rd": 3,
}
_AGREEMENT = frozenset({
    "yes", "yeah", "yep", "yup", "ya", "haan", "han", "correct", "right",
    "true", "ok", "okay", "sure", "that", "one", "it", "same", "exactly",
    "please", "do", "go", "ahead", "fine", "good", "perfect", "confirm",
})


def pick(choice, count: int) -> int:
    """Turn whatever the caller said into a zero-based index, or -1.

    Callers do not answer a one-item list with "one". They say "yes", and an
    agent that then insists on a number has turned a confirmation into an
    obstacle — observed live, three turns in a row, on a list with a single
    entry.
    """
    text = str(choice or "").strip().lower()
    if text.lstrip("-").isdigit():
        return int(text) - 1

    words = [w for w in re.findall(r"\w+", text) if w]
    if any(w in {"no", "not", "nope", "neither", "wrong"} for w in words):
        return -1
    for word in words:
        if word in _ORDINAL_WORDS:
            return _ORDINAL_WORDS[word] - 1
    # An agreement is only unambiguous when there is one thing to agree to.
    if count == 1 and any(word in _AGREEMENT for word in words):
        return 0
    return -1
