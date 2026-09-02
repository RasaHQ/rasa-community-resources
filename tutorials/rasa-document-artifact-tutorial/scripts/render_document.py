#!/usr/bin/env python3
"""Derive the document from fixture state and print it. Optionally diff an edit.

    python3 scripts/render_document.py           print the derived document
    python3 scripts/render_document.py --diff    change one field, show the diff

No licence, no API key, no network, no model.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from docpkg import build_fixture_state, render_markdown, set_sourced_field  # noqa: E402


def show_document() -> int:
    state = build_fixture_state()
    document = render_markdown(state)
    out_dir = _ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{state.document_id}.md"
    path.write_text(document)
    print(document)
    print(f"\n--- written to {path.relative_to(_ROOT)} ({len(document.encode())} bytes) ---")
    return 0


def show_diff() -> int:
    """One edit, and everything it moved.

    The edit re-points the total portfolio value at the *cash* line of the same
    valuation record — a plausible mistake, and one that a document without a
    provenance table would hide completely. Here it moves two lines: the figure
    and its citation.
    """
    state = build_fixture_state()
    before = render_markdown(state)

    result = set_sourced_field(
        state,
        "total_value",
        source_id="custodian-extract",
        record_id="VAL-2026-08-29-PF4402",
        record_field="cash_gbp",
        reason="adviser asked to show the cash line instead",
    )
    after = render_markdown(result.state)

    print("One field changed:")
    print(f"  field  : {result.field_key}")
    print(f"  before : {result.before}")
    print(f"  after  : {result.after}")
    print(f"  cited  : {result.citation_label}")
    print("\nWhat moved in the document:\n")

    for line in difflib.unified_diff(
        before.splitlines(), after.splitlines(), "before", "after", lineterm="", n=1
    ):
        print(f"  {line}")

    print("\nNote the revision row at the foot: the history is append-only, so an")
    print("edit adds a line there as well as changing the field. That is the only")
    print("part of the document that grows when a field is corrected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(show_diff() if "--diff" in sys.argv else show_document())
