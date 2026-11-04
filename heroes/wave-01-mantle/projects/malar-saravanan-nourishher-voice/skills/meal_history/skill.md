---
name: meal_history
description: >
  Retrieve and summarize what the person has logged recently. Activate for
  "what did I eat yesterday?", "have I been skipping breakfast this week?",
  "show me today's meals", or any question about their own logged history.
import_tools:
  - get_meal_history
  - get_behavioral_summary
---

Answer questions about the person's own logged meals and symptoms.

Pick the window from what they asked: 1 day for "today", 2 for "yesterday",
7 for "this week". Call get_meal_history with that range_days. For pattern
questions ("have I been skipping breakfast?"), also call
get_behavioral_summary.

Summarize only what is actually in the log. If nothing is logged for the
window, say so plainly and offer to start logging now.

Present observations cautiously and never turn them into medical
conclusions. Good: "You logged breakfast on two of the last five days, and
you mentioned mornings are rushed." Never: "This means your blood sugar is
unstable."

Keep it short and natural for voice — no long enumerated lists.
