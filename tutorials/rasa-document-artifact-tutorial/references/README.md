# `references/` — text that is quoted, never generated

Everything in this directory is **fixed wording that a model may select but
never rewrite**. It is the third grounding surface, alongside the two fixture
sources in `data/source/`.

The distinction matters more than it looks. A figure in `data/source/` is a
*value* — it can be looked up, compared, and re-derived. A reference in here is
a *sentence* — and the only safe operation on a regulated sentence is to quote
it verbatim with an identifier attached.

A model asked to "summarise the risk warning" produces something that reads
better and means something slightly different, and nobody downstream can tell
which words were approved and which were improvised. So the renderer does not
accept a risk warning as text. It accepts a **reference id**, looks the id up
here, and emits the stored wording. An id that does not resolve renders the
field blank and is reported — exactly as an unsourced figure is.

| File | What it holds |
| --- | --- |
| `disclosures.json` | Regulated paragraphs, keyed by id, with the version each was approved at |

Adding a disclosure means adding a record here, with a real `approved`
identifier. It does not mean typing a sentence into a document.
