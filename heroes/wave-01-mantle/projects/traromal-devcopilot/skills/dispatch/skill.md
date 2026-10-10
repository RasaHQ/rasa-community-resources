---
name: dispatch
description: >
  List the developer's assigned tasks and SLA status.
  Activate when they ask what tasks they have, for their queue,
  or to review today's work.
import_tools:
  - load_developer_profile
  - list_jobs
---

Help the developer review their task queue.

If developer details are missing, call load_developer_profile.

Then call list_jobs and summarize each open task in short spoken
sentences: project, issue, priority, and task reference spoken
character by character (for example D E V one zero zero one).

If the queue includes a critical-priority task, read it first and confirm the
developer can take it, offering @skill.escalation if they cannot.

Ask if they want task details, to close a task, or to order hardware.
