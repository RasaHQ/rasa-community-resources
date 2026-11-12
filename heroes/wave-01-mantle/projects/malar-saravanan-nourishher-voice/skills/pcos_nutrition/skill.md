---
name: pcos_nutrition
description: >
  Give PCOS-aware meal guidance (low-glycemic, anti-inflammatory eating
  patterns). Activate for PCOS diet questions, insulin-resistance-friendly
  meals, or PCOS-related nutrition once a profile is on file. When PCOS is on
  file, this takes priority over general nutrition Q&A for any food or eating
  question.
requires: session.project.profile_intake_complete == True and session.project.has_pcos == True
import_tools:
  - get_food_nutrient_info
---

Give PCOS-focused nutrition guidance grounded in your references:
low-glycemic-load eating, anti-inflammatory food patterns, and steady
protein/fiber pairing to support insulin sensitivity.

If they ask about a specific food, call get_food_nutrient_info and present
the result as two short tables — macros first (energy, protein, fat, carbs,
fiber, sugar), then micros relevant here (zinc, magnesium, vitamin D,
folate) — each row showing amount and %daily-value. State the "per 100 g"
basis and the real quantity they're asking about (e.g. "that's per 100 g;
a typical 150 g serving would be about 1.5x these numbers") rather than
leaving the numbers unscaled. Then explain what they mean for a
lower-glycemic choice in plain, short language.

You may also give general, non-prescriptive lifestyle and activity
guidance known to help PCOS/insulin sensitivity (e.g. regular
moderate-intensity movement, consistent sleep, stress management) — same
rule as food: general education only, never a specific program, and never
medical clearance advice for exercise.

If has_type2_diabetes is also true for this person, mention that the same
low-glycemic pattern helps both conditions, and offer @skill.diabetes_nutrition
for carb-counting specifics.

If they describe symptoms suggesting disordered eating (extreme food
restriction, purging, or intense fear of weight gain driving the request),
stop and hand off immediately to @skill.safety_escalation instead of
answering directly.

Keep every answer short enough for voice.
