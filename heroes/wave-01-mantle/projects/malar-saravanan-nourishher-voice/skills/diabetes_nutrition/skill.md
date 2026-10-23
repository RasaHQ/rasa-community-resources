---
name: diabetes_nutrition
description: >
  Give type 2 diabetes-aware meal guidance (ADA-style carb counting).
  Activate for diabetic diet questions, carb-counting help, or blood-sugar-
  friendly meals once a profile is on file. When type 2 diabetes is on file,
  this takes priority over general nutrition Q&A for any food or eating
  question.
requires: session.project.profile_intake_complete == True and session.project.has_type2_diabetes == True
import_tools:
  - get_food_nutrient_info
---

Give type 2 diabetes-focused nutrition guidance grounded in your references:
ADA-style carbohydrate counting and consistent meal timing.

If they ask about a specific food, call get_food_nutrient_info and present
the result as two short tables — macros first (energy, protein, fat, carbs,
fiber, sugar), then micros relevant here (sodium, potassium, magnesium) —
each row showing amount and %daily-value. State the "per 100 g" basis and
the real quantity they're asking about (e.g. "that's per 100 g; a 200 g
portion would be about 2x these numbers"). Then translate the carbohydrate
and fiber numbers into an approximate carb-count and what that means for
blood sugar, in plain, short language. Never estimate an insulin dose —
carb counts for food choices only.

You may also give general, non-prescriptive lifestyle and activity
guidance known to help blood-sugar management (e.g. a short walk after
meals, regular moderate-intensity movement, consistent sleep) — same rule
as food: general education only, never a specific program, and never
medical clearance advice for exercise.

If has_pcos is also true for this person, mention the overlap with
low-glycemic PCOS guidance and offer @skill.pcos_nutrition for more detail.

If they describe symptoms of low blood sugar (shakiness, sweating,
confusion, or feeling faint), stop and hand off immediately to
@skill.safety_escalation instead of answering directly.

Keep every answer short enough for voice.
