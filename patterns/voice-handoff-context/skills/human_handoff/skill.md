---
name: Human Handoff
description: >
  Hand the caller to a human agent, carrying everything already established.
  Activate when they ask for a person, representative, or live agent, or when a
  path is blocked and cannot be completed on this line.
tool_constraints:
  - transfer_to_human:
      requires: session.project.handoff_reason
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_handoff
        utter_on_user_denial: utter_handoff_cancelled
---

Hand the caller to a person without making them start over.

Say in one line why a human is needed and set `handoff_reason` to that line.
Then call `transfer_to_human`.

Do NOT ask the caller to summarise the call, restate who they are, confirm their
account again, or repeat anything they already told you. All of it is already in
session state and `transfer_to_human` transfers it. Asking is the exact failure
this skill exists to prevent.

Never put a PIN, one-time code, passphrase, full card number or token into
`handoff_reason`. Those are withheld from the transfer by policy, and writing one
into the reason line would carry it across anyway.

if: session.project.handoff_id
The transfer is already prepared. Give the caller the handoff id
@memory.project.handoff_id, tell them a specialist will pick up with everything
already on screen, and that they will not need to repeat themselves.
