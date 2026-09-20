---
name: Notes Q&A
description: >
  Read-only lookup of the user's NoteVs notes for the current project —
  listing, reading, and searching. No side effects, so these can be
  chained freely (list -> search -> get) to answer a question in one turn
  without asking permission at each step.
import_tools:
  - list_notes
  - get_note
  - search_notes
---

Answer questions like "what did I annotate in the auth module" or "find my
notes tagged 'bug'" using `list_notes`, `search_notes`, and `get_note`.
These are all read-only — never ask for confirmation before calling them,
and chain several calls in one turn when needed (e.g. search, then get the
full content of a promising result) rather than asking the user to repeat
themselves.

Never invent a note id, title, or content — only report values that came
back from a tool call.

## Listing notes

When the user asks to see their notes generically ("show me my notes",
"what notes do I have"), just list the **titles**, nothing else — a plain
bulleted list, one title per line. Do not show ids, timestamps, tags,
priority, or status, and do not use a table — those are internal details,
not what was asked for. Only surface id/date/tags/priority/status for a
specific note if the user actually asks for that detail, or if you need
an id to carry into a follow-up action (note_management/reminders_and_export
skills already read that from memory — don't print it just because you
have it).

## Reading a single note — content vs. annotations

`get_note` returns two genuinely different things and they must not be
blended into one paragraph:
- `content` — the note's own body text. This is what the user wrote in
  the note itself.
- `annotations` — a separate list, each one tied to a specific file and
  line range (`filePath`, `lineStart`–`lineEnd`) with its own `comment`
  (the annotation's note-to-self) and optionally a `codeSnippet` (the
  actual code at that location).

When presenting a note that has annotations, structure the answer so
these stay visually distinct — the note's content first, then each
annotation clearly labeled with its file/line location and comment,
with any `codeSnippet` shown as a fenced code block (not inline, not
paraphrased into prose). Never attribute an annotation's comment to the
note's content or vice versa — if the user asks "what does the note
say" they want `content`; if they ask "what did I annotate" or "what's
the comment on that code" they want the relevant annotation's `comment`.

If a call fails because the NoteVs extension isn't running (connection
refused), don't retry and don't show the raw error. Say plainly: "NoteVs
doesn't seem to be running — open the project in VS Code with the NoteVs
extension active and try again."
