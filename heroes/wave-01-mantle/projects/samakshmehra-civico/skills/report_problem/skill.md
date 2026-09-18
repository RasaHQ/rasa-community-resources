---
name: Report a Problem
description: >
  Start a complaint, including "I want to file a complaint" before category or
  location is known. Handle potholes, garbage, water supply, street lights,
  drainage, and stray animals.
complete_when: session.report_problem.complaint_id
tool_constraints:
  - confirm_ward:
      requires: session.report_problem.ward_candidates
  - find_similar_open:
      requires: >
        session.report_problem.category
        and session.report_problem.ward_confirmed == True
        and session.report_problem.description
        and session.report_problem.exact_spot
        and session.report_problem.callback_number
  - file_complaint:
      requires: >
        session.report_problem.details_verified == True
        and session.report_problem.duplicate_decision == "new"
        and session.report_problem.ward_confirmed == True
        and session.report_problem.exact_spot
        and session.report_problem.description
        and session.report_problem.callback_number
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_filing
        utter_on_user_denial: utter_filing_cancelled
      on_failure: utter_report_not_saved
  - attach_to_existing:
      requires: >
        session.report_problem.details_verified == True
        and session.report_problem.duplicate_decision == "attach"
        and session.report_problem.similar_id
        and session.report_problem.ward_confirmed == True
        and session.report_problem.exact_spot
        and session.report_problem.description
        and session.report_problem.callback_number
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_attachment
        utter_on_user_denial: utter_filing_cancelled
      on_failure: utter_report_not_saved
---

:::ordered_block id=main
name: report_problem
description: >
  A helpful conversation, not a questionnaire. Capture facts in any order,
  check existing reports, read one summary, obtain one submission confirmation.
  One question per turn. Tool calls have no spoken preamble: never say "got it",
  "recording that", or "filing now" before tools. Never repeat a tool message
  marked already_read_out_to_the_caller.
steps:
  - id: intake
    instructions: |
      A bare "I want to file a complaint" belongs here. Ask "What would you
      like to report?" Do not also ask where in that turn.

      Capture ALL volunteered details using capture_report, consulting the
      whole conversation. Problem, area, landmark and callback are independent:
      location can arrive before problem. Never discard an answer because it
      is not what you just asked for.
      "Near Juniper Heights, Vashali, Ghaziabad" gives area Vashali, Ghaziabad
      AND landmark near Juniper Heights. Save both immediately.
      "The light bulb is not working" in this civic context is already a usable
      streetlight description. Do not ask for another sentence about it.
      If they clearly mean a private indoor bulb, explain this covers public lights.
      "Vikas Marg" or "near the metro station" adds to the incident location,
      not the problem description. Preserve earlier landmarks unless corrected.
      Keep the existing locality when adding a road. Set replace_area true only
      when the caller explicitly changes locality, not for an extra landmark.
      Landmark details are additive. Set replace_landmark true only when the
      caller explicitly replaces the spot; do not discard their earlier building.
      Do not guess a gate, road, PIN or issue detail the caller did not supply.

      Ask only for missing information, one item at a time:
      - problem: "What is the problem there?"
      - area: "Which locality is that in? A PIN code also helps me choose the demo team."
      - landmark: "What building or landmark would help someone find the exact spot?"
      - callback: "What number should I save for follow-up on this report?"
      Explain ten digits only if the number is incomplete. Do not promise SMS,
      calls, or automatic updates: this demo supports lookup, not notifications.
      A PIN identifies a routing area, not an exact incident spot. If the caller
      supplies only a PIN, still ask for a building, road or public landmark.
      A specific public place or building is enough; do not demand a gate or
      pole number once the spot is identifiable.
      If they say "near my society", ask the society name first even if the
      problem is still missing. Follow their train of thought.

      A unique directory match is provisional routing reviewed in the FINAL
      summary. Do not ask "is ward twelve correct?" or list officers now.
      Only for multiple localities or a PIN mismatch, ask which LOCALITY they
      mean in plain language, then call confirm_ward with their selection.
      If no match, ask for another locality or PIN once and call capture_report with
      the actual answer even if "I don't know". Two misses route to the demo
      grievance cell. Do not invent an area or ask a third time.
      On an unsupported problem, explain the six supported civic categories;
      never choose a different category just to continue. On invalid callback,
      ask for ten digits again. Do not search knowledge to decide intake steps.

      Validate callback digits; never guess missing digits or assume the demo
      calling number. If explicitly asked to use the calling number, pass
      @memory.project.caller_phone to capture_report as callback.
      Use capture_report for volunteered details. After a summary, use
      revise_report for corrections; it rechecks and reads back the changed draft.
      For "the other gate", keep the known building and locality. If it is
      unclear which side they mean, ask front/back or a nearby landmark once;
      never invent a gate number or a compass direction.
      Save quietly, then ask the next question without a separate acknowledgement.
    complete_when: >
      session.report_problem.category
      and session.report_problem.ward_confirmed == True
      and session.report_problem.exact_spot
      and session.report_problem.description
      and session.report_problem.callback_number

  - id: check_existing
    execute_tool: find_similar_open

  - id: duplicate_choice
    instructions: |
      With no match, duplicate_decision is already new; say nothing and continue.
      With a match, ask "There is already an open report at [tool's where].
      Is that the same issue, or a different spot?" Never decide from ward alone.
      Set duplicate_decision to attach only if the caller says same, or new
      if they say different. Never read another caller's reference or phone.
      If the location is corrected instead, save it and rerun the check.
    complete_when: session.report_problem.duplicate_decision

  - id: review
    execute_tool: prepare_report_summary

  - id: route
    noop: true
    next:
      - if: session.report_problem.duplicate_decision == "attach"
        then: attach
      - then: register
  - id: register
    execute_tool: file_complaint
    next:
      - then: finished
  - id: attach
    execute_tool: attach_to_existing
    next:
      - then: finished
  - id: finished
    noop: true
:::
