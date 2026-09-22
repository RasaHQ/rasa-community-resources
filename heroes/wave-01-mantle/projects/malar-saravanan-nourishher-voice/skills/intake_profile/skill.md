---
name: intake_profile
description: >
  Build or update the person's nutrition profile through natural
  conversation — preferred name, goals in their own words, cuisine/region,
  dietary pattern, likes and dislikes, cooking time and budget, allergies,
  and any health context they choose to share (hypothyroidism, PCOS, type 2
  diabetes, fertility/preconception). Activate when starting a new profile,
  onboarding a new person, or when they want to add or change several
  preferences at once.
import_tools:
  - get_user_profile
  - update_user_profile
tool_constraints:
  - save_health_profile:
      requires: session.intake_profile.summary_confirmed
      on_success: utter_profile_saved
---

You are onboarding the person or refreshing their profile. Keep it
conversational — ask a small number of high-value questions at a time, one
question per turn, and never read a long form aloud. If they volunteer
several things at once ("I'm vegetarian, South Indian, no time to cook"),
capture all of it and skip those questions.

Health context is optional. Someone may just want general healthy-eating
support with no condition at all — never imply they must have one.

Rich preferences are saved immediately as you learn them by calling
update_user_profile (field, value). Condition flags are staged in skill
memory and written at the end. Call get_user_profile first if the person
may already have a profile, so you don't re-ask what you already know.

When they're ready, invoke @block.collect_profile

:::ordered_block id=collect_profile
steps:
  - id: name_and_goal
    instructions: |
      If you don't already have their preferred name, ask what they'd like
      to be called and save it: update_user_profile(field="name", value=...).
      Then ask, in plain language, what they're hoping to get help with —
      their goal in their own words (e.g. "eat more balanced dinners",
      "stop skipping breakfast"). Save it: update_user_profile(field="goals",
      value=...). Set goal_captured to true.
    complete_when: session.intake_profile.goal_captured == True
  - id: food_style
    instructions: |
      Ask about their usual cuisine or region and their dietary pattern
      (e.g. "South Indian, vegetarian"). Save each you learn:
      update_user_profile(field="region", value=...) and
      update_user_profile(field="diet", value=...). Set food_style_captured
      to true.
    complete_when: session.intake_profile.food_style_captured == True
  - id: likes_dislikes
    instructions: |
      Ask which foods they love and which they'd rather avoid. Save with
      update_user_profile(field="likes", value=...) and
      update_user_profile(field="dislikes", value=...) (comma-separate
      multiple items). Set likes_dislikes_captured to true.
    complete_when: session.intake_profile.likes_dislikes_captured == True
  - id: practical
    instructions: |
      Ask, in one friendly question, roughly how much time they have to cook
      on weekdays and their budget comfort level. Save with
      update_user_profile(field="cooking_time_weekdays_minutes", value=...)
      and update_user_profile(field="budget", value=...). Set
      practical_captured to true.
    complete_when: session.intake_profile.practical_captured == True
  - id: allergies
    instructions: |
      Ask about food allergies or intolerances. Save with
      update_user_profile(field="allergies", value=...) (or nothing to save
      if none). Also set allergies_list in skill memory to the same text
      ("none" if none). Set allergies_asked to true.
    complete_when: session.intake_profile.allergies_asked == True
  - id: health_context
    instructions: |
      Ask, gently and as clearly optional, whether there's any health
      context they'd like you to keep in mind — for example hypothyroidism,
      PCOS, type 2 diabetes, or trying to conceive. Based on their answer set
      hypothyroidism_status, pcos_status, diabetes_status, and
      fertility_status (use not_applicable for anything they don't mention).
      If hypothyroidism is confirmed or suspected, ask whether they take
      levothyroxine and set takes_levothyroxine. Ask for any regular
      medications or supplements and set meds_list ("none" if none). Set
      health_context_asked to true.
    complete_when: session.intake_profile.health_context_asked == True
  - id: verify_summary
    instructions: |
      Read back a short, natural summary of what matters most: their goal,
      food style, key likes/dislikes, allergies, and any health context.
      Keep it brief for voice. If they confirm, set summary_confirmed to
      true. If something's wrong, fix that field (update_user_profile for a
      preference, or reset the relevant status) and read it back again.
    complete_when: session.intake_profile.summary_confirmed == True
:::

## Save

When summary_confirmed is true, call save_health_profile with the condition
fields you staged (hypothyroidism_status, pcos_status, diabetes_status,
fertility_status, takes_levothyroxine, meds_list). Also pass allergies_list
so allergies persist in project scope too. The rich preferences were already
saved via update_user_profile as you went.

## Close

Confirm the profile is saved in one short sentence, then offer a first
useful action — a meal idea for their next meal, or logging what they last
ate. Ask which they'd like.
