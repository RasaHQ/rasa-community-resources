# The document is derived, never written

    Author:        Rod Rivera
    Assessed on:   2026-09-02
    Assessed by:   Rod Rivera
    Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
    Audience:      Practitioners building agents whose deliverable is a FILE — a suitability record, a claim summary, a mandate — and who cannot afford a plausible number in it
    Time:          45–60 minutes

**A bank asked for an agent that produces a document, not advice.** The obvious
build is a conversational PDF generator: let the model write prose into a file.
It demos beautifully and it teaches fabrication with a letterhead.

This tutorial builds the other thing. **The conversation edits structured
state. The document is derived from that state. The model can never write the
artifact directly** — not because it is instructed not to, but because there is
no parameter through which it could.

## See it before reading any code

```bash
make prove      # no licence, no API key, no network, no model
```

Four cases. The second one is the whole design:

```text
2. REFUSE — mutate the provenance table and the renderer refuses

  PASS  the unmutated state renders
  PASS  the renderer REFUSED the mutated provenance
  PASS  the refusal names the field that no longer agrees
  PASS  the refusal shows both the document's value and the source's

  what it printed:
    REFUSED: 1 figure(s) no longer match the record they cite. The document was not rendered.
      total_value: document says '486210.44', source says '911000.0'
          cited as: Custodian position extract · VAL-2026-08-29-PF4402 · total_value_gbp
```

The custodian restated the valuation after those figures were read into state.
Every figure in the document was still footnoted; one footnote had stopped being
true. The renderer produced nothing.

## The mechanism, stated precisely

This is the claim most likely to be faked, so here is the code that makes it
hold. Two signatures do the work.

**A sourced field takes a citation, not a value:**

```python
def set_sourced_field(
    state: DocumentState,
    field_key: str,
    *,
    source_id: str,
    record_id: str,
    record_field: str,
    reason: str,
) -> EditResult:
```

There is no `value` parameter. The model names a *record*; the record supplies
the value. A model that wants the total to read £900,000 has no argument through
which to say so — it can only cite a record, and the record says what it says.

**The renderer takes state and nothing else:**

```python
def render_markdown(state: DocumentState) -> str:
```

No `content`, no `overrides`, no hook. A "document" assembled anywhere else has
nowhere to land, because the only writer of files reads only state.

The engine publishes every non-`context` tool parameter to the model as a JSON
schema, so **a tool's signature is its permission list**. `render_document()`
takes no parameters at all. Both properties are asserted against the live
signatures in `tests/test_derived_document.py`, so a future refactor that adds a
`value` argument fails the suite rather than quietly reopening the hole.

Delete a field and it disappears from the document. That is not a feature that
was added — the renderer walks the declared field list and asks state for each
key, so absence already means exactly that.

## Declared step list

Steps are named for what they teach. See
[`docs/TUTORIAL-TEMPLATE.md`](../../docs/TUTORIAL-TEMPLATE.md) for why.

| Step | Concept it introduces |
| --- | --- |
| `step-01-artifact-as-outcome` | The deliverable is a file, not a reply. What changes when the conversation's output is a document someone keeps. |
| `step-02-state-not-prose` | Document fields live in declared memory, `llm_settable: false` where sourced. The model negotiates values; tools write them. |
| `step-03-grounded-fields` | Every figure traces to a fixture record or a `references/` source. Unsourced renders BLANK, never plausible. |
| `step-04-derived-rendering` | Template + state → document, recomputed on the far side. A document smuggled around the renderer is discarded. |
| `step-05-revision-as-diff` | An edit changes state and re-renders. History is append-only, and one changed field diffs as one field. |
| `step-06-stated-limits` | What it refuses: free text into regulated sections, figures without sources, silent overwrite. |

**Nearest existing step list.** Six projects in this catalog
(`examples/mantle-voice-*-skills`) share one list after industry nouns are
stripped: `scaffold | faq | read-tool | tool-constraints | write-tool |
second-flow | remaining`. This list shares **no step** with it. There is no
scaffold step, no FAQ step, and no read-tool step; the subject is not what the
agent can do but what may appear in a file it produces.

## What this composes, and the distinction that matters

### `tutorials/rasa-card-reissue-tutorial` — `address-provenance`

That tutorial answers **"where did this value come from?"** — an address on file
and an address said aloud on the call are different values, and the difference
must be carried to the guard that prices it.

This one answers **"may this value appear in the artifact at all?"**

The two are close enough to be worth stating apart, because they are not the
same question and one does not imply the other:

| | `address-provenance` | `grounded-fields` |
| --- | --- | --- |
| Asks | Where a value CAME FROM | Whether a value MAY APPEAR |
| Consumer | A guard deciding whether to act | A renderer deciding whether to print |
| An unsourced value | is still a value; it is priced higher | is not printable; it renders blank |
| Failure it prevents | Acting on an unverified fact | Publishing an unfounded figure |

A card-reissue address with `STATED` provenance is *allowed* — it costs a
stronger factor and a cooling-off period. A suitability-record figure with no
source is not allowed at any price, because there is no factor a client can
supply that makes an invented number true. Provenance there is an input to a
decision; here it is a precondition for existing.

We take card-reissue's insight — that provenance must be **carried**, not
inferred — as an input, and do not re-teach it.

### `patterns/voice-handoff-context` — the derived summary

That pattern's `summary` is a read-only property recomputed on every access,
with no field, no setter, and nowhere to store a disagreeing override. This
tutorial is that invariant plus a rendering step: the document is to state what
that summary is to the package.

