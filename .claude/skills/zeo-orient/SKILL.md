---
name: zeo-orient
description: First-act orientation for any ZEO seat.
---

# zeo-orient

1. `zeo orient --json`
2. If `ZEO_INSTANCE_ID` is set: `zeo relay whoami --json`
3. `zeo relay receive --instance $ZEO_INSTANCE_ID --json` when registered
4. Streams: `zeo --locate <stream>` then `zeo --inbox <stream>`
5. Master: `zeo --triage .`

Do not treat persona names as live addresses.
