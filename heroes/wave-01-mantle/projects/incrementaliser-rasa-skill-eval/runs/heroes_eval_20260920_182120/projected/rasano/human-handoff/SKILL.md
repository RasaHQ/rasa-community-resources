---
name: human-handoff
description: 'Connect the customer to a human agent. Activate when they ask for a
  person, representative, live agent, or say the assistant cannot help.

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

Help the customer reach a human agent.

Ask briefly why they want a human and set `handoff_reason`.
When ready, set `handoff_confirmed` to true and call create_handoff_ticket.
Share the ticket id and say a specialist will join shortly.

## Examples

Follow Instructions; do not invent account details.
