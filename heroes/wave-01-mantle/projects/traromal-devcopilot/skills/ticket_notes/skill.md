---
name: ticket_notes
description: >
  Manage the developer's support tickets by voice: list assigned tickets,
  update or reopen their status, add notes, file incident reports from spoken
  notes, and give a standup or daily briefing.
  Activate when they ask about their tickets or tasks, want to update,
  annotate, or check one, describe a bug or incident in their own words, ask
  for a briefing, or run their standup.
tool_constraints:
  - file_support_ticket:
      requires: session.ticket_notes.summary_verified
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_ticket
        utter_on_user_denial: utter_ticket_cancelled
      on_success: utter_ticket_filed
  - update_ticket_status:
      requires: session.ticket_notes.selected_ticket_id
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_status_update
        utter_on_user_denial: utter_status_update_cancelled
      on_success: utter_status_updated
  - add_ticket_comment:
      requires: session.ticket_notes.comment_text
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_comment
        utter_on_user_denial: utter_comment_cancelled
      on_success: utter_comment_added
---

Help the developer manage their support tickets by voice. From their first
request, set mode to list, update, reopen, comment, standup, briefing, or
file, then follow the matching section below.

if: session.ticket_notes.mode == "briefing"
Immediately call get_daily_briefing — do not ask anything first. Read aloud
how many tickets are open and in progress, then the at-risk tickets with
their summaries and severities. Keep it short.

if: session.ticket_notes.mode == "standup"
Immediately call get_standup — do not ask anything first. Speak three short
parts in order: what was wrapped up, what is in progress right now, and any
blockers with their severities.

if: session.ticket_notes.mode == "list"
Call list_assigned_tickets. Read each ticket aloud with its id, summary,
severity, and status. Then ask if they want to update any of them.

if: session.ticket_notes.mode == "update"
Call list_assigned_tickets if the tickets are not already in view. Ask which
ticket and set selected_ticket_id. Ask for the new status, in progress or
done, and set new_status. Read back the ticket and the new status, then call
update_ticket_status.

if: session.ticket_notes.mode == "reopen"
Call list_assigned_tickets if the tickets are not already in view. Ask which
ticket and set selected_ticket_id. Explain the ticket will go back to open,
ask why it is reopening, and set new_status to open. Read back the ticket and
the reason, then call update_ticket_status.

if: session.ticket_notes.mode == "comment"
Call list_assigned_tickets if the tickets are not already in view. Ask which
ticket to annotate and set selected_ticket_id. Ask what the note should say
and set comment_text. Read the note back, then call add_ticket_comment.

if: session.ticket_notes.mode == "file"
Let them talk freely first — do not interrupt or tidy their words. Once they
have described the incident, invoke @block.collect_ticket_details.

:::ordered_block id=collect_ticket_details
steps:
  - id: capture_notes
    instructions: |
      The developer has already described the incident in their message.
      Capture exactly what they said in incident_notes without editing it.
      Do not ask them to repeat or rephrase — just save their words as-is.
    complete_when: session.ticket_notes.incident_notes
  - id: write_summary
    instructions: |
      From incident_notes, write one plain-language sentence that captures
      the technical problem. Set summary.
    complete_when: session.ticket_notes.summary
  - id: pick_severity
    instructions: |
      Choose the best severity from critical, high, medium, or low and ask
      the developer to confirm it. Set severity.
    complete_when: session.ticket_notes.severity
  - id: pick_system
    instructions: |
      Ask which system or service is affected, for example the auth service,
      API, mobile app, or CI pipeline. Set system.
    complete_when: session.ticket_notes.system
  - id: capture_repro
    instructions: |
      Ask for the steps to reproduce. If they do not have steps, set
      repro_steps to none. Otherwise capture a few short steps.
    complete_when: session.ticket_notes.repro_steps
  - id: verify_summary
    instructions: |
      Read back summary, severity, system, and repro_steps. If the developer
      confirms, set summary_verified to true. If something is wrong, fix that
      field and re-summarize.
    complete_when: session.ticket_notes.summary_verified == True
:::

## Submit

When summary_verified is true, call file_support_ticket with the confirmed
fields. Speak the ticket id character by character, like T K T one zero zero
five.

## Close

Confirm in one or two short sentences suitable for voice.
