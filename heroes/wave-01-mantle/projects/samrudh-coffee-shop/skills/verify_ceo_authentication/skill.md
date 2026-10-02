---
name: verify_ceo_authentication
description: >
  Verify the 4-digit CEO Executive Security PIN to unlock privileged business and financial analytics.
  Activate when the user explicitly asks to authenticate as CEO or provides their executive PIN.
import_tools:
  - verify_ceo_pin
memory:
  pin_attempt:
    type: string
    description: "4-digit executive PIN or passcode entered by the user."
  pin_verified:
    type: boolean
    description: "Set to True once executive PIN authentication succeeds."
complete_when:
  condition: "session.verify_ceo_authentication.pin_verified"
tool_constraints:
  - verify_ceo_pin:
      requires: session.verify_ceo_authentication.pin_attempt
---

Verify CEO / Executive credentials to grant analytics access.

When the user asks for executive analytics or CEO access, prompt them clearly: "Please enter your 4-digit Executive Security PIN to unlock financial analytics."
When the user provides their PIN (e.g. 8888), store the PIN in pin_attempt.

Call @tool.verify_ceo_pin with pin=pin_attempt.

If authentication succeeds, confirm that CEO privileges are verified, set pin_verified to True, and present the requested financial or operational metrics (Revenue, Gross Margins, Store Benchmarks, or COGS).
If authentication fails, inform the user that the PIN is incorrect and access to financial analytics remains restricted.
