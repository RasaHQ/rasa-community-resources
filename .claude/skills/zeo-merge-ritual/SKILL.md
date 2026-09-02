---
name: zeo-merge-ritual
description: Protected-trunk session-branch cadence.
---

# zeo-merge-ritual

One branch per session. Rebase onto trunk, push, one PR. Do not merge yourself
on a protected trunk. Do not claim delivery from a local SHA; verify
`git branch -r --contains <hash>` against the real remote.
