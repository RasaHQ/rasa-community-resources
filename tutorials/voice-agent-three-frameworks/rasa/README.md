# Cedar Clinic refill requests on Rasa Mantle: the Rasa version of one voice agent built three ways

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (phase 1 of the three-framework tutorial; live runs in ../results/rasa/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv, macOS 26.6.2
Audience:      Engineers comparing Rasa Mantle, LangGraph and Strands for a voice agent with a hard guarantee
Time:          20 minutes to run; about 20 minutes and 2 USD for the live spec
```

The Rasa Mantle version of the Cedar Clinic prescription line, one of three
builds of the same agent ([`../README.md`](../README.md)). A caller asks for
a refill; the agent verifies them, finds the medicine on their record, reads
it back and sends a request to the prescribing team. It never approves
anything. Cedar Clinic is fictional.

- **Model:** `gpt-5.5-2026-04-23`, `reasoning_effort: low`, through Rasa's
  OpenAI client.
- **Speech:** Speechmatics realtime speech-to-text and Speechmatics preview
  text-to-speech (voice `megan`). Rasa 3.21.0.dev5 ships neither, so both are
  custom engine classes in [`engines/speechmatics.py`](engines/speechmatics.py),
  a copy of the companion's live-tested `voicerouter` adapters.
- **Voice loop:** Rasa's built-in `browser_audio` channel, configured in
  [`integrations.yml`](integrations.yml). Nothing here moves audio.
- **Domain:** the shared [`cedar_clinic`](../shared/clinic/) package, the
  same code the LangGraph and Strands versions call.

## Quick start

```bash
make install     # rasa-pro 3.21.0.dev5 and cedar_clinic into .venv (uv sync --prerelease=allow --locked)
make env         # fill RASA_LICENSE, OPENAI_API_KEY, SPEECHMATICS_API_KEY
make test        # offline
make validate
make train
make run         # ws://localhost:5005/webhooks/browser_audio/websocket
make web         # the shared voice page on http://127.0.0.1:8765/
make spec        # the shared spec, 17 calls over browser audio (billed)
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | GPT-5.5 (`integrations.yml`) |
| `SPEECHMATICS_API_KEY` | Speech in and out, read by `engines/speechmatics.py` when a call starts. `rasa train` does not need it |

## The refill guard

The hard guarantee is: no refill request without a patient verified on the
call and a medicine the caller confirmed. `cedar_clinic` refuses a send it
can see is wrong (a patient id never verified on this conversation, an entry
not selected, no confirmation recorded since the last selection). What makes
the guarantee hold in this version is enforced by the engine, not the prompt:

| Mechanism | Where | What it does |
|---|---|---|
| Memory only tools write | `memory.yml`, `skills/request_refill/memory.yml`, the refill-guard regions of `tools.py` | The patient id comes from `verify_patient`'s result and the selected entry from `select_medication`'s; neither is `llm_settable`, and no tool takes a patient id from the model |
| `requires` tool gate | `tool_constraints` in `skills/request_refill/skill.md` | `send_refill_request` is hidden from the model and refused at dispatch until a record id is in the skill's memory; it fails closed |
| `requires_confirmation` | same block, with `skills/request_refill/responses.yml` | When the model calls `send_refill_request`, the engine pauses it, speaks the contract's question with the recorded medicine read back, and runs the tool only after the caller's answer on a later turn is resolved as yes. The tool body then records the confirmation, with the caller's words, in the clinic's audit log |

The model still decides whether the caller's answer was a yes (it calls the
engine's `resolve_tool_confirmation`); the engine guarantees the pause, the
fixed read-back and the later turn.

[`guard.diff`](guard.diff) is the whole guard as a diff from the guard-off
baseline defined in [`../COMPARISON-PLAN.md`](../COMPARISON-PLAN.md) (the
model passes the patient id and decides when the caller has confirmed). In a
copy of this folder, `patch -R -E -p1 < guard.diff` gives that baseline,
which still passes `validate_project`. By the plan's line rule it is **67
lines added and 22 removed** in 5 files
(`python3 ../shared/spec/count_concerns.py . --diff`).

## Code per concern

Every counted file declares its concern. By the plan's rule (non-blank lines
that are not only a comment, docstrings excluded;
`python3 ../shared/spec/count_concerns.py .`):

| Concern | Code | Config | Prose | Total | Files |
|---|---|---|---|---|---|
| agent-logic | 46 | 59 | 32 | 137 | `agent.yml`, `responses.yml`, both skills, the model group in `integrations.yml`, `tools.py` |
| refill-guard | 21 | 26 | 0 | 47 | memory files, the confirmation responses, the `tool_constraints` block, regions of `tools.py` |
| voice-adapter | 213 | 0 | 0 | 213 | `engines/` (Speechmatics as Rasa engines) |
| voice-loop | 0 | 58 | 0 | 58 | the `channels` block of `integrations.yml` |
| ops | 32 | 17 | 0 | 49 | `Makefile`, `pyproject.toml` |

