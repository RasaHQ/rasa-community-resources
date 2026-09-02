# Voice stacks

Four whole voice stacks for the same agent. Each file is a complete
`integrations.yml` — copy one over the project's file and nothing else about
Vela changes:

```bash
make stack STACK=offline      # writes stacks/offline.yml to integrations.yml
make stack                    # lists what is available and which is current
```

`make stack` refuses to overwrite an `integrations.yml` you have edited unless
you pass `FORCE=1`, so a local tweak is not lost to a typo.

| Stack | What it optimises for | What it costs you |
|---|---|---|
| `resilient` | Never going silent. Two vendors then a local model. **This is the shipped default.** | Vela's voice changes if Rime is out of credits or unreachable. |
| `cost-tiered` | Spend. Filler goes to a cheap voice, disclosures stay premium. | Vela audibly changes voice *within a call*, by design, not only on failure. |
| `hyperscaler` | One procurement relationship. AWS throughout, Google behind it. | Both halves of the stack sit with vendors whose speech products are not their best work. |
| `offline` | No third party hears the call. Vosk and NeuTTS, no network. | Noticeably worse recognition and a slower, flatter voice. |

The default is `resilient` because "the agent stopped speaking" is the failure
callers actually notice. The other three are here because that is not everyone's
first constraint.

Read [`../../../patterns/voice-vendor-router/README.md`](../../../patterns/voice-vendor-router/README.md)
for what the policy keys mean and which vendors exist.
