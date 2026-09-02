"""Measuring ASR vendors against each other on one corpus.

Rasa's ASR events carry no confidence: `NewTranscript` has exactly one field,
`text` (see `rasa/core/channels/voice_stream/asr/asr_event.py`). There is no
number to read that says "this vendor was sure". So the only quality signal
obtainable without forking the engine is **agreement**: when several independent
vendors hear the same thing, that thing is probably what was said, and where
they diverge is where a caller is about to be misunderstood.

That is what this module computes, and it is deliberately careful about the
difference between two claims:

* *"These vendors disagreed on utterance 4."* — a measurement. Always available.
* *"Vendor A is more accurate than vendor B."* — a judgement about truth, which
  needs a reference transcript. Available only where one was written down.

WER is therefore computed **only** for fixtures carrying a reference, and the
column is omitted entirely when none does. A benchmark that invents a ground
truth it does not have is worse than one that admits it has none.

Nothing here touches the network, a vendor, or a model. It is arithmetic over
strings, which is why it can be unit-tested offline.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

#: Everything that is not a word character or whitespace. Vendors punctuate and
#: capitalise to their own house style, and "Yes." vs "yes" is not a
#: disagreement about what the caller said.
_PUNCT = re.compile(r"[^\w\s']")


def normalise(text: str) -> str:
    """Reduce a transcript to what was said, dropping how it was written.

    Case, punctuation and runs of whitespace are all vendor style rather than
    caller content. Without this, every pair of vendors disagrees on every
    utterance and the matrix says nothing.
    """
    return " ".join(_PUNCT.sub(" ", (text or "").lower()).split())


def tokens(text: str) -> List[str]:
    return normalise(text).split()


# ---------------------------------------------------------------------------
# Edit distance — the one primitive both agreement and WER are built on.
# ---------------------------------------------------------------------------


def edit_distance(a: Sequence[str], b: Sequence[str]) -> int:
    """Levenshtein distance over token sequences.

    Two rows rather than a full matrix: the corpus is small, but a transcript
    is unbounded in principle and there is no reason to hold O(n*m) for a
    number that only needs the previous row.
    """
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, token_a in enumerate(a, start=1):
        current = [i]
        for j, token_b in enumerate(b, start=1):
            current.append(
                previous[j - 1] if token_a == token_b
                else 1 + min(previous[j - 1], previous[j], current[j - 1])
            )
        previous = current
    return previous[-1]


def similarity(a: str, b: str) -> float:
    """Agreement between two transcripts, 1.0 identical and 0.0 nothing shared.

    This is 1 - (edit distance / length of the longer side), so it is symmetric
    and bounded. Two vendors that both returned nothing agree completely: they
    heard the same silence, which is a real and correct agreement rather than a
    division by zero.
    """
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return 1.0
    longest = max(len(ta), len(tb))
    return 1.0 - (edit_distance(ta, tb) / longest)


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Classic WER: edit distance over reference length.

    Uncapped on purpose. A vendor that hallucinates a paragraph onto a two-word
    utterance genuinely has a WER above 1.0, and clamping it to 1.0 would hide
    the worst failure mode behind the same number as "got everything wrong".
    """
    ref = tokens(reference)
    if not ref:
        raise ValueError(
            "WER is undefined against an empty reference transcript. Callers "
            "must omit the fixture rather than score it as zero."
        )
    return edit_distance(ref, tokens(hypothesis)) / len(ref)


# ---------------------------------------------------------------------------
# One measured call.
# ---------------------------------------------------------------------------


@dataclass
class Observation:
    """What one adapter returned for one fixture, and how long it took."""

    fixture: str
    label: str
    transcript: str
    latency_ms: float
    #: Set when the adapter raised. A failed call is recorded rather than
    #: dropped: "this vendor errored on this audio" is a benchmark result.
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass
class Fixture:
    """One utterance in the corpus.

    `reference` is optional and that is the whole point — see the module
    docstring. A fixture without one still contributes to agreement.
    """

    name: str
    path: str = ""
    reference: Optional[str] = None


