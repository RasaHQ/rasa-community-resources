---
name: update_profile
description: >
  Add, change, or remove a single remembered preference without re-running
  the whole intake. Activate for "remember that I don't like mushrooms",
  "I'm not vegetarian anymore", "forget my old dinner preference", "update my
  cooking time to 30 minutes", or any one-off correction to stored profile
  details.
import_tools:
  - get_user_profile
  - update_user_profile
  - delete_user_profile
---

Make a targeted change to the person's stored profile.

To add or change a preference, call update_user_profile(field, value). To
remove something, call delete_user_profile(field) for a whole field, or
delete_user_profile(field, value) to remove one item from a list (e.g.
remove "vegetarian"-related likes, or a single disliked food).

Valid fields: name, age_range, region, diet, allergies, likes, dislikes,
cooking_frequency, cooking_time_weekdays_minutes, meal_schedule, budget,
goals, health_context, clinician_constraints.

Confirm high-impact changes back to the person before or right after saving
("Got it — I'll use tofu instead of tempeh."), especially when a voice
transcript might be uncertain. If a change conflicts with something already
stored, point out the conflict briefly and confirm which one they want.

Note: changing a diagnosed condition (adding or removing hypothyroidism,
PCOS, type 2 diabetes, or fertility focus) runs through @skill.intake_profile,
since those flags gate the condition-specific guidance — offer to do that if
they ask to change a condition.

Keep it to one short spoken confirmation.
