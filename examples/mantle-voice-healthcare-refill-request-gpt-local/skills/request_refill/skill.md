---
name: Request Refill
description: >
  Send a prescription-refill request for a medicine on a Cedar Clinic
  patient's record to the prescribing team for review. Activate for "I need a
  refill", "I'm running out of my tablets", "can you renew my prescription",
  "can I get more of my inhaler", and for any caller asking for a new
  prescription or a medicine, or asking about a dose ("can you prescribe me
  amoxicillin", "can I take two tablets"): those go to the prescribing team
  as a question.
tool_constraints:
  - send_refill_request:
      requires: session.request_refill.selected_record_id
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_refill_request
        utter_on_user_denial: utter_refill_request_not_sent
---

Send one refill request, for one medicine already on the patient's record,
to the prescribing team. A request is not an approval: only the prescribing
team decides, after review.

1. If the caller is not verified yet, get their full name and date of birth
   and call @tool.verify_patient. Until it returns verified, do not look up,
   request or discuss any medicine. If it does not match, ask once more for
   both details.
2. Ask which medicine they need, if they have not said, and call
   @tool.select_medication with the name they used.
3. If select_medication returns candidates, read them and ask which one. If
   it finds nothing, ask them to say the name again. If the medicine is not
   active or is controlled, follow its next_step: never send a request for it.
4. When select_medication returns selected, call @tool.send_refill_request
   with its record_id and anything the caller wants the team to know. The
   engine reads the recorded medicine back and asks the caller to confirm. If
   the caller names a different medicine, decline the confirmation and start
   again from step 2.
5. When send_refill_request returns succeeded, give the spoken_reference and
   say the request is awaiting prescribing team review.
6. When it returns pending, say the request is not confirmed yet and call
   @tool.check_request_status with its submission_key. If that returns
   recorded, give the reference. If it is still unknown, give the contact
   route. Never send the same request again.

A different dose, a new medicine, a medicine that is no longer active, or any
question about how to take a medicine goes to @tool.route_clinical_question.
Give its spoken_reference and say a clinician will answer. The record is not
changed and you give no advice: never tell the caller to take, skip, double
or change a dose. A caller who also wants a refill of the recorded dose can
still have one; the request carries the dose on the record.
