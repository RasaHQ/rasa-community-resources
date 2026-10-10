---
name: human-handoff
description: 'Handoff to a human agent. Activate when the customer asks for a person,
  representative, or live agent, or says the assistant cannot help.

  '
license: Apache-2.0
version: 0.1.0
compatibility: Rasa Mantle (rasa-pro 3.20.0.dev6)
metadata:
  author: RasaHQ <hi@rasa.com>
  version: 0.1.0
  rasa_skill_id: human_handoff
  rasa_display_name: Human Handoff
---

# Human Handoff

## Instructions

Connect the customer to a human agent.

1. Ask briefly why they want a human. Done when `handoff_reason` is set from their answer.
2. Set `handoff_confirmed` to true and call create_handoff_ticket. Done when the call returns a ticket id.
3. Share the ticket id and say a specialist will join shortly. Done when the customer has the ticket id.

## Examples

Follow Instructions; do not invent account details.
