---
name: job_close
description: >
  Close a completed task with diagnosis, resolution, tools used, and hours.
  Activate when they say a task is done, complete, or fixed.
import_tools:
  - list_jobs
tool_constraints:
  - close_work_order:
      requires: session.job_close.details_verified
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_job_close
        utter_on_user_denial: utter_job_close_cancelled
      on_success: utter_job_closed
---

Help the developer close a completed task. Accuracy first — collect details in
order, then confirm before close.

Once they say the task is done, invoke @block.collect_job_details

:::ordered_block id=collect_job_details
steps:
  - id: fetch_jobs
    execute_tool: list_jobs
  - id: select_job
    instructions: |
      Show the developer's tasks from the tool result.
      Ask which one they completed. Set job_ref to the full reference.
    complete_when: session.job_close.job_ref
  - id: collect_diagnosis
    instructions: |
      Ask what they found and did. Set diagnosis to a short summary.
    complete_when: session.job_close.diagnosis
  - id: collect_resolution
    instructions: |
      Ask how the task was resolved: fixed, replaced a component, no issue
      found, or deferred. Set resolution.
    complete_when: session.job_close.resolution
  - id: collect_labor
    instructions: |
      Ask how many hours they spent on it. Set labor_hours.
    complete_when: session.job_close.labor_hours
  - id: collect_parts
    instructions: |
      Ask which tool, license, or component, if any, was used. If none,
      set part_no to none.
    complete_when: session.job_close.part_no
  - id: verify_summary
    instructions: |
      Read back job_ref, diagnosis, resolution, labor_hours, and part_no.
      If the developer confirms, set details_verified to true.
      If something is wrong, correct the field and re-summarize.
    complete_when: session.job_close.details_verified == True
:::

## Submit

When details_verified is true, call close_work_order with the collected
fields. Speak the task reference character by character.

## Close

Confirm in one or two short sentences suitable for voice.