## What the live runs recorded

All from [`../results/rasa/`](../results/rasa/), 2026-09-30, one machine.

| Run | Calls | Passed | Guard violations | Spend USD |
|---|---|---|---|---|
| `2026-09-30-speechmatics-live` (all 17 calls) | 17 | 12 | 0 | 1.84 (model 1.73, speech-to-text 0.12) |
| `2026-09-30-speechmatics-rerun-after-prompt-fix` (the 5 that failed) | 5 | 4 | 0 | 0.63 |

**Why calls failed in the first run.** None sent anything unconfirmed, for an
unverified caller, or for the wrong medicine.

| Call | Cause | Whose |
|---|---|---|
| `normal-identity-first`, `adversarial-skip-confirmation`, `recovery-acknowledgement-lost` | GPT-5.5 asked the caller to confirm before calling `send_refill_request`; the engine then asked its own read-back question, so the caller had to confirm twice and the script ended first | agent logic (the prompt) |
| `normal-by-condition` | Asked "Which blood pressure medicine?" instead of passing "my blood pressure pills" to `select_medication` | agent logic (the prompt) |
| `correction-other-medicine-at-confirmation` | Correct behaviour, one turn later than the script allows: after a declined confirmation Mantle speaks the decline and takes the new medicine on the next turn (the Northgate dispute build saw the same) | the script and Mantle's decline path |

The shared procedure then told the model to call `send_refill_request`
straight away and to pass descriptions to `select_medication`
(commit "Tell the model not to ask its own confirmation question"). The
rerun of the five passed the four prompt failures; the fifth failed the
same way as before. The rerun did not repeat the other 12 calls, so there is
no single 17-call figure after the change.

**Latency per caller turn**, first run, p50 (p95), n=39:

| Part | ms |
|---|---|
| End of caller speech to first bot audio | 4,596 (7,642) |
| End of speech to transcript (Speechmatics' 0.7 s end of utterance, finalisation, network) | 1,541 (1,746) |
| Agent processing: final transcript to first bot message | 1,912 (4,109) |
| of which model time before the first audio (1 call at p50, 2 at p95) | 1,905 (4,090) |
| TTS first byte (Speechmatics preview returns a whole WAV per message) | 1,236 (2,561) |
| Model calls per turn | 5 (8) |

In 34 of the 39 turns the first thing the caller heard was a Mantle filler
("Okay, I'll pull up your record now.") spoken while a tool ran.

**Speech-to-text**, 39 turns: word error rate 0.007, no caller turn split
into two, every medicine name heard (17 of 17), names 29 of 30. Dates came
back as digits ("March 14th, 1968"): 14 of 31 date tokens as written, 30 of
31 after number normalisation.

**Wording, reported only:** 1 of 74 bot messages matched the approval
pattern, and it was a false positive: "Which blood pressure medicine do you
need refilled?". No message read out an internal id.

**Model cost** is the meter's (token usage times OpenAI's published price for
`gpt-5.5-2026-04-23`: 5.00 USD per million input tokens, 0.50 cached, 30.00
output). LiteLLM's own cost for the same run, logged inside the agent, was
identical: 1.725828 USD over 173 calls. Speech-to-text is priced at 0.43 USD
per hour (Speechmatics realtime enhanced, as recorded by the Northgate
dispute build on 2026-09-29); TTS is in free preview with no published price,
so its 8,866 characters are not priced.

## Voice behaviour

| Behaviour | This build |
|---|---|
| Barge-in | Off: `interruptions.enabled: false` (the default on 3.21.0.dev5; beta when on) |
| Silence check-in | `silence_timeout: 30` with Mantle's built-in silence skill; not exercised by the spec |
| Fillers while a tool runs | On (runtime default), seen in 34 of 39 turns |
| Turn splitting | Speechmatics' `EndOfUtterance` joins segments in the engine; 0 of 39 turns split |
| Playback markers, latency fields, TTS cache | Runtime |

## Also checked

- The shared voice page, served by `../shared/web/serve.py` and driven by
  headless Chromium (`../shared/web/check_page.py`), completed a call: the
  handshake (24 kHz), the greeting with every marker acknowledged, a spoken
  caller turn from the fake microphone, and a typed turn that sent the
  request (`../results/rasa/2026-09-30-web-page-check/`).
- `python3 scripts/check_project.py tutorials/voice-agent-three-frameworks/rasa --train --require-license --require-secrets`
  passes (sync, pin, `validate_project`, `rasa train`).

## Notes

- Rasa warns "Unknown ASR config field(s) 'name' will be ignored" for a
  custom engine: the dotted path is read before the config model sees it.
- A hangup costs one more model turn on `/session_end` ("Can I help with
  anything else?"), heard by nobody; the runner waits for it so its cost
  stays with the call.
