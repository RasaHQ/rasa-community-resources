---
name: engineering_briefing
description: >
  Give a complete engineering briefing across tickets, pull requests,
  reminders, approvals, and recent deployments. Activate when they ask for a
  full engineering overview, engineering dashboard, or everything important.
---

Help the developer understand the current engineering situation.

Immediately call get_engineering_briefing. Do not ask follow-up questions.

Speak in this order:

1. Critical and high tickets.
2. PRs waiting on the developer.
3. Failing CI on the developer's PRs.
4. Pending hardware or license approvals.
5. Due or overdue personal follow-ups.
6. The latest deployment.

If a section is empty, say that it is clear. Keep the response concise enough
for voice, but include identifiers character by character.
