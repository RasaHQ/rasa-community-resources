---
name: Transfer Status
description: >
  Status of a transfer that was already submitted, by its reference. Activate
  for "has transfer NB-TRF-7731 gone through", "did my payment post", "check
  my transfer from yesterday".
import_tools:
  - check_transfer_status
  - escalate_reconciliation
---

Call @tool.check_transfer_status with the reference the caller gives. If they
have none, ask for it; the reference is on the transfer confirmation.

Report the ledger status exactly: posted (with when it posted), pending
(reserved, not yet received by the payee's bank) or unknown. A pending
transfer is not complete, and the reference alone does not mean it posted.
If the state is unknown, call @tool.escalate_reconciliation and give its
reference. Never submit a transfer again from here.
