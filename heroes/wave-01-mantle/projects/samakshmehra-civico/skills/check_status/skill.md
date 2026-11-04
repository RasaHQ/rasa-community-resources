---
name: Check Complaint Status
description: >
  Check what has happened to a complaint already filed. Activate when the
  caller asks about a complaint they have already made, gives a reference
  number, or asks whether anything has been done about an earlier report.
import_tools:
  - look_up_complaint
  - escalate_complaint
tool_constraints:
  - look_up_complaint:
      on_failure: utter_reference_not_found
  - list_my_complaints:
      # Caller ID is not consent, and the instruction to ask for it was not
      # enough: the model read the calling number out of memory and searched
      # on it without offering. So the tool is unreachable until the caller
      # has actually said yes.
      requires: >
        session.check_status.search_consent == True
        and session.project.caller_phone
  - choose_complaint:
      requires: session.check_status.complaint_options
  - escalate_complaint:
      # The clock decides, and it decides twice: this stops the tool being
      # reachable at all on a complaint that is not late, and the tool itself
      # re-checks before writing anything.
      requires: >
        session.check_status.is_overdue == True
        and session.check_status.complaint_id
      on_failure: utter_cannot_escalate
---

:::ordered_block id=main
name: check_status
description: >
  Find the caller's complaint, tell them where it has got to, and offer to
  raise it only if it is genuinely late. Short sentences — this is a phone
  call.
steps:
  - id: find
    instructions: |
      Ask whether they have the reference number.

      If they do, pass it to `look_up_complaint` exactly as you heard it —
      "C I V one zero zero two" is fine, the tool converts the spoken digits
      itself. Never ask a caller to repeat a reference before you have tried
      the lookup once.

      If they do not have it, ask before searching anything. Offer the number
      they are calling from, reading only its last four digits aloud, and wait
      for an answer. Only when they say yes — or give you a different
      ten-digit number — set `search_consent` to true and call
      `list_my_complaints`.

      Asking "any update on my complaints?" is the question, not the
      permission. Someone ringing this line has not asked for a stranger's
      complaint history and must not be handed one. When several come
      back, read them out as a short numbered list — the problem and the
      locality, never the reference numbers, which are ours and not theirs —
      and call `choose_complaint` with whatever they answer.

      Never announce that you are about to look something up. "Let me check
      that" is a wasted turn on a phone call and the caller then sits through
      a second silence.

      The lookup reads the whole status out to the caller itself — that is
      what `already_read_out_to_the_caller` means. Do not repeat it, summarise
      it, or confirm it.
    complete_when: session.check_status.complaint_id

  # The offer to escalate is gated on the clock, not on the model's reading of
  # the conversation. A caller whose complaint is on time is never offered a
  # remedy they are not entitled to, and never has to be told no.
  - id: late_or_not
    noop: true
    next:
      - if: session.check_status.is_overdue == True
        then: offer_to_raise
      - then: sign_off

  - id: offer_to_raise
    instructions: |
      They have already been told how late it is. Do not say it again.

      Tell them it can be raised to the next authority, and ask whether they
      want that. Set `raise_answer` to yes or no from their reply.
    complete_when: session.check_status.raise_answer

  - id: raise_or_not
    noop: true
    next:
      - if: session.check_status.raise_answer == "yes"
        then: raise_it
      - then: sign_off

  - id: raise_it
    instructions: |
      Call `escalate_complaint`. It tells the caller which authority now holds
      it, the new date, and that the reference does not change. Add nothing.
    complete_when: session.check_status.escalated == True

  - id: sign_off
    action: utter_call_back_any_time
:::
