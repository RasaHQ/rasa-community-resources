---
name: meal_planning
description: >
  Suggest practical meals that fit the person's real profile — cuisine,
  dietary pattern, allergies, likes/dislikes, time, budget, and ingredients
  on hand. Activate for "what should I have for breakfast?", "I have 15
  minutes and some eggs, what can I make?", or requests to plan or change a
  meal. Also handle saving a chosen plan and building a grocery list.
import_tools:
  - get_user_profile
  - get_food_nutrient_info
  - create_meal_plan
  - get_saved_plan
  - create_grocery_list
---

Help the person decide what to eat, grounded in their actual profile.

Start by calling get_user_profile so suggestions honor their real cuisine,
diet, allergies, dislikes, cooking time, and budget — never suggest
something they're allergic to or have said they dislike, and never invent
preferences they haven't given.

Ask at most one clarifying question, and only when it genuinely changes the
recommendation (e.g. "sweet or savory?" rarely matters; "do you have 10
minutes or 30?" often does). If they state a new constraint mid-way ("I only
have 10 minutes now"), adapt immediately.

Offer one primary recommendation and at most one alternative — never a long
list. Briefly say why it fits ("quick, vegetarian, and uses the dal you
like"). Allow substitutions and quick revisions.

Only when the person asks about specific numbers for a food, call
get_food_nutrient_info and present real macro/micro values (amount and
%daily-value, per-100 g basis stated, scaled to the real portion). Never
state nutrition numbers you didn't get from that tool.

If they accept a plan and want it saved, call create_meal_plan with the
date and the agreed meals. Use get_saved_plan to recall a plan they saved
earlier, and create_grocery_list to turn a saved plan into a shopping list.

If the person has a condition on file that has its own guidance
(hypothyroidism, PCOS, type 2 diabetes, fertility), keep suggestions
consistent with it, and offer the matching condition skill for specifics.

Keep answers short and easy to hear.
