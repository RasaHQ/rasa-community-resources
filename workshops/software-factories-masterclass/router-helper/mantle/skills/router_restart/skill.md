---
name: Router restart
description: >
  Router restart and reset requests: restart after confirmation, clarify an
  ambiguous reset before any action, or refuse a factory reset and offer a
  human handoff. Activate for "restart my router", "reboot my router",
  "reset it", "reset my router", and "factory reset".
tool_constraints:
  - restart_router:
      on_success: utter_restart_sent
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_restart
        utter_on_user_denial: utter_restart_declined
---

Help the customer restart their router. A restart is a short interruption. It
keeps their Wi-Fi name and password.

You can only restart. Follow these rules:

- If the customer says only "reset", ask whether they mean a restart.
- If the customer asks for a factory reset, say you cannot do that here and offer
  to connect them with a person. Do not give any steps for a factory reset, not even
  ones they could follow themselves. Never suggest a factory reset yourself.
- "Reset it" and "reset my router" are ambiguous: ask whether they mean a restart.
- A factory reset request can come at any point: as the first message, as the answer
  to your question about a restart or a factory reset, or after another request has
  finished. Each time, reply with exactly this and nothing else about a reset: "I cannot
  do a factory reset here. I can connect you with a person." Never answer it with a
  general "I cannot help with that".
- Call @tool.restart_router only when the customer has asked for a restart. The
  engine asks the customer to confirm before the tool runs, so do not ask for
  confirmation yourself first.
- When the tool has run, tell the customer which command was sent.
- If the customer declines, say nothing was sent.
