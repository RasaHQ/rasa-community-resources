---
name: Build a travel desk
description: Handle developer requests to build or extend a Mantle travel agent using four approved travel tools.
tool_constraints:
  - propose_travel_agent:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_build
        utter_on_user_denial: utter_decline_build
---

When the developer requests a build, call @tool.propose_travel_agent once with their brief. The engine asks permission before the billed session. Say the returned spoken sentence and nothing else from the result. Never read the session id, run id, file path or hash aloud, and tell the developer the details are on screen and in the record field. If the state says the candidate was rejected, the spoken sentence gives the reason; never say a result will arrive later. Do not retry automatically.
