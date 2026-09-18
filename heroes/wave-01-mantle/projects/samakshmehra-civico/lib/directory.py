"""The ward directory — what this project has instead of a geocoder.

A caller says where the problem is. The only thing the system does with that
answer is decide which ward owns it, because a ward is what maps to an officer
and a work queue. A ward is a neighbourhood, not a point, so the right lookup
is a table of neighbourhoods, not a map of the world.

This is twenty-nine rows we ship. Matching a mangled phrase against known
strings is a solved problem; matching it against every place on Earth is not,
and the earlier version of this project spent most of its complexity losing
that fight. Nothing here touches the network, so nothing here can time out,
rate-limit, or route a caller in Ghaziabad to Vijayawada.

Everything the caller says beyond the locality — "in front of the Juniper
Heights main gate" — is kept verbatim as text and printed on the work order. A
field crew navigates by landmark better than by coordinate.
"""

from __future__ import annotations

import functools
import json
import os
import re
from difflib import SequenceMatcher

from lib.paths import data_dir

#: How close a locality name has to sound before the directory accepts it.
#: 0.72 was chosen against the mangled place names in this project's ASR
#: transcripts: it accepts "vishali" and "indrapuram", and rejects "vijayawada".
THRESHOLD = float(os.getenv("CIVICO_MATCH_THRESHOLD", "0.72"))

#: How far below the best match a runner-up may sit and still be worth offering.
_BAND = 0.12

_NUMBER_WORDS = {
    "zero": "0", "oh": "0", "o": "0", "nought": "0",
    "one": "1", "won": "1",
    "two": "2", "to": "2", "too": "2",
    "three": "3", "tree": "3",
    "four": "4", "for": "4", "fore": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8", "ate": "8",
    "nine": "9",
    "double": "__DOUBLE__",
    "triple": "__TRIPLE__",
}

#: Words that carry no location information. Stripped before matching so that
#: "near the pothole in Vaishali" scores on "vaishali", not on the filler.
_FILLER = frozenset({
    "near", "at", "in", "on", "the", "a", "an", "of", "by", "to", "from",
    "front", "behind", "opposite", "beside", "next", "outside", "inside",
    "my", "our", "its", "this", "that", "there", "here", "area", "side",
    "please", "actually", "basically", "like", "um", "uh", "so", "and",
    "is", "it", "we", "i", "am", "are", "was", "pin", "code", "pincode",
    "sector", "block", "number", "no", "house", "flat", "street", "road",
    "lane", "gali", "colony", "society", "ke", "paas", "wali", "mein",
})


@functools.lru_cache(maxsize=1)
def _directory() -> dict:
    with open(data_dir() / "wards.json", encoding="utf-8") as handle:
        return json.load(handle)


def municipality() -> str:
    return _directory()["municipality"]


def general_cell() -> dict:
    """Where a complaint goes when no ward can be identified.

    Not an error path. A human operator who cannot place an address still takes
    the complaint and sends it to the grievance cell; so does this.
    """
    return dict(_directory()["general_cell"])


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower()).strip()


def _words(text: str) -> list[str]:
    return [w for w in _normalize(text).split() if w]


def digits_from_speech(text: str) -> list[str]:
    """Pull runs of digits out of speech, spoken or written.

    "two zero one zero one zero" and "201010" both come back as ["201010"];
    "double nine eight" becomes ["998"]. Returns each contiguous run
    separately so a caller who says a PIN and a house number does not end up
    with the two glued together.
    """
    runs: list[str] = []
    current = ""
    repeat = 0

    for token in _words(text):
        mapped = _NUMBER_WORDS.get(token)
        if mapped == "__DOUBLE__":
            repeat = 2
            continue
        if mapped == "__TRIPLE__":
            repeat = 3
            continue
        if mapped is None and token.isdigit():
            mapped = token
        if mapped is None:
            if current:
                runs.append(current)
                current = ""
            repeat = 0
            continue
        current += mapped * max(repeat, 1) if len(mapped) == 1 else mapped
        repeat = 0

    if current:
        runs.append(current)
    return runs


def extract_pincode(text: str) -> str:
    """The six-digit run in what the caller said, or an empty string.

    Exactly six — a five- or seven-digit run is something else, and guessing
    which six of seven digits were meant is how you route someone to the wrong
    ward without ever telling them.
    """
    for run in digits_from_speech(text):
        if len(run) == 6:
            return run
    return ""


