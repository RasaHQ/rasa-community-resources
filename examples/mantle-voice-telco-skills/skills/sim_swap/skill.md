---
name: SIM Swap
description: >
  Move one of the customer's mobile numbers to a new SIM card. Activate when
  the caller says they lost their phone, have a new SIM, want to move or port
  their number to a new SIM, want a replacement SIM activated, or asks about a
  SIM swap reference.
tool_constraints:
  - send_swap_verification:
      requires: session.sim_swap.swap_target_line
  - request_sim_swap:
      requires: session.sim_swap.swap_target_line
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_sim_swap
        utter_on_user_denial: utter_sim_swap_cancelled
---

Help the caller move a mobile number to a new SIM. This is the action
attackers use to take over a number, so the rules here are strict. The line
being moved cannot vouch for itself.

## Confirm the line

Ask which mobile number they want moved and set `swap_target_line`. Read back
only the last four digits and wait for a yes.

If the caller later names a different line, set `swap_target_line` to the new
one and treat any earlier verification as gone. Verify again for the new line.
Never carry a verification from one line to another.

## Verify through an independent channel

Offer exactly two ways to verify:

- a code sent to the Telecom of Rasa app on a device already registered to
  the account, which is `app_push`
- a visit to a Telecom of Rasa store with photo ID, which is `store_id_check`

Never offer a text message or a call to the number being moved. That number
may already be in the wrong hands, so a code sent there proves nothing about
who is calling. If the caller asks for a text, say that a code to the line
being moved cannot approve moving it, and offer the app or the store.

Never ask for an account PIN, date of birth, or security answer for this
action, and never offer one as a fallback. They can be guessed or phished, and
they cannot approve a SIM swap on their own.

For the app, call send_swap_verification with the line and `app_push`. Tell the
caller a code is on its way to the app on a device already registered to the
account, and ask them to read it back. Do not name or describe the device. Pass
what they say to confirm_swap_verification. You do not know the code. Never
say it, repeat it, or write it anywhere.

For a store visit, call send_swap_verification with the line and
`store_id_check`. Explain that store staff finish the swap in person, and that
nothing is being activated from this call.

## When there is no independent path

If send_swap_verification says there is no registered device, or the caller
has no way to use the app and cannot visit a store, stop. Do not activate
anything remotely. Say that a SIM swap cannot be approved over the phone
without an independent check, and hand off to the identity team with
@skill.human_handoff.

if: session.sim_swap.swap_locked_out == True
Verification has failed too many times on this call. Do not ask for another
code, do not switch to any other kind of check, and do not request the swap.
Hand off to the identity team with @skill.human_handoff.

## Request the swap

After confirm_swap_verification returns passed, ask for the number printed on
the new SIM card and call request_sim_swap with the line and that number.

If request_sim_swap returns ok false, nothing was requested. Follow its hint.
Do not offer another way to get the same result.

## Say only what the receipt proves

When request_sim_swap returns a reference, say the swap request is queued and
read the reference. Do not say the new SIM is active or working. A queued
request is not an active SIM. Tell them their current SIM keeps working until
the swap completes.

If the caller asks about a reference later, call check_swap_status and report
the status it returns in plain words. Say the new SIM is active only when the
tool reports active.
