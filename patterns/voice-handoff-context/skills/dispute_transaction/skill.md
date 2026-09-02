---
name: Dispute Transaction
description: >
  Raise a dispute on a card transaction the caller does not recognise. Activate
  when they report an unrecognised, duplicate, or incorrect charge.
tool_constraints:
  - raise_dispute:
      requires: session.dispute_transaction.disputed_txn_id
---

Help the caller dispute a charge they do not recognise. Do not invent
transactions, amounts, merchants, or dates.

Call `load_caller_context` first if you do not yet know who you are speaking to.
It resolves the caller and records the verification tier they reached.

Call `list_recent_charges`, present the charges briefly (date, merchant, amount),
and ask which one they are disputing. Set `disputed_txn_id` via `set_fields` to
the matching id from the tool result.

Then call `raise_dispute`.

A dispute needs a high verification tier. If `raise_dispute` reports that the
caller's tier is insufficient, do not retry it and do not attempt to raise the
tier yourself — this agent does not perform step-up. Say plainly that a
specialist has to complete it, set `handoff_reason` to one line explaining that,
and use @skill.human_handoff.

Never ask the caller for a PIN, one-time code, or full card number. If they offer
one, do not record it.
