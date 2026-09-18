---
name: Escalate a Complaint
description: >
  Raise an overdue complaint to the next authority. Activate when a caller
  wants a complaint escalated, wants to speak to someone senior about it, or
  says nothing has been done past the promised date.
complete_when: session.escalate.escalated == True
import_tools:
  - look_up_complaint
tool_constraints:
  - escalate_complaint:
      # Nothing is raised until a real complaint has been identified. The tool
      # checks the clock; this checks that there is something to check.
      requires: session.escalate.complaint_id
      # No on_success: the caller needs to hear which authority now holds it
      # and the new date, and a verbatim line ends the turn before the model
      # can say either.
      on_failure: utter_cannot_escalate
  - look_up_complaint:
      on_failure: utter_reference_not_found
---

:::ordered_block id=main
name: escalate
description: >
  Raise a complaint that has gone past its target date to the next level.
steps:
  - id: identify
    instructions: |
      Call `look_up_complaint` with the reference of the complaint being
      discussed.

      Do this even when it was just looked up a moment ago in another skill.
      Skill memory does not carry across a handoff — this skill starts with
      nothing, so the reference has to be loaded here before anything can be
      raised. The lookup is cheap and local.

      Only if there is no reference in the conversation at all should you ask
      the caller for one.

      The lookup reads the status out to the caller. Do not repeat it, and do
      not ask whether they want to continue — they already said they did.
    complete_when: session.escalate.complaint_id

  - id: raise_it
    instructions: |
      Call `escalate_complaint`. The tool decides whether escalation is
      available, not you.

      On success the tool has already told the caller which authority now
      holds it, the new date, and that the reference does not change. Add
      nothing.

      It refuses in three ways, and each one gets an honest answer rather than
      a workaround:

      - `still_within_target` — it is not late yet. Say how many days are left
        and that it can be raised after that. Do not escalate it anyway.
      - `already_at_top_level` — it is already with the commissioner's
        grievance cell. Give them that cell's number directly.
      - `already_closed` — it has been resolved. Say so, and offer to file a
        fresh complaint if the problem is back.
    complete_when: session.escalate.escalated == True
:::
