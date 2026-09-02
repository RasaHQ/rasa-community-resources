# Vela — voice banking on a routed vendor stack

```text
Author:        Rod Rivera
Assessed on:   2026-09-02
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
Audience:      Practitioners running a Rasa voice agent that is not allowed to go quiet
Time:          30–45 minutes
```

The same banking agent as [`mantle-voice-rime-skills`](../mantle-voice-rime-skills)
and [`mantle-voice-speechmatics-skills`](../mantle-voice-speechmatics-skills).
The difference is what happens when the vendor stops answering.

A Rasa channel holds exactly one ASR engine and one TTS engine. In both sibling
resources that is the correct design and the whole risk: when Rime is out of
credits, Vela does not degrade — she stops speaking, mid-call, to a customer who
was halfway through a transfer. Here each half of the stack names a *chain*, and
[`patterns/voice-vendor-router`](../../patterns/voice-vendor-router) walks it.

## The whole difference

`agent.yml` points at the router instead of at a vendor:

```yaml
agent:
  voice:
    enabled: true
    asr: voicerouter.RoutedASR
    tts: voicerouter.RoutedTTS
```

and `integrations.yml` says who to try, in order:

```yaml
tts:
  name: voicerouter.RoutedTTS
  policy:
    cooldown_seconds: 60
    health_scope: process
  providers:
    - name: rime                       # Vela's voice
      language_map: { en: { voice: cove, language: eng } }
      model_id: mistv2
    - name: deepgram                   # a different company, different infra
      language_map: { en: { model: aura-2-andromeda-en } }
    - name: voicerouter.providers.openai.OpenAITTS
      label: openai
      language_map: { en: { voice: alloy } }
      model_id: gpt-4o-mini-tts
```

Nothing else about Vela changes. The skills, tools, memory and responses are
byte-identical to the Rime sibling — deliberately, so the voice stack is the
only variable between the three.

## Quick start

```bash
make install                 # installs the router from ../../patterns/ too
make env                     # then put at least OPENAI_API_KEY + DEEPGRAM_API_KEY in .env
make verify                  # prints both chains and which links your keys reach
make train
make inspect
```

You do not need every key. The router skips providers whose credentials are
absent, with a log line, so the chain above runs on whichever ones you hold —
`make verify` tells you exactly which, and warns when a chain is down to a
single link and therefore is not a chain at all.

## Seeing the thing you are actually buying

`make inspect` proves the stack speaks. It cannot show you the moment Rime runs
out of credits, because you would have to run Rime out of credits.

```bash
make drill
```

reads *this project's* `integrations.yml`, builds the real router from it, and
fails vendors on a schedule. The chain, the policy, the utterance classes and
the voice-change rule are the ones in your file; only the vendor HTTP call is
stubbed, so it needs no key and no network.

```text
credits — Primary runs out of credits (HTTP 402) from turn 3
  chain: rime > deepgram > openai

  1. [rime            ] Hi, you're through to Northwind. This is Vela.
  2. [rime            ] One moment.
  3. [deepgram        ] Your current balance is two thousand four hundred fifty dollars.   <- rime -> deepgram, failover
  4. [deepgram        ] Transferring four hundred pounds to Sam Rivera - shall I go ahead?
  ...
  after the call, rime: open, 1 failure(s), last was quota, retried in 900.0s

rate-limit — Primary rate-limits turn 3 once (HTTP 429), then recovers
  1. [rime            ] Hi, you're through to Northwind. This is Vela.
  ...
  6. [rime            ] That's done. Is there anything else?
  after the call, rime: closed, 1 failure(s), last was rate_limit, already serving again
```

That contrast is the design. **Vela changes voice only when she has to** — the
vendor is out of credits, the key is rejected, or the API is unreachable. A rate
limit or a 5xx is retried on the same provider after 250 ms first, because a
caller notices a new person far more than a quarter-second pause. The rule lives
in [`voicerouter/failures.py`](../../patterns/voice-vendor-router/voicerouter/failures.py);
`make drill SCENARIO=bad-key` and `SCENARIO=unreachable` are the other two.

Health is process-scoped, so what one call learns the next one starts with — the
900-second quota park above outlives the hangup rather than being rediscovered
by every caller who arrives during the outage.

## Four stacks, one agent

