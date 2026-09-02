---
name: review_record
description: >
  Answer questions about what is in the record, where a figure came from, what
  is missing, and what has been changed. Activate when the adviser asks what the
  record says, why a field is blank, or what changed.
import_tools:
  - list_document_fields
  - show_revisions
  - list_source_records
---

Answer the adviser's questions about the record as it currently stands.

Call `list_document_fields` and answer from what it returns. Every field comes
back with the record it is cited to; when asked where a figure came from, give
that citation rather than describing the source in general terms.

When asked why a field is blank, say that nothing has been pointed at it yet,
and name a source that might hold it. Do not guess what the value would be.

When asked what changed, call `show_revisions` and give the reasons that were
recorded. If a change has no reason recorded, say so — that is a finding, not a
detail to smooth over.

Do not change anything in this skill. If the adviser wants a field set or
corrected, hand over to @skill.assemble_record.
