"""Shared spoken-list choice parsing for packaged skill tools."""

import re


#: How people actually pick from a spoken list.
_ORDINAL_WORDS = {
    "first": 1, "one": 1, "1st": 1,
    "second": 2, "two": 2, "2nd": 2,
    "third": 3, "three": 3, "3rd": 3,
    "fourth": 4, "four": 4, "4th": 4,
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
    if count < 1 or re.search(r"(?<!\w)-+\s*[0-9]", text):
        return -1
    words = [w for w in re.findall(r"\w+", text) if w]
    if any(w in {"no", "not", "nope", "neither", "wrong", "minus", "negative", "or", "and"}
           for w in words):
        return -1
    choices = set()
    for word in words:
        # In "the fourth one", "one" is a noun, not a second selection.
        if word in _ORDINAL_WORDS and word != "one":
            choices.add(_ORDINAL_WORDS[word])
        elif re.fullmatch(r"[0-9]+", word):
            digits = word.lstrip("0") or "0"
            if len(digits) > len(str(count)):
                return -1
            choices.add(int(digits))
    if choices:
        if len(choices) != 1:
            return -1
        number = choices.pop()
        return number - 1 if 1 <= number <= count else -1
    if [w for w in words if w not in {"the", "option", "number", "please"}] == ["one"]:
        return 0
    # An agreement is only unambiguous when there is one thing to agree to.
    allowed = _AGREEMENT | {"the", "is", "option", "number"}
    if count == 1 and set(words) <= allowed and any(word in _AGREEMENT for word in words):
        return 0
    return -1
