---
name: report_baggage
description: >
  File a lost or delayed baggage report.
  Activate for missing bags, delayed luggage, or baggage claims.
import_tools:
  - list_bookings
tool_constraints:
  - submit_baggage_report:
      requires: session.report_baggage.details_verified
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_baggage_report
        utter_on_user_denial: utter_baggage_report_cancelled
      on_success: utter_baggage_submitted
utter:
  - utter_baggage_recording_notice:
      on: activate
  - utter_baggage_stolen_warning:
      when: session.report_baggage.bag_issue == "stolen"
---

Help the traveler report lost or delayed baggage. Accuracy first — collect
details in order, then confirm before submit.

Once they want to file a report, invoke @block.collect_baggage

:::ordered_block id=collect_baggage
steps:
  - id: fetch_bookings
    execute_tool: list_bookings
  - id: select_booking
    instructions: |
      Show the traveler's bookings from the tool result.
      Ask which trip the bag belongs to. Set booking_ref to the full reference.
    complete_when: session.report_baggage.booking_ref
  - id: collect_issue
    instructions: |
      Ask whether the bag is delayed, lost, or stolen. Set bag_issue.
    complete_when: session.report_baggage.bag_issue
  - id: collect_tag
    instructions: |
      Ask for the bag tag number if they have it. If unknown, set bag_tag to unknown.
    complete_when: session.report_baggage.bag_tag
  - id: collect_last_seen
    instructions: |
      Ask where they last saw the bag (carousel, gate, hotel, taxi). Set last_seen.
    complete_when: session.report_baggage.last_seen
  - id: collect_description
    instructions: |
      Ask for a short description: color, size, distinctive marks. Set description.
    complete_when: session.report_baggage.description
  - id: verify_summary
    instructions: |
      Read back booking_ref, bag_issue, bag_tag, last_seen, and description.
      If they confirm, set details_verified to true.
      If something is wrong, correct the field and re-summarize.
    complete_when: session.report_baggage.details_verified == True
:::

## Submit

When details_verified is true, call submit_baggage_report with the
collected fields. Speak the report id character by character.

## Close

Confirm in one or two short sentences suitable for voice.
