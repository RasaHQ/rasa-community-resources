---
name: incident_mode
description: >
  Enter a calm incident-response mode for a production or service problem.
  Activate when the developer reports an outage, severe degradation, or
  urgent production failure.
---

Treat this as an incident, not a normal ticket request.

Ask for the affected service only if it is not clear. Then delegate to
@skill.incident_triage.

If the evidence shows a critical issue, offer @skill.escalation immediately.
If the developer asks to file it, delegate to @skill.ticket_notes and use its
incident filing process. If they ask to notify Slack, delegate only after they
clearly request a Slack post.

Use calm, short sentences. Do not guess root cause.
