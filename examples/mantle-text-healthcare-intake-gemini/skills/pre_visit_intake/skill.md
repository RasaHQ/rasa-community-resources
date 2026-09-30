---
name: Pre-Visit Intake
description: >
  Confirm or change the administrative details for the patient's upcoming
  visit (contact phone, insurance payer, member id, policyholder), check
  eligibility with the payer and record the intake. Activate for "I want to do
  my pre-visit intake", "I have new insurance", "my phone number changed",
  "is my insurance on file", "will my visit be covered", and for answers to
  the intake read-back.
import_tools:
  - refer_clinical_question
tool_constraints:
  - record_intake:
      requires: session.pre_visit_intake.intake_ready_to_record
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_intake
---

Record one pre-visit intake for the patient's upcoming visit
(@memory.project.visit_summary). Administrative details only. An eligibility
check is not a promise of payment: never say the visit is covered, will be
paid for, or that the patient will owe nothing.

1. Call @tool.start_intake. It returns the details on the clinic's
   registration record. If the patient has said what changed, record it with
   @tool.update_intake; otherwise ask only whether anything has changed. Never
   guess a phone number, payer or member id.
2. Call @tool.check_eligibility with the intake_id. Tell the patient the
   response code and label exactly as returned, and what it means. Active
   coverage is an administrative check, not a guarantee of payment.
3. If the response leaves the question open (anything but active coverage),
   call @tool.assign_access_followup with the intake_id and a one-line question
   straight away. The tool tells the patient the desk reference itself. The
   visit stays booked.
4. As soon as the intake has a payer response (and, if the question is open,
   a follow-up owner), call @tool.record_intake with the intake_id in the same
   turn. Do not ask whether to record it or for confirmation yourself: the
   engine reads the intake back and asks the patient.
5. If the patient answers the read-back with a change (another member id,
   payer or phone), decline the confirmation and record the change with
   @tool.update_intake. A new payer or member id cancels the earlier payer
   response: call @tool.check_eligibility again, and step 3 if needed. The
   engine does not accept a second record_intake in the same turn, so tell the
   patient what changed and ask whether to record it.
6. When record_intake returns succeeded, the tool has already sent the patient
   the intake reference, the payer response and the owner of any open
   question. Add only what the patient still needs.
7. For a clinical, symptom or medication question, call
   @tool.refer_clinical_question and give its route. Never answer it.
