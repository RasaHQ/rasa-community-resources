---
name: Authenticate
description: >
  Verify who the caller is before any account work happens. Activate when the
  caller wants to sign in, verify themselves, or when another skill needs an
  authenticated customer and there is not one yet.
---

Sign the caller in.

If the caller has already given a passphrase in what they just said, call
`verify_passphrase` with it straight away. Do not ask them to repeat it.

Only if no passphrase has been given, ask for it once, then call
`verify_passphrase` with their answer.

When the tool succeeds, greet them by the returned name and confirm they are
signed in. When it fails, say the passphrase did not match and offer one more
try. After three failed attempts, stop and suggest they call the branch.

Never reveal the passphrase, and never guess it on the caller's behalf.
