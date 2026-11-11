---
name: job_status
description: >
  Look up SLA status and priority for a task.
  Activate for "is this task still due", urgency checks, or incident reports.
tool_constraints:
  - get_job_status:
      requires: session.job_status.job_ref
---

Help the developer check a task's SLA status.

Ask for their task reference if job_ref is not set. Accept spoken forms
like "D E V one zero zero one" and normalize to DEV1001 in memory as job_ref.

Once job_ref exists, call get_job_status.

if: session.job_status.priority == "emergency"
Treat as critical. State that this task has a two-hour SLA and that the
on-call engineer is already paged. Offer @skill.escalation to raise a
priority ticket.

if: session.job_status.priority == "standard"
State the four-hour SLA window and whether it is still on time.

if: session.job_status.priority == "planned"
State the planned window and confirm the schedule.

Keep every answer short enough for voice.
