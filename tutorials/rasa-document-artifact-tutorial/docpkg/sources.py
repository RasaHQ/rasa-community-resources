"""The provenance table: where a value is allowed to have come from.

THE ONE IDEA IN THIS FILE
-------------------------
A field in this document is not a string. It is a **string plus the record it
came from**, and the two are inseparable — not by convention, but because
:class:`Sourced` has no constructor that produces a value without a citation.

That is the whole mechanism. Everything else in this package is consequence.

WHY A TYPE AND NOT A CHECK
--------------------------
The obvious design is to build the document from plain values and then run a
validator over it that asks "is everything sourced?". That design fails in a
specific and predictable way: the validator can only check the fields it knows
to look at, so the first field somebody adds without updating the validator is
unsourced and silent. The check drifts behind the document.

Here, an unsourced value cannot be constructed. There is no code path that
turns a bare string into a renderable field, so a field added next year is
sourced or it does not render — without anyone remembering to extend a list.

THE SOURCE REGISTRY
-------------------
`SOURCES` names every origin a figure in this document may claim. It is
deliberately small and deliberately closed:

    custodian-extract    what the client owns and what it is worth
    advice-factfind      what the client said about objectives and risk
    disclosure-library   approved wording, quoted verbatim

A citation naming anything else does not resolve, and a field whose citation
does not resolve renders BLANK. Not "unknown", not a plausible default, not the
last value anyone saw — blank, with the gap reported. See :mod:`docpkg.render`.

The asymmetry is deliberate. A blank in a client document is embarrassing and
someone fixes it that afternoon. A plausible wrong number in a client document
is a misrepresentation that nobody notices until it matters.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parent.parent / "data" / "source"
_REFS = Path(__file__).resolve().parent.parent / "references"


# ---------------------------------------------------------------------------
# The closed set of origins
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Source:
    """One place a figure is allowed to come from."""

    source_id: str
    label: str
    path: Path
    #: What this source is authoritative FOR. Recorded because the commonest
    #: provenance bug is not an unsourced figure — it is a figure sourced to a
    #: file that happens to contain a similar number for a different reason.
    authoritative_for: str


SOURCES: dict[str, Source] = {
    "custodian-extract": Source(
        source_id="custodian-extract",
        label="Custodian position extract",
        path=_DATA / "holdings.json",
        authoritative_for="holdings, valuations and charges",
    ),
    "advice-factfind": Source(
        source_id="advice-factfind",
        label="Client fact-find questionnaire",
        path=_DATA / "factfind.json",
        authoritative_for="objectives, risk profile and capacity for loss",
    ),
    "disclosure-library": Source(
        source_id="disclosure-library",
        label="Approved disclosure library",
        path=_REFS / "disclosures.json",
        authoritative_for="regulated wording, quoted verbatim",
    ),
}


class UnknownSource(Exception):
    """Raised when a citation names an origin that is not in :data:`SOURCES`.

    This is an exception rather than a blank because it is a *programming*
    error, not a data gap. A missing record means the document has a hole; a
    citation to a source that does not exist means somebody invented an origin,
    and inventing origins is the failure this package exists to prevent.
    """


# ---------------------------------------------------------------------------
# A value and its citation, welded together
# ---------------------------------------------------------------------------

#: The origin of a value that no external record can supply: a choice made in
#: the conversation. It is a real origin — the revision log records who chose
#: what and why — so it is declared here rather than faked by pointing a
#: negotiated field at an unrelated record.
#:
#: This constant exists because of a bug caught on this package's FIRST render.
#: `set_negotiated_field` originally cited `DISC-SCOPE-004` for want of
#: anywhere better to point, and `verify_state` immediately refused the whole
#: document: the stored value was `client_and_adviser`, the cited record said
#: `DISC-SCOPE-004`, and they did not match. The guard was right and the
#: citation was a lie. Borrowing a citation from a record that does not justify
#: the value is precisely the failure this package exists to prevent, and it
#: took ten minutes to commit it by accident.
CONVERSATION_SOURCE = "conversation"


@dataclass(frozen=True)
class Citation:
    """The pointer from a rendered figure back to the record that justifies it.

    ``source_id`` says which file, ``record_id`` says which record inside it,
    and ``field`` says which key of that record. All three are needed: a
    citation naming only the file is the documentary equivalent of "it was on
    the internet somewhere".

    The one origin that is not a file is :data:`CONVERSATION_SOURCE`, used by
    negotiated fields. It resolves through the revision log rather than through
    a JSON record — see :func:`resolve`.
    """

    source_id: str
    record_id: str
    field: str

    def __post_init__(self) -> None:
        if self.source_id == CONVERSATION_SOURCE:
            return
        if self.source_id not in SOURCES:
            raise UnknownSource(
                f"citation names source {self.source_id!r}, which is not a "
                f"declared source. Declared: {sorted(SOURCES)}"
            )

    @property
    def is_conversation(self) -> bool:
        """True for a value chosen in conversation rather than read from a file."""
        return self.source_id == CONVERSATION_SOURCE

    @property
    def label(self) -> str:
        """How the citation appears in the document's provenance table."""
        if self.is_conversation:
            return f"Chosen in conversation · {self.record_id} · {self.field}"
        return f"{SOURCES[self.source_id].label} · {self.record_id} · {self.field}"


