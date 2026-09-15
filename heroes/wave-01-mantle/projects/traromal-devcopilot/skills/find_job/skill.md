---
name: find_job
description: >
  Find and select a specific task by reference or project name.
  Used as a sub-skill when another skill needs a selected task.
import_tools:
  - list_jobs
tool_constraints:
  - get_job:
      requires: session.find_job.job_ref
---

Help the developer identify which task they mean.

If they already gave a task reference, set job_ref and call get_job.

Otherwise call list_jobs, read the project names aloud, and ask which one.
Set job_ref from their choice, then call get_job.

When selected_job_ref is set, confirm the project name in one short sentence
and return to the parent skill.