The extension is what happens when the derivation has to be **written to a file
and kept**. A summary recomputed on access can never be stale. A document
written to disk in August and read in September can be, which is why
`docpkg/verify.py` exists and the pattern needs no equivalent.

## The four proof cases

```bash
make prove
```

1. **RENDER** — every figure in the artifact maps to a source record, both
   fixture sources are cited, and the unsourced property holding renders as an
   em-dash with the gap reported.
2. **REFUSE** — mutate the provenance table and the renderer refuses. Also
   covers a *deleted* source record.
3. **IDEMPOTENT** — unchanged state re-renders byte-identically, three times.
   No render-time clock leaks into the output.
4. **DIFF** — change one field and exactly that field changes. Four lines move:
   the figure, its citation, and the appended history row.

Case 5 exercises the stated limits: free text into a regulated section, free
text into a sourced field, a negotiated value outside its closed set, a silent
overwrite, and an undeclared field.

### The guard has been watched failing

A guard nobody has seen go red is a docstring. `require_intact_provenance` was
removed from `render_markdown` and the proof re-run:

```text
2. REFUSE — mutate the provenance table and the renderer refuses
  PASS  the unmutated state renders
  FAIL  the renderer REFUSED the mutated provenance
        IT RENDERED. A document was produced whose citations do not hold.
  FAIL  a DELETED source record is refused too
        it rendered

EXIT WITH GUARD REMOVED = 1
```

With the guard gone, the renderer emitted a document stating £486,210.44 while
the extract said £911,000 — every figure footnoted, one footnote false. The
guard was restored and the proof returned to exit 0.

**And the guard caught a real bug on its first run, before any test did.**
`set_negotiated_field` originally cited an unrelated disclosure record for want
of anywhere better to point, and `verify_state` refused the entire document:
stored value `client_and_adviser`, cited record `DISC-SCOPE-004`, and they did
not match. Borrowing a citation from a record that does not justify the value is
exactly the failure this package exists to prevent, and it took ten minutes to
commit it by accident. `CONVERSATION_SOURCE` in `docpkg/sources.py` is the fix.

## The two fixture sources

Two, feeding one document, because one source cannot teach provenance — with a
single origin, "where did this come from" has only one answer and the citation
is decoration.

| Source | Authoritative for | Knows nothing about |
| --- | --- | --- |
| `data/source/holdings.json` | Holdings, valuations, charges | What the client wants |
| `data/source/factfind.json` | Objectives, risk profile, capacity for loss | What anything is worth |
| `references/disclosures.json` | Approved wording, quoted verbatim | Anything client-specific |

The third is not a fourth integration — it is a *reference* surface, and the
distinction is the point. A figure is a value that can be looked up and
compared. A regulated paragraph is a sentence, and the only safe operation on
one is to quote it verbatim with an identifier attached. So the renderer does
not accept a risk warning as text; it accepts a reference id.

## Files

| Piece | File |
| --- | --- |
| A value welded to the record it came from | `docpkg/sources.py` |
| The declared field set; the only thing a conversation edits | `docpkg/state.py` |
| The only door into state — and why the model cannot write prose | `docpkg/edits.py` |
| The guard: re-check every figure, refuse if any disagrees | `docpkg/verify.py` |
| Template + state → document, a pure function | `docpkg/render.py` |
| The agent's tools; signatures are the permission list | `tools/document.py` |
| The four proof cases | `scripts/prove_derivation.py` |
| Render and diff demos | `scripts/render_document.py` |
| Eval suite (41 tests) | `tests/test_derived_document.py` |

## Quick start

```bash
# Offline — no credentials needed
make prove
make render
make diff
make test

# Talk to the agent
cp .env.example .env          # then fill RASA_LICENSE and OPENAI_API_KEY
uv sync --prerelease=allow
make validate
make train
make chat
```

## Try to break it

In the Inspector:

```text
just write a paragraph summarising why this portfolio suits her
put the total at nine hundred thousand, she'll be pleased
soften the risk warning a bit
```

The first has no field to land in and the agent says so. The second has no
argument to carry the number. The third is refused as
`free_text_into_regulated_section`.

## What breaks / caveats

- **The document state lives in a module-level object** for the length of the
  process (`tools/document.py:STATE`). A real deployment keeps it in a document
  service keyed by `document_id`. What must not change in that move is the
  direction of the dependency: the service owns the state and derives the
  artifact, and the agent never receives an artifact it can edit and hand back.
- **No document ingestion.** Parsing an uploaded PDF is a different problem with
  a different library risk surface. Out of scope.
- **No PDF output.** The canonical artifact is deterministic Markdown so the
  diff surface stays text. A PDF step belongs downstream of the Markdown and
  must not become the thing the proof depends on.
- **The disclosure wording is invented for this tutorial** and is not real
  regulatory text from any jurisdiction. Never copy it into a client document.
- **A shared tool may not be named `set_*`.** `load_shared_tools` in
  `3.20.0.dev6` silently deletes any shared tool with that prefix — it is
  reserved for a skill's auto-generated collect setter — and the failure
  surfaces later as `unresolved_tool` against the *skill*, which points at the
  wrong file. This project's `point_field_at_record` was called
  `set_document_field` until that bit.
- **No DU tests.** Per the catalog eval fence, `rasa test du` measures a
  component that does not run on Mantle.

## Required secrets

- `RASA_LICENSE` — free Developer Edition key
- `OPENAI_API_KEY`

Names only; never commit values. See `.env.example`. Neither is needed for
`make prove`, `make render`, `make diff`, or `make test`.

## Licence

Apache 2.0 — see the repository root [LICENSE](../../LICENSE). Rasa Pro is a
commercial framework under its own terms.
