---
name: Note Management
description: >
  Create, edit, and delete NoteVs notes, and attach code annotations to
  them. Create/edit/annotate are conversational and unguarded; delete is
  destructive and permanent, so it requires the user to explicitly
  confirm before it runs.
import_tools:
  - create_note
  - save_note
  - add_annotation
  - delete_note
  - list_notes
  - search_notes
  - get_note
tool_constraints:
  - delete_note:
      requires_confirmation:
        enabled: true
---

Create and edit notes conversationally — "jot down a note about X" or "add
a tag to that note" should just happen, no confirmation needed. Same for
attaching a code annotation to an existing note.

`save_note` only updates the fields you pass — don't re-send fields the
user didn't ask to change.

## Writing real content

When the user asks you to create a note "about X" or write/add content to
one, actually write that content into the `content` argument — real
prose or notes on the topic, not a placeholder, not just a title with an
empty body. If they give you the exact text to use, use it verbatim. If
they only describe the topic, write something genuinely useful based on
what they told you (and the conversation so far), then let them know
you can adjust it. Same when editing: if they ask to "add a section
about Y" or "expand on Z", fetch the current content first with
`get_note` so you can append/edit it properly instead of overwriting
what was already there.

If the user references a note by title only, look it up first with
`search_notes` or `list_notes` to get its real id before calling
`save_note`, `add_annotation`, or `delete_note` — never invent an id.

## Deleting a note

`delete_note` is permanent — no undo, no trash, no soft delete. It's
gated by a required confirmation, so be specific about *which* note
(title, not just id) when you ask, e.g. "Delete the note 'Refactor auth
middleware'? This can't be undone." — not a generic "are you sure?".

If the user says something ambiguous like "delete that" and more than one
note could be "that" (e.g. multiple results from a prior search), ask
which one before even reaching the confirmation step — don't guess.

## Failure handling

If a tool call fails because the NoteVs extension isn't running, tell the
user plainly rather than surfacing a raw connection error.
