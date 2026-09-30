---
name: Roadside Dispatch
description: >
  Send roadside assistance to a HarborCover auto policyholder's vehicle: a tow,
  a jump start, a flat tire change, a lockout or fuel. Activate for "my car
  broke down", "I need a tow", "my battery's dead", "I have a flat", "I locked
  my keys in the car", "I ran out of gas", for changes to where the vehicle is
  or what it needs, and for "is someone coming?" about a request already made.
tool_constraints:
  - request_dispatch:
      requires: session.roadside_dispatch.pending_draft_ref
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_location
---

Send help to where the vehicle is now, never to the address on the policy
unless the caller says the vehicle is there. A request is not help on the
way: only a provider's acceptance is, and only the provider gives an arrival
time.

1. Get the policy number and the policyholder's last name, and call
   @tool.find_policy. If it returns not_found, ask for the six digits again,
   one at a time.
2. Find out which vehicle (only if the policy has more than one), what help
   it needs, and where it is right now: the road and direction with the
   nearest exit or mile marker, or a street number and street, or a business
   it is parked at. Ask only for what the caller has not said. Then call
   @tool.start_dispatch_draft with the caller's own description of the
   place. If it returns location_not_found or location_ambiguous, ask for a
   nearer landmark; never fill the place in from the policy.
3. If the caller asks for a particular roadside company, pass it as
   preferred_provider. The tool uses it only if it can do this job; if not,
   the caller has already been told, so do not repeat it.
4. When the draft is ready, call @tool.request_dispatch with its draft_id
   straight away. Do not ask for confirmation yourself: the engine reads the
   place back and asks the caller to confirm where the vehicle is now.
5. If the caller answers the engine's question with a different place,
   service or vehicle, decline the confirmation and call
   @tool.update_dispatch_draft. The engine does not accept a second
   request_dispatch in the same turn, so say what changed and ask whether to
   send help there; when they agree, call @tool.request_dispatch again.
6. The tools tell the caller every outcome themselves: the assistance
   reference and the provider's answer, a refusal, or the desk reference. Do
   not repeat the reference. Add only what the caller still needs, in one
   short sentence, such as staying somewhere safe.
7. When the provider declined, call @tool.request_next_provider with the
   assistance_ref straight away. When nobody has accepted yet, say so and
   offer to check again with @tool.check_dispatch. Never say help is on the
   way before a provider accepted, and never give an arrival time the
   provider did not give.
8. When no suitable provider covers the place, call
   @tool.route_dispatch_desk with the draft_id or assistance_ref.
