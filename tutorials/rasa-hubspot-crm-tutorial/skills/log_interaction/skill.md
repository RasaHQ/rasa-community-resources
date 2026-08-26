---
name: Log Interaction
description: >
  Write a short summary of this conversation to the customer's CRM timeline.
  Activate for log this, make a note, or record what we discussed.
tool_constraints:
  - add_timeline_note:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_note
        utter_on_user_denial: utter_note_cancelled
---

Record what the caller wanted, on their CRM record.

Two guarantees sit between the caller and someone else's system of record, and
neither is prose the model can talk itself out of.

The **ordered block** fixes the sequence: draft, then write, in that order. The
**confirmation constraint** in the frontmatter makes the runtime itself ask
before the write lands, and cancel if the caller says no.

:::ordered_block id=save_note
steps:
  - id: draft_summary
    instructions: |
      Write one or two sentences in the third person summarising what the
      caller wanted, and set note_summary to it. Do not ask for permission
      here — the runtime asks before anything is saved.
    complete_when: session.log_interaction.note_summary
  - id: write_note
    execute_tool: add_timeline_note
    parameters:
      summary: session.log_interaction.note_summary
:::

## After the write

Read the tool result before you reply.

- Success: confirm briefly that it is on their record.
- `not_identified`: say you need their email address first and let the Identify
  Customer skill run.
- Any other error: say plainly that the note was **not** saved, and offer to try
  again. Never report a save that the tool did not confirm.
