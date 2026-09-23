---
name: handoff
description: >
  Give an end-of-shift on-call handoff: urgent open tickets, work in
  progress, pending approvals, and the last deployment.
  Activate when they ask for a handoff, shift summary, or to brief the next
  on-call engineer.
---

Help the developer hand off to the next on-call engineer.

Immediately call get_handoff_summary — do not ask anything first. No
authentication is required for this skill. Speak the handoff in this order:

First the urgent items — critical and high tickets still open or in progress,
with id, summary, and what state they are in.

Then anything actively being worked on.

Then pending approvals waiting on a manager.

Finish with the last deployment: project, environment, and when it happened.

Keep each part to one or two short spoken sentences. Close by asking if they
want anything repeated.
