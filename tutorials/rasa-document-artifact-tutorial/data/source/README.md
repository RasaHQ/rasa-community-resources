# Fixture data — entirely fictional

Every person, company, holding, valuation, and account in this directory is
**invented for this tutorial**. Nothing corresponds to a real person, a real
business, a real security, or any real portfolio. Do not replace these records
with real customer data — the repo-wide `fictional-data` lint rejects real
institutions and unreserved email domains, and this catalog is public.

Two sources sit here on purpose. The tutorial teaches that every figure in a
generated document must trace to a source record, so it needs more than one
record set to make provenance visible:

- `factfind.json` — the client profile a document's narrative fields cite.
- `holdings.json` — the positions its figures cite.

`references/disclosures.json` is a third surface and a different kind: approved
wording a document quotes verbatim, not data it computes from. It is fictional
too, and is **not** regulatory text from any jurisdiction — do not treat it as
compliant language for any real document.
