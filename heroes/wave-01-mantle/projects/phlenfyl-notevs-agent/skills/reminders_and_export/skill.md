---
name: Reminders and Export
description: >
  Send a NoteVs note somewhere outside NoteVs — a Todoist/Google Tasks
  reminder, a Notion page, or an Obsidian vault file. All three create
  real external side effects, so all three require explicit user
  confirmation before running.
import_tools:
  - create_reminder
  - export_to_notion
  - export_to_obsidian
  - list_notes
  - search_notes
  - get_note
tool_constraints:
  - create_reminder:
      requires_confirmation:
        enabled: true
  - export_to_notion:
      requires_confirmation:
        enabled: true
  - export_to_obsidian:
      requires_confirmation:
        enabled: true
---

These three tools all leave NoteVs — a Todoist/Google Tasks task, a Notion
page, or an Obsidian file that exists independently of the note
afterward. Every one of them requires confirmation — don't promise the
user it'll happen before the confirmation step actually completes.

Before calling any of these, make sure you already have a real note id —
from a prior `list_notes`, `search_notes`, or `get_note` call in this
conversation. If the user references a note by title only ("remind me
about the auth note tomorrow"), look it up first rather than inventing an
id.

Use `create_reminder` for the reminder/task action (not a `set_*` name —
Maestro reserves that prefix for its own tools).

## Confirmation copy

Be concrete about what's about to happen and where, e.g.: "Create a
Todoist task 'Refactor auth middleware' due 2026-08-01?" or "Export
'Refactor auth middleware' to Notion — this will create or update a page
there. Proceed?" — not a generic "are you sure?".

## Preconditions the tools themselves enforce

These surface as tool errors if unmet — pass them through to the user
rather than retrying silently:
- `create_reminder` needs Todoist or Google Tasks connected (Settings →
  Integrations → Tasks).
- `export_to_notion` needs Notion connected (Settings → Integrations →
  Exporting).
- `export_to_obsidian` needs Obsidian configured (Settings → Integrations
  → Exporting).

## Failure handling

If the NoteVs extension itself isn't reachable, tell the user plainly
rather than surfacing a raw connection error.
