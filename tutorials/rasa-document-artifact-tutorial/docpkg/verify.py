"""The guard: every figure is re-checked against its record before anything renders.

WHY A SECOND CHECK AT ALL
-------------------------
:mod:`docpkg.edits` already guarantees that a value entering state came from a
record — it looked the value up itself. So why check again at render time?

Because the record can change after the value entered state. A state object
built this morning, carried through a conversation, and rendered this afternoon
holds figures that were true when they were read. If the custodian extract is
corrected, restated, or tampered with in between, the document would otherwise
report this morning's numbers under this afternoon's citations — every figure
footnoted, every footnote wrong.

That is the failure this guard exists for, and it is the one proof case (2)
demonstrates: mutate the provenance table, and the renderer REFUSES rather than
emitting a document whose citations no longer hold.

FAIL CLOSED, AND SAY WHY
------------------------
A mismatch does not render blank. Blank is the correct answer for a field that
was never sourced; a field whose citation has *stopped agreeing* is a different
condition, and quietly blanking it would hide a changed record behind what
looks like an incomplete document. So the whole render refuses, names every
disagreeing field, and exits non-zero.
"""

from __future__ import annotations

from dataclasses import dataclass

from docpkg.sources import resolve
from docpkg.state import DocumentState


@dataclass(frozen=True)
class Mismatch:
    """One field whose stored value no longer matches the record it cites."""

    field_key: str
    citation_label: str
    stored: str
    found: str | None

    def describe(self) -> str:
        found = "no such record" if self.found is None else repr(self.found)
        return (
            f"  {self.field_key}: document says {self.stored!r}, "
            f"source says {found}\n"
            f"      cited as: {self.citation_label}"
        )


class ProvenanceBroken(Exception):
    """Raised when at least one figure no longer agrees with its source.

    Carries every mismatch rather than the first, because an operator whose
    extract was restated needs to see the blast radius in one pass, not one
    field per run.
    """

    def __init__(self, mismatches: tuple[Mismatch, ...]) -> None:
        self.mismatches = mismatches
        detail = "\n".join(m.describe() for m in mismatches)
        super().__init__(
            f"REFUSED: {len(mismatches)} figure(s) no longer match the record "
            f"they cite. The document was not rendered.\n{detail}"
        )


def _comparable(value: object) -> str:
    """Normalise for comparison without being clever about it.

    Numbers arrive from JSON as int or float and are stored as they were found,
    so ``486210.44`` and ``"486210.44"`` must compare equal. Anything looser
    than string-equality-after-str() would start accepting values that merely
    look similar, which is the opposite of the job.
    """
    return str(value).strip()


def verify_state(state: DocumentState) -> tuple[Mismatch, ...]:
    """Re-resolve every citation in state and report the ones that disagree.

    Returns the mismatches rather than raising, so callers can choose: the
    renderer raises, while the proof script wants to print them. A field with
    no stored value is skipped — an absent field has nothing to disagree with,
    and it is already reported by ``missing_required``.
    """
    # The negotiated choices, as the conversation citations resolve against
    # them. Built from state itself, so a negotiated value cannot verify against
    # anything other than what state actually holds.
    conversation = {
        key: held.value
        for key, held in state.values.items()
        if held.citation.is_conversation
    }
    out: list[Mismatch] = []
    for key, held in state.values.items():
        if not held.is_present:
            continue
        found = resolve(held.citation, conversation=conversation)
        if found is None or _comparable(found) != _comparable(held.value):
            out.append(
                Mismatch(
                    field_key=key,
                    citation_label=held.citation.label,
                    stored=_comparable(held.value),
                    found=None if found is None else _comparable(found),
                )
            )
    return tuple(out)


def require_intact_provenance(state: DocumentState) -> None:
    """Raise :class:`ProvenanceBroken` unless every figure still matches.

    This is the guard proof case (2) removes. It is one call, in one place —
    :func:`docpkg.render.render_markdown` — and removing it is a one-line edit,
    which is exactly why the test that catches its removal has to exist.
    """
    mismatches = verify_state(state)
    if mismatches:
        raise ProvenanceBroken(mismatches)