# ---------------------------------------------------------------------------
# The report.
# ---------------------------------------------------------------------------


@dataclass
class BenchReport:
    """Everything measured, and nothing inferred."""

    fixtures: List[Fixture] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)
    #: label -> why it was not measured. Reported, never silently dropped.
    skipped: Dict[str, str] = field(default_factory=dict)

    # -- basics -------------------------------------------------------------

    @property
    def labels(self) -> List[str]:
        """Adapters that produced at least one observation, in stable order."""
        seen: List[str] = []
        for obs in self.observations:
            if obs.label not in seen:
                seen.append(obs.label)
        return sorted(seen)

    def transcript(self, fixture: str, label: str) -> Optional[str]:
        for obs in self.observations:
            if obs.fixture == fixture and obs.label == label and obs.ok:
                return obs.transcript
        return None

    # -- agreement ----------------------------------------------------------

    def agreement_matrix(self) -> Dict[Tuple[str, str], Optional[float]]:
        """Mean pairwise agreement for every ordered pair of adapters.

        None where a pair never successfully transcribed the same fixture —
        which is not the same as agreeing zero, and must not be printed as 0.0.
        """
        labels = self.labels
        matrix: Dict[Tuple[str, str], Optional[float]] = {}
        for left in labels:
            for right in labels:
                if left == right:
                    matrix[(left, right)] = 1.0
                    continue
                scores = [
                    similarity(a, b)
                    for fixture in self.fixtures
                    if (a := self.transcript(fixture.name, left)) is not None
                    and (b := self.transcript(fixture.name, right)) is not None
                ]
                matrix[(left, right)] = statistics.fmean(scores) if scores else None
        return matrix

    def disagreement_hotspots(self) -> List[Tuple[str, float]]:
        """Fixtures ranked worst-agreement first.

        This is the output an operator actually acts on: it names the audio to
        go and listen to. Fixtures heard by fewer than two adapters are absent,
        because a lone transcript cannot disagree with anything.
        """
        rows: List[Tuple[str, float]] = []
        for fixture in self.fixtures:
            heard = [
                t for label in self.labels
                if (t := self.transcript(fixture.name, label)) is not None
            ]
            if len(heard) < 2:
                continue
            pairs = [
                similarity(heard[i], heard[j])
                for i in range(len(heard))
                for j in range(i + 1, len(heard))
            ]
            rows.append((fixture.name, statistics.fmean(pairs)))
        return sorted(rows, key=lambda row: row[1])

    # -- latency ------------------------------------------------------------

    def latency(self, label: str) -> Dict[str, float]:
        """Latency distribution for one adapter, over successful calls only.

        A failed call's duration measures how long the vendor took to say no,
        which is a different quantity and does not belong in the same summary.
        """
        samples = sorted(
            obs.latency_ms for obs in self.observations
            if obs.label == label and obs.ok
        )
        if not samples:
            return {}
        return {
            "n": float(len(samples)),
            "min": samples[0],
            "median": statistics.median(samples),
            "p95": samples[min(len(samples) - 1, int(round(0.95 * (len(samples) - 1))))],
            "max": samples[-1],
        }

    # -- accuracy, only where it is defined ---------------------------------

    @property
    def has_references(self) -> bool:
        """True when at least one fixture carries a reference transcript.

        The WER column is printed if and only if this is true. There is no
        placeholder and no zero-filled default.
        """
        return any(f.reference for f in self.fixtures)

    def wer(self, label: str) -> Optional[float]:
        """Mean WER for one adapter over referenced fixtures only.

        None when this corpus has no reference transcripts, which the caller
        must render as an absent column rather than as a score.
        """
        referenced = {f.name: f.reference for f in self.fixtures if f.reference}
        if not referenced:
            return None
        scores = [
            word_error_rate(reference, hypothesis)
            for name, reference in referenced.items()
            if (hypothesis := self.transcript(name, label)) is not None
        ]
        return statistics.fmean(scores) if scores else None
