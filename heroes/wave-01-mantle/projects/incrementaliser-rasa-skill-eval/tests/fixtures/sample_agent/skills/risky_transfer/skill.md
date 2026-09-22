---
name: Risky Transfer
description: Send money to an authorised payee.
tool_constraints:
  - process_transfer:
      requires: session.risky_transfer.order_confirmed
---

Call process_transfer. If the payee is missing, invoke @skill.add_payee.
