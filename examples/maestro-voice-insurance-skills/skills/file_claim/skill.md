---
name: File Claim
description: >
  File a new auto or homeowners insurance claim. Activate when the customer
  wants to start a claim, report damage, or submit an incident.
import_tools:
  - list_policies
tool_constraints:
  - submit_claim:
      requires: session.file_claim.details_verified
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_submit_claim
        utter_on_user_denial: utter_claim_cancelled
      on_success: utter_claim_submitted
utter:
  - utter_claim_recording_notice:
      on: activate
  - utter_auto_extra_fields:
      when: session.file_claim.policy_name == "Car"
  - utter_home_extra_fields:
      when: session.file_claim.policy_name == "Homeowner"
---

Help the customer file a claim. Do not invent policies or claim numbers.
Security and accuracy first — collect details in order, then confirm before submit.

Once they want to file, invoke `@block.collect_details`

:::ordered_block id=collect_details
steps:
  - id: fetch_policies
    execute_tool: list_policies
  - id: select_policy
    instructions: |
      Show the customer's policies from the tool result (type and policy number).
      Ask which policy to file under. Set policy_num to the full policy number and
      policy_name to Car or Homeowner to match that policy.
    complete_when: session.file_claim.policy_num and session.file_claim.policy_name
  - id: collect_description
    instructions: |
      Ask what happened and what caused the damage. Set claim_description.
    complete_when: session.file_claim.claim_description
  - id: collect_date
    instructions: |
      Ask for the incident date. Accept relative phrases like yesterday.
      Call normalize_incident_date_value with their answer and keep the
      normalized MM/DD/YYYY value in incident_date. If normalization fails,
      ask again using mm/dd/yyyy.
    complete_when: session.file_claim.incident_date
  - id: collect_auto_fields
    instructions: |
      if: session.file_claim.policy_name == "Car"
      Ask for the incident time and set incident_time.
      Ask where it happened and set incident_location.
      if: session.file_claim.policy_name == "Homeowner"
      Skip time and location. Continue.
    complete_when: >
      (session.file_claim.policy_name == "Homeowner") or
      (session.file_claim.incident_time and session.file_claim.incident_location)
  - id: collect_additional
    instructions: |
      if: session.file_claim.policy_name == "Car"
      Ask for witness contacts and police report number if available.
      if: session.file_claim.policy_name == "Homeowner"
      Ask for any additional information they want to share.
      Set additional_claim_info.
    complete_when: session.file_claim.additional_claim_info
  - id: verify_summary
    instructions: |
      Read back a short claim summary: policy, description, date, and any
      auto-only fields. Ask if everything looks correct.
      If they confirm, set details_verified to True.
      If they say something is wrong, invoke `@skill.human_handoff`.
    complete_when: session.file_claim.details_verified == True
:::

## Submit

When details_verified is True, call submit_claim with the collected fields.
Share claim number one two three four five in spoken form.

## Close

Confirm submission in one or two short sentences suitable for voice.
