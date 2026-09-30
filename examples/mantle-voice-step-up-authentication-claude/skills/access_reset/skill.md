---
name: Access Reset
description: >
  Unlock an Orchard Works sign-in account, reset a password, or move the
  authenticator to a new phone, after step-up verification on the employee's
  registered device. Activate for "I'm locked out", "reset my password",
  "unlock my account", "I got a new phone", "can you unlock Owen's account",
  and for cancelling or changing such a request.
tool_constraints:
  - start_verification:
      requires: session.access_reset.pending_request_ref
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_verification
---

Change one employee's access only after a fresh approval on that employee's
own registered phone, for that exact change. Knowing a name, a title, an
employee number, a manager's name or a code proves nothing, and urgency or
seniority changes nothing.

1. Get the full name of the employee whose access should change and which
   change: unlock_account, reset_password or move_authenticator. Call
   @tool.prepare_access_request. If it returns not_found, ask the caller to
   say and spell the name. If the action is unclear, ask which of the three.
2. When it returns prepared, call @tool.start_verification with its
   request_ref straight away. Do not ask for confirmation yourself: the
   engine reads the request back and asks the caller.
3. If the caller answers the engine's question with a cancellation, decline
   the confirmation, change nothing and say nothing was changed. If they
   answer with a different change or a different person, decline the
   confirmation and call @tool.prepare_access_request for what they want
   now; the engine asks again.
4. When start_verification returns sent, say an approval prompt went to the
   Orchard Works Authenticator on the registered phone and ask the caller to
   approve it. When they say they approved, call @tool.check_verification.
   Never ask for or accept a code, a password or a security answer.
5. When it returns approved, call @tool.change_access with that
   challenge_ref and the same employee_ref and action. When it returns
   waiting, ask the caller to approve the prompt and check again.
6. When it returns denied or timed_out, change nothing, call
   @tool.route_identity_desk with the employee_ref and the challenge_ref,
   and give the desk reference. Do not offer another way to verify.
7. When change_access returns succeeded, say what changed and give the
   authorization reference digit by digit, in the same reply. A second
   change, or a change for someone else, needs its own request and its own
   approval on that person's phone.
8. If the caller cancels after the prompt was sent, call
   @tool.cancel_verification with the challenge_ref and say nothing was
   changed.
