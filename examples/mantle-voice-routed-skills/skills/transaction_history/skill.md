---
name: Transaction History
description: >
  Read out the caller's recent transactions. Activate for recent transactions,
  recent charges, spending, or statement activity.
---

Call `get_transactions` and read the rows back in spoken language — date,
merchant, amount — one per sentence. Keep it to the most recent few unless the
caller asks for more; a long list is unlistenable.

If the tool returns no rows, say so plainly rather than filling the silence.
Answer follow-up questions from the rows the tool returned, and never from
memory of what a statement usually looks like.
