---
name: meal_logging
description: >
  Log a meal the person describes in natural speech, including approximate or
  incomplete descriptions ("a small bowl of rice and dal", "a sandwich, not
  sure what was in it"). Also log how a meal made them feel. Activate when
  they say what they ate or drank, or want to log a meal or symptom.
import_tools:
  - log_meal
  - log_symptom
---

Capture what the person ate, exactly as they describe it. Approximate
descriptions are fine — store them as given and never invent quantities or
nutrition facts they didn't provide.

1. Extract the meal items from what they said.
2. If the meal type (breakfast, lunch, dinner, snack) is clear from context,
   use it; otherwise ask once, briefly.
3. Call log_meal with the description, meal_type, and a confidence of low,
   medium, or high based on how complete the description was.
4. Confirm what you logged in one short sentence.

Only ask for detail that materially helps ("was that today?" if timing is
unclear). Don't interrogate.

If they're really describing how they felt rather than a meal (e.g. "I felt
sluggish after lunch"), use log_symptom instead, and do not draw any medical
conclusion from it.

If what they describe sounds like a red flag (possible hypoglycemia, thyroid
crisis, a concerning menstrual-pattern change, or disordered-eating signals),
stop and hand off immediately to @skill.safety_escalation instead of logging
it as routine.

Keep every response short enough for voice.
