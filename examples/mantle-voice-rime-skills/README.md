# Vela — voice banking on Rime TTS

```text
Author:        Rod Rivera
Assessed on:   2026-09-02
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
Audience:      Practitioners choosing a TTS provider for a Rasa voice agent
Time:          30–45 minutes
```

A small banking voice agent whose point is the **speaking half** of the voice
stack: Deepgram Flux listens, and **Rime Mist v2** speaks.

Rime is a first-class TTS engine in Rasa, so wiring it up is one block of
configuration — no plugin, no adapter. The companion resource
[`mantle-voice-speechmatics-skills`](../mantle-voice-speechmatics-skills) takes
the other case: a provider Rasa does **not** ship, which has to be written as a
custom engine. Same agent in both, so the voice stack is the only variable.

## The configuration, in full

```yaml
# integrations.yml
channels:
  inspector:
    asr:
      name: deepgram
      language_map: { en: { model: flux-general-en } }
    tts:
      name: rime
      language_map:
        en:
          voice: cove       # Rime speaker
          language: eng     # ISO-639-3, not "en"
      model_id: mistv2
```

```yaml
# agent.yml
agent:
  voice:
    enabled: true
    asr: deepgram
    tts: rime
```

That is the entire integration. `RIME_API_KEY` is read from the environment by
the engine itself — it is never named in configuration.

Three details, the third of which cost real time:

- **`voice` here is Rime's `speaker`.** Rasa renames it in the language map.
- **`cove` is the speaker Rasa ships as the Rime default**, and is what this
  resource is verified against. Rime's catalogue has many others; swapping one
  in is a one-line change.
- **`language` is required, and it is not the key above it.** Rime wants
  ISO-639-3 (`eng`); the language-map key is Rasa's (`en`). Leave `language`
  out and nothing complains at load — the engine builds a websocket URL
  containing `lang=None` and Rime closes the connection with a bare
  **HTTP 400** the first time your agent tries to speak, with nothing in the
  message pointing at the cause.

That last one was found by connecting to the live API both ways:

```text
lang=None   ->  ConnectionException: Connection to Rime TTS failed with status 400
lang=eng    ->  93 chunks, 141548 bytes of 24 kHz PCM
```

## What it covers

| Skill | What it does |
|---|---|
| `default_session_start` | Loads the customer profile into project memory, then greets — before the caller says anything |
| `intro` | Explains what the agent can do |
| `check_balance` | Reads a checking or savings balance |
| `transfer_money` | Moves money between the caller's own accounts, with spoken confirmation before the write |
| `report_lost_card` | Blocks a card by its last four digits |
| `transaction_history` | Reads out recent transactions |
| `goodbye` | Ends the call |

## Quick start

```bash
make install
make env          # creates .env from .env.example — then fill in the four keys
make verify       # pre-flight: keys and project structure
make train
make inspect      # talk to it — voice and text
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | LLM for routing and conversation |
| `DEEPGRAM_API_KEY` | Speech-to-text (Flux) |
| `RIME_API_KEY` | Text-to-speech (Mist v2) — [rime.ai](https://rime.ai/) |

Names only, never values.

`RIME_API_KEY` is needed to **run**, not to build: `rasa train` completes with it
entirely unset, because the TTS engine is only constructed when a call starts.
That is checked rather than assumed, and it is why this resource is not declared
in `[tool.rasa-catalog] required-secrets` — CI trains it in full like any other
example.

The Rime audio path itself **is** verified: synthesis was run against the live
API from this configuration, returning 141548 bytes of 24 kHz PCM.

## Two things voice changes about tool design

Both are in [`lib/bank.py`](lib/bank.py), and both were learned in the demo this
resource comes from rather than reasoned about in advance.

**A transcript is not a menu choice.** "checking", "check", "my current one" and
"chequing" are one account to a caller and four different strings to a
dictionary lookup. `normalise_account_type` maps what people say onto an account
key, and the skill deliberately passes the caller's own words to the tool rather
than making the model guess a canonical value first.

**Spoken digits arrive spaced.** ASR returns `"4 5 3 2"` as readily as `"4532"`,
and the spacing carries no meaning. `normalise_digits` strips to digits before
comparing. Without it the original demo rejected perfectly good card numbers
routinely.

## What breaks

- **A partial `language_map` fails only at call time.** Covered above: it is
  the single most likely way to break this configuration, and the error names
  neither the field nor the file.
- **`normalise_digits` drops words, not just spaces.** "four five three two"
  collapses to an empty string. Deepgram returns numerals for spoken digit
  strings, which is why that is survivable — an ASR configured to spell numbers
  out would need a word-to-digit pass in front of it. The skill asks the caller
  to repeat rather than guessing, which is the safe failure for a card block.
- **Balances live in memory.** `lib/bank.py` is a module-level dict, so a
  transfer persists for the life of the process and resets on restart. That is
  deliberate — there is no database to set up — but it means two concurrent
  callers share one set of accounts.

## Where it came from

Migrated from [`RasaHQ/rasa-rime-voice-demo`](https://github.com/RasaHQ/rasa-rime-voice-demo)
(`main`), which was a CALM/flows project: `data/flows.yml`, `domain.yml`, and
`rasa_sdk` actions, with voice handled **outside** Rasa by a custom Python
orchestrator talking to Deepgram and Rime directly over REST.

The migration is therefore not a rename. Flows became skills, domain slots
became `memory.yml` schemas, `rasa_sdk` actions became `@tool` functions, and
the voice stack moved **into** Rasa's native voice channel — which is what makes
`tts.name: rime` possible at all. The seeded balances and transactions are
carried over unchanged so the numbers a listener hears are the ones that demo
was tuned around.

## Licence

Apache 2.0 — see the repository root [LICENSE](../../LICENSE). Rasa Pro is a
commercial framework under its own terms.
