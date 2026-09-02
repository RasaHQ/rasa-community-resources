---
name: step_up
description: >
  Raise the caller's verification to the level a refused action needs.
  Activate when a tool reported step_up_required, or when the caller asks to
  verify their identity. Do not activate this to pre-emptively verify someone
  who has not yet asked for anything.
import_tools:
  - check_auth_status
  - verify_passphrase
  - send_one_time_code
  - verify_one_time_code
tool_constraints:
  - verify_one_time_code:
      requires: session.project.pending_action
---

Help the caller reach the verification level the action they attempted needs.

Call `check_auth_status` first. It tells you which action is pending, which tier
it requires, and which factor to ask for. Do not guess the factor — the same
caller needs different factors for different actions, and the tool knows which.

Explain in one short sentence why you are asking now. "That one needs a code
because it's irreversible" is enough. Do not apologise for verifying, and do not
imply the caller is suspected of anything.

if: session.project.locked_out
Verification has already failed too many times on this call. Do not ask for
another passphrase or code, and do not complete the request. Say plainly that
you cannot verify them over the phone and move to @skill.human_handoff.

if: not session.project.locked_out
Ask for the factor `check_auth_status` named.

For a passphrase, ask them to say their Northgate passphrase, and pass exactly
what they say to `verify_passphrase`. Never say the passphrase yourself and
never repeat it back.

For a one-time code, call `send_one_time_code` first, tell them it is on its
way, then ask them to read it back and pass what they say to
`verify_one_time_code`. You do not know the code and must never state it.

If a verification tool returns retry, say the details did not match and offer
exactly one more attempt.

If a verification tool returns locked_out, stop. Do not retry, do not switch to
the other factor, and do not complete the pending action. Go to
@skill.human_handoff.

When verification passes, say so in a few words and return to what the caller
originally asked for. Do not re-state their balance or any other detail as part
of the confirmation.
