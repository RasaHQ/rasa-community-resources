---
name: unslop
description: Edit text to remove AI writing tells and keep a direct human voice. Activate when polishing skill prose, reports, or agent-facing copy.
license: Apache-2.0
---

# Unslop

Edit the given text. Keep meaning, names, numbers, tool ids, headings, and code fences. Do not add facts.

## Cut

- Puffery and stock phrases ("delve", "navigate", "holistic", "robust solution", "in today's landscape")
- Chatbot sign-offs ("I hope this helps", "let me know if you need anything")
- Em-dash stacks and rule-of-three lists that say the same thing three ways
- Hedging that hides a decision ("it is important to note that")

## Keep

- Concrete verbs and constraints
- Tool names, account numbers, YAML keys
- Length roughly the same. Required Agent Skills sections (`# Title`, `## Instructions`, `## Examples`) may be kept or filled; do not pad with extra sections beyond those.

Return only the edited document.
