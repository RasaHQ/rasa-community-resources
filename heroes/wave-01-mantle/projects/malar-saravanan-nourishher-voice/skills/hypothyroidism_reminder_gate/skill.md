---
name: hypothyroidism_reminder_gate
description: >
  Internal routing gate — never mention this skill by name. Matches the exact
  same requests as hypothyroidism_nutrition (hypothyroidism diet questions,
  thyroid-friendly meals, iodine/selenium questions, or any food/eating
  question when hypothyroidism is on file). Takes priority over general
  nutrition Q&A. Activates instead of hypothyroidism_nutrition only for the
  one turn where the levothyroxine timing reminder still needs to play.
requires: >
  session.project.profile_intake_complete == True and
  session.project.has_hypothyroidism == True and
  session.project.takes_levothyroxine == True and
  session.project.levothyroxine_reminder_sent == False
---

:::ordered_block id=gate
steps:
  - id: send_reminder
    execute_tool: send_levothyroxine_reminder_if_needed
  - id: continue_to_guidance
    link: hypothyroidism_nutrition
:::
