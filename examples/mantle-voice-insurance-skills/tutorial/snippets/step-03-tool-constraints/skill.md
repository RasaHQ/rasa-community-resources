---
name: Check Claim Status
description: >
  Look up the status of an existing insurance claim by claim number. Activate
  when the customer asks about claim status, claim progress, or an open claim.
tool_constraints:
  - get_claim_status:
      requires: session.check_claim_status.claim_number
---

Help the customer check a claim status. Do not invent claim numbers or statuses.

if: not session.check_claim_status.claim_number
Ask for the claim number. When they provide it, set `claim_number` via
`set_fields`. Demo claim numbers include CLAIM1234 through CLAIM1238.

if: session.check_claim_status.claim_number
Call get_claim_status with that claim number.

if: session.check_claim_status.claim_status == "0"
Explain that an adjustor is being assigned. Mention the expected assignment
by `adjustor_date`. Keep it to two short sentences.

if: session.check_claim_status.claim_status == "1"
Explain that an adjustor is assigned. Share the contact: John Doe,
plus one two two two three three three four five six seven.

if: session.check_claim_status.claim_status == "2"
Explain that inspection scheduling is in progress.
Offer to help schedule an inspection. If they agree, invoke
`@skill.schedule_inspection`.

if: session.check_claim_status.claim_status == "3"
Explain the claim was approved and details were emailed.
Ask if they have questions. If they need a person, invoke `@skill.human_handoff`.

if: session.check_claim_status.claim_status == "4"
Explain the claim was rejected.
Ask if they want details from a human. If yes, invoke `@skill.human_handoff`.

if: session.check_claim_status.claim_status == "5"
Say you could not find that claim number and ask them to confirm it.