`stacks/` holds complete alternative `integrations.yml` files:

| Stack | Optimises for | Costs you |
|---|---|---|
| `resilient` *(default)* | Never going silent | Vela's voice changes on a real outage |
| `cost-tiered` | Spend — filler goes to a cheap voice, disclosures stay premium | Her voice changes *within* a healthy call, by design |
| `hyperscaler` | One procurement relationship — AWS, then Google | Neither vendor leads on conversational speech |
| `offline` | Nobody else hearing the audio — Vosk and NeuTTS | Worse recognition, slower and flatter voice |

```bash
make stack                    # list; the current one is starred
make stack STACK=cost-tiered  # switch
make drill STACK=offline      # try one without switching to it
```

Switching refuses to overwrite an `integrations.yml` you have edited unless you
pass `FORCE=1`. Details and the full trade-offs: [`stacks/README.md`](stacks/README.md).

## What breaks

**A chain of one is not a chain.** The commonest mistake is configuring three
providers, holding one key, and believing the agent is covered. `make verify`
says so out loud; it is the reason that check exists.

**A fallback inside the same vendor is not a fallback.** Two Deepgram models go
down together. The default chain crosses companies on purpose, and ends in a
local model that is nobody's outage.

**Rime needs `language: eng`, not `en`.** Omitting it passes validation, builds a
websocket URL containing `lang=None`, and fails with a bare HTTP 400 the first
time the agent speaks. The router classifies that as CONFIG — permanent, so
Rime is disabled for the process rather than retried every minute. Correct
behaviour, and a confusing way to learn about a typo: check `make verify` and
the `voicerouter.tts.*` log lines.

**Failover happens before the first byte, never mid-sentence.** Once audio is
flowing the provider owns that sentence; a vendor dying halfway through is
recorded and ends the sentence rather than restarting it in a different voice.

**Health is per process, not per fleet.** Four workers discover the same outage
four times. Sharing it needs a store and a failure mode of its own; process
scope already removes most of the waste. See the pattern README.

**The `offline` stack has no voice out of the box.** NeuTTS cannot be installed
alongside rasa-pro in one environment — rasa-pro pins numpy `<2.2`, neutts needs
`>=2.2.6`. It is skipped with that reason until you run it out of a second venv.
That is a real outcome, and better seen in a drill than in production.

## Running the local last resort

The ASR chain ends in faster-whisper, which needs an extra:

```bash
uv sync --prerelease=allow --extra local-asr
```

The model downloads on first use (~75 MB for `tiny.en`). Until then that link is
skipped like any other unconfigured provider — the chain still works, it is just
one shorter. Vosk, AWS and Google are the same story with different extras;
`make probe` inside the pattern reports which vendors your environment can
actually reach.

## Verified

- `validate_project` and `rasa train` pass on the catalog pin
- The TTS chain in `integrations.yml` exercised against **live** Rime and
  Deepgram, at both audio formats the Inspector negotiates (L16 24 kHz and
  mulaw 8 kHz): Rime serves the healthy chain; with its key rejected the router
  classifies the failure as AUTH, disables Rime for the process, and Deepgram
  finishes the call
- `make drill` output checked against that live behaviour, so the four scenarios
  describe what actually happens rather than what the code appears to do
- ASR routing is verified in the pattern, against live Deepgram and
  Speechmatics; the chain here is the same shape and has not been re-run
  separately
- Not verified: the `hyperscaler` and `offline` stacks. AWS, Google and NeuTTS
  need credentials and installs this machine does not have, so they are
  configuration this resource ships and does not claim to have run.

## Layout

```text
agent.yml                 persona, rules — points voice at the router
integrations.yml          the live voice stack (a copy of one of stacks/)
stacks/                   four complete alternatives + their trade-offs
scripts/drill_failover.py replay a call with a vendor failing
scripts/verify_setup.py   pre-flight: keys, files, and both chains
skills/                   check_balance, transfer_money, report_lost_card, …
lib/bank.py               seeded demo bank
```

## Credits

Vela, her skills and her demo bank come from
[`mantle-voice-rime-skills`](../mantle-voice-rime-skills), reused unchanged so
that the three resources stay comparable. The routing layer is
[`patterns/voice-vendor-router`](../../patterns/voice-vendor-router).
