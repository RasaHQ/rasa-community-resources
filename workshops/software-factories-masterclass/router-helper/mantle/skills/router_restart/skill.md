---
name: Router restart
description: >
  Restart the customer's router after they confirm. Activate for "restart my
  router", "reboot my router", "turn my router off and on", "my internet is
  stuck, can you restart it".
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
  to connect them with a person. Never suggest a factory reset yourself.
- Call @tool.restart_router only when the customer has asked for a restart. The
  engine asks the customer to confirm before the tool runs, so do not ask for
  confirmation yourself first.
- When the tool has run, tell the customer which command was sent.
- If the customer declines, say nothing was sent.