@dataclass(frozen=True)
class Sourced:
    """A value that knows where it came from, or is not a value at all.

    There is no way to build one of these without a :class:`Citation`, and the
    citation is validated at construction. A ``Sourced`` therefore carries a
    *claim* that is checkable — and :func:`docpkg.verify.verify_state` checks
    every one of them against the actual record on disk before anything
    renders.

    ``value`` may be ``None``. That is a field that was cited but whose record
    could not be found, and it renders blank. A ``Sourced`` with a value and a
    citation that does not resolve is the dangerous case, and it is exactly
    what proof case (2) mutates to produce.
    """

    value: Any
    citation: Citation

    @property
    def is_present(self) -> bool:
        """Whether this field has anything to render at all."""
        return self.value is not None and str(self.value).strip() != ""


# ---------------------------------------------------------------------------
# Reading the sources
# ---------------------------------------------------------------------------

def load_source(source_id: str) -> dict[str, Any]:
    """Read one declared source off disk.

    No caching. These are small fixture files, and a cache here would mean the
    proof's "mutate the provenance table" case could pass against a stale copy
    read before the mutation — which would make the load-bearing negative test
    pass for the wrong reason.
    """
    if source_id not in SOURCES:
        raise UnknownSource(f"{source_id!r} is not a declared source")
    path = SOURCES[source_id].path
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every record in a source, flattened, regardless of which list holds it.

    The three fixture files group their records under different keys
    (``positions``, ``responses``, ``disclosures``, …) because that is how real
    extracts arrive. Lookup does not care about the grouping — it cares that a
    ``record_id`` is unique across the file, which the fixtures maintain.
    """
    out: list[dict[str, Any]] = []
    for key, value in payload.items():
        if key.startswith("_") or not isinstance(value, list):
            continue
        out.extend(item for item in value if isinstance(item, dict))
    return out


def resolve(citation: Citation, *, conversation: Mapping[str, Any] | None = None) -> Any:
    """Look up the value a citation points at, or ``None`` if it is not there.

    ``None`` — never a default, never a guess, never the nearest match. The
    caller's only options are to render blank or to refuse, and both of those
    are safe. Returning a plausible substitute here would defeat every guard
    downstream, because downstream cannot tell a real value from a helpful one.

    A conversation citation resolves against ``conversation`` — the mapping of
    negotiated choices carried in state — rather than against a file. Passing
    ``None`` for it means "I cannot see the conversation", which resolves to
    ``None`` and is reported as a mismatch rather than waved through. Callers
    that hold the state always pass it; see :func:`docpkg.verify.verify_state`.
    """
    if citation.is_conversation:
        if conversation is None:
            return None
        return conversation.get(citation.record_id)

    payload = load_source(citation.source_id)
    for record in _records(payload):
        if record.get("record_id") == citation.record_id:
            return record.get(citation.field)
    return None