def extract_phone(text: str) -> str:
    """The ten-digit run in what the caller said, or an empty string.

    A leading 0 or a +91 country code is stripped first, which is how people
    actually read their own number out.
    """
    for run in digits_from_speech(text):
        stripped = run
        if len(stripped) == 13 and stripped.startswith("91"):
            stripped = stripped[2:]
        if len(stripped) == 11 and stripped.startswith("0"):
            stripped = stripped[1:]
        if len(stripped) == 12 and stripped.startswith("91"):
            stripped = stripped[2:]
        if len(stripped) == 10:
            return stripped
    return ""


def _score(name: str, spoken_words: list[str]) -> float:
    """Best similarity between a directory name and any phrase the caller said.

    Slides a window the length of the name across what was said, so "there is a
    pothole in indrapuram near the market" is scored on "indrapuram" alone
    rather than being diluted by the rest of the sentence.
    """
    target = _normalize(name)
    target_len = len(target.split())
    if not target or not spoken_words:
        return 0.0

    best = 0.0
    for size in {max(1, target_len - 1), target_len, target_len + 1}:
        for start in range(0, max(1, len(spoken_words) - size + 1)):
            window = " ".join(spoken_words[start:start + size])
            if not window:
                continue
            if window == target:
                return 1.0
            best = max(best, SequenceMatcher(None, target, window).ratio())
    return best


def find_ward(spoken: str) -> dict:
    """Match what the caller said against the ward directory.

    Returns ``{matches, pincode, matched_on}``. ``matches`` is at most three
    candidates, best first, each with everything needed to route and to read
    back aloud. An empty list is a normal outcome, not a failure.

    A locality name wins over a PIN code when both are present. People misread
    their own PIN far more often than they misname the neighbourhood they live
    in, and a PIN in this city spans several wards anyway.
    """
    spoken = str(spoken or "").strip()
    pincode = extract_pincode(spoken)

    # Number words already became the PIN; leaving them in only adds noise.
    residue = [w for w in _words(spoken)
               if w not in _FILLER and w not in _NUMBER_WORDS and not w.isdigit()]

    scored: list[tuple[float, dict]] = []
    for row in _directory()["wards"]:
        names = [row["locality"], *row.get("aliases", [])]
        best = max((_score(name, residue) for name in names), default=0.0)
        if best >= THRESHOLD:
            scored.append((best, row))

    if scored:
        scored.sort(key=lambda pair: (-pair[0], pair[1]["locality"]))
        # Only offer the near-misses when the best match is itself uncertain.
        # "Indirapuram" also scores 0.76 against "Govindpuram", and reading
        # both back to someone who pronounced their own neighbourhood clearly
        # is how a confident answer gets turned into a confusing question.
        floor = max(THRESHOLD, scored[0][0] - _BAND)
        matches = [_as_match(row, score, "name", pincode)
                   for score, row in scored[:3] if score >= floor]
        return {"matches": matches, "pincode": pincode, "matched_on": "name"}

    if pincode:
        by_ward: dict[str, dict] = {}
        for row in _directory()["wards"]:
            if row["pincode"] != pincode:
                continue
            existing = by_ward.get(row["ward_id"])
            if existing is None:
                by_ward[row["ward_id"]] = _as_match(row, 1.0, "pincode", pincode)
            else:
                # One PIN covers several localities in the same ward. Offer the
                # ward once, named by all of them, rather than three near-
                # identical options the caller has to choose between.
                existing["label"] = f"{existing['label']} / {row['locality']}"
        if by_ward:
            return {"matches": list(by_ward.values())[:3],
                    "pincode": pincode, "matched_on": "pincode"}

    return {"matches": [], "pincode": pincode, "matched_on": "none"}


def _as_match(row: dict, score: float, matched_on: str, spoken_pin: str) -> dict:
    return {
        "ward_id": row["ward_id"],
        "label": row["locality"],
        "locality": row["locality"],
        "pincode": row["pincode"],
        "zone": row["zone"],
        "officer_name": row["officer_name"],
        "officer_contact": row["officer_contact"],
        "score": round(score, 3),
        "matched_on": matched_on,
        # Surfaced, never acted on. If the caller's PIN disagrees with the
        # directory's, that is something to mention, not something to resolve
        # by silently preferring one of them.
        "pincode_differs": bool(spoken_pin and spoken_pin != row["pincode"]),
    }


def ward_by_id(ward_id: str) -> dict | None:
    for row in _directory()["wards"]:
        if row["ward_id"] == ward_id:
            return _as_match(row, 1.0, "id", "")
    if ward_id == _directory()["general_cell"]["ward_id"]:
        cell = general_cell()
        cell.update({"locality": cell["label"], "pincode": "", "score": 1.0,
                     "matched_on": "id", "pincode_differs": False})
        return cell
    return None
