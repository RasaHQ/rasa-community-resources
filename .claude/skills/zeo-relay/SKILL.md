---
name: zeo-relay
description: Address seat instances; never spawn-by-name when an instance is registered.
---

# zeo-relay

Seat types (`zeo-master`, `zeo-sparring`, `zeo-stream`) are constructors.

```bash
zeo relay resolve --seat sparring --json
zeo relay send --from $ZEO_INSTANCE_ID --to <dest> --kind review-request --body "..."
zeo relay receive --instance $ZEO_INSTANCE_ID --json
zeo relay ack --message <message-id>
```

If `should_spawn` is false, send; do not spawn. Artifact refs instead of file copies.
Keep `zeo --inbox` for SOW/ruling truth.
