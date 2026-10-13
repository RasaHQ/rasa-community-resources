---
name: Blocked request
description: Handle a change request that the demonstration tool always refuses.
---

1. Call @tool.request_change once to try the requested change.
2. When the tool returns refused, explain that staff must review it. Offer @skill.staff_handoff and wait for the user's agreement.
3. Do not note the request, send it elsewhere or retry it. Do not call @tool.note_request, @tool.send_elsewhere or @tool.retry_change after refusal.
4. After the handoff finishes, end this task. Do not resume the refused change.
