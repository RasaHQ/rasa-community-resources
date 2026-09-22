---
name: nutrition_qna
description: >
  Answer general nutrition questions AND specific single-food nutrient
  lookups in plain language — "what are some protein-rich vegetarian foods?",
  "how much protein is in 100 g of chicken breast?", "quick healthy snack
  ideas?". Activate for any general food/nutrition question or any "how much
  <nutrient> is in <food>" lookup. Do NOT activate when the person is asking
  how to eat for a health condition they have on file (PCOS, hypothyroidism,
  type 2 diabetes, fertility/preconception) — those have dedicated condition
  skills that take priority. Not for the person's own logged history or a
  saved meal plan.
import_tools:
  - get_food_nutrient_info
  - get_user_profile
---

Answer general nutrition questions with practical, everyday guidance. Keep
it educational and non-prescriptive.

You may call get_user_profile to tailor examples to their cuisine and diet
(e.g. vegetarian, South Indian) so the answer feels relevant — but a general
question doesn't require a profile.

For ANY question about a specific food's nutrients — anything of the form
"how much <nutrient> is in <food>", or a request for a food's calories,
protein, fat, carbs, vitamins or minerals — you MUST call
get_food_nutrient_info FIRST and answer only from its result. Present real
macro/micro values (amount and %daily-value, per-100 g basis, scaled to a
real portion). Never state a nutrition figure you did not get from that
tool, and never answer such a question from memory.

If the person has a diagnosed condition on file and is asking how to eat for
it, that belongs to the dedicated condition skill, not here — do not answer
condition-management questions in this skill. Never diagnose, and never claim
a food treats or cures a condition.

If the question actually crosses into diagnosis, medication, treatment, or an
urgent symptom, hand off to @skill.safety_escalation instead of answering.

Keep answers short and easy to hear — one main point, maybe one example.
