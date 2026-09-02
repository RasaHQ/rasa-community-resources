---
name: human_handoff
description: >
  Hand the call to a human agent. Activate when the caller asks for a person,
  or when verification has failed and the request cannot be completed.
---

Tell the caller you are connecting them to a colleague who can help.

if: session.project.locked_out
Explain that identity could not be confirmed over the phone, and that a
colleague will verify them another way. Do not say what was wrong with the
passphrase or the code, do not say how many attempts were used, and do not hint
at what the correct answer would have been.

Say that reference H D four one seven has been created for this demo, and keep
the closing short.
