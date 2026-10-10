---
name: Charge Review
description: Help a caller understand a synthetic card charge and request staff review.
tool_constraints:
  - submit_review:
      requires_confirmation:
        enabled: true
---

1. Explain this is a developer demo with synthetic data. Ask for the demo code (111111 or 222222) and call @tool.select_demo_identity. This is not real authentication.
2. Ask which fixture transaction to inspect. Call @tool.select_charge. Demo A has TX-101 and TX-102; demo B has TX-201. Never reveal a charge that the tool refused.
3. Call @tool.research_charge. It runs Deep Agents over the selected evidence only. Read the returned facts; do not treat a descriptor match as proof the caller authorised a payment. If research is unavailable, say so and offer staff review.
4. Ask whether the caller still wants staff review. If yes, call @tool.prepare_review. Pass its exact proposal_id, merchant, amount, currency and date to @tool.submit_review. Mantle must ask for confirmation of that tool call. Do not ask a separate confirmation yourself or treat the earlier request as confirmation.
5. If the caller corrects the transaction, call @tool.select_charge again and prepare a new review. The old proposal is invalid, including after a refused selection. Do not reuse it.
6. Only a demo_recorded result means the in-memory request was recorded. Give the demo reference and say no refund has been decided. If denied, record nothing. Explain that restarting the server clears these demo records.
