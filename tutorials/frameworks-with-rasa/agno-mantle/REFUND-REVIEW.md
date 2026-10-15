# Worked fictional policy-review decision

This is an illustrative design choice for the local worksheet. It is not a
real retailer’s policy acceptance or a deployed staff workflow. The automatic
policy in REFUND-POLICY.md and its function are unchanged.

The worked choice is to retain the first automatic-review reason and supply
inspection status separately in a draft review note. For this exercise, a
returns reviewer needs an inspection before deciding a late-return exception.
Obtaining that inspection is the next step when it is missing; a late sealed
return can proceed to exception review. This additional receiving-process
requirement is a proposed choice, not a rule already stated by the automatic
policy.

The worksheet’s proposed note records the case, automatic result, explicit
inspection status, next step, receiving-role label and draft delivery state.
The inspection status comes from the same invented service record used by
the policy exercise. These are community-example fields, not Mantle queue or
handoff configuration.

The receiving-role label is `returns-reviewer`. Every note has delivery state
`draft_not_sent`: the worksheet contacts nobody and records no acknowledgement.
A real integration needs authenticated access, current order references,
correct records, an actual receiving service and its acceptance evidence.

Run `make policy-review` from this project. The two late-return notes have
the same automatic reason but different next steps. A control removes the
inspection field and is rejected; another skips a missing inspection and is
rejected. These controls check the local proposed contract. They do not show
a live staff queue or approval from a business owner.
