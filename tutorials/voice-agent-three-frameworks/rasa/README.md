# Cedar Clinic refill requests on Rasa Mantle: the Rasa version of one voice agent built three ways

```text
Author:        Rasa Community
Assessed on:   2026-10-01
Assessed by:   Claude Code (three-framework tutorial; live runs in ../results/rasa/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv, macOS 26.6.2
Audience:      Engineers comparing Rasa Mantle, LangGraph and Strands for a voice agent with a hard guarantee
Time:          20 minutes to run; about 20 minutes and 2 USD for the live spec (17 calls)
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
which still passes `validate_project`. By the plan's line rule, with
docstrings excluded on both sides as for the other two versions, it is **67
lines added and 18 removed** in 5 files
(`python3 ../shared/spec/count_concerns.py . --diff`).

**The fix, opt-in.** The guard binds consent to the order in which Mantle
takes transcripts, not to whether the caller had heard the question: a
"Yes, please." spoken before the read-back was taken as the answer
(`../COMPARISON.md`). [`fix.diff`](fix.diff) adds a browser_audio
subclass, loaded by dotted path from `integrations.yml`, that records when
each utterance began and when each bot message finished playing. It also
adds a check in `send_refill_request` that refuses an answer begun before
the read-back finished playing. No change to `rasa-pro`. Apply it with
`make fix-copy FW=rasa` from the tutorial folder. It is 92 counted lines,
not part of the figures above.

## Code per concern

Every counted file declares its concern. By the plan's rule (non-blank lines
that are not only a comment, docstrings excluded;
`python3 ../shared/spec/count_concerns.py .`):

| Concern | Code | Config | Prose | Total | Files |
|---|---|---|---|---|---|
| agent-logic | 46 | 59 | 32 | 137 (94 without the 43 lines that restate `cedar_clinic.instructions`, which LangGraph and Strands import instead) | `agent.yml`, `responses.yml`, both skills, the model group in `integrations.yml`, `tools.py` |
| refill-guard | 21 | 26 | 0 | 47 (44 without 3 restated lines) | memory files, the confirmation responses, the `tool_constraints` block, regions of `tools.py` |
| voice-adapter | 213 | 0 | 0 | 213 | `engines/` (Speechmatics as Rasa engines) |
| voice-loop | 0 | 58 | 0 | 58 | the `channels` block of `integrations.yml` |
| ops | 32 | 17 | 0 | 49 | `Makefile`, `pyproject.toml` |

## What the live runs recorded

All from [`../results/rasa/`](../results/rasa/), on one machine.

| Run | Procedure | Calls | Passed | Guard violations | Spend USD |
|---|---|---|---|---|---|
| `2026-10-01-speechmatics-live-shared-prompt` (**the headline**) | shared, after the change | 17 | 16 | 0 | 2.01 (model 1.89, speech-to-text 0.12) |
| `2026-09-30-speechmatics-live` (first run, history) | before the change | 17 | 12 | 0 | 1.84 |
| `2026-09-30-speechmatics-rerun-after-prompt-fix` | after | 5 | 4 | 0 | 0.63 |
| `2026-10-01-guard-off-adversarial` (guard-off baseline, the 6 adversarial calls) | after | 6 | 6 | 0 | 0.48 |
| `2026-10-01-deepgram-tts-streaming` (variant: built-in Deepgram TTS, model streamed) | after | 17 | 16 | 0 | 2.17 (model 1.80, speech-to-text 0.11, TTS 0.26) |
| `2026-10-01-deepgram-live` (variant: built-in Deepgram ASR and TTS) | after | 17 | 11 | 0 | 1.86 (model 1.51, speech-to-text 0.11, TTS 0.25) |

**The headline run's one failure** is `correction-other-medicine-at-confirmation`,
as in the first run. At the read-back the caller names another medicine;
Mantle's decline path speaks "Okay, I have not sent a refill request." and
ends the turn, and the budesonide is selected and read back on the next
turn, which is one turn later than the script allows. Nothing wrong was
sent. The LangGraph and Strands guards hand the caller's words back to the
model in the same turn and passed it. This version passed
`recovery-second-verification`, which both of them failed.

**The first run's failures** were four calls where GPT-5.5 asked its own
confirmation question before calling `send_refill_request` (so the caller
had to confirm twice), or asked which medicine instead of selecting by
description. They led to the shared procedure change
("Tell the model not to ask its own confirmation question"), which all three
versions' headline runs use.

**Latency per caller turn**, headline run, p50 (p95), n=39:

| Part | ms |
|---|---|
| End of caller speech to first bot audio | 4,971 (7,050) |
| End of speech to transcript | 1,574 (1,750) |
| Agent processing: final transcript to first bot message | 2,295 (3,731) |
| of which the turn's first model call, not streamed | 2,193 (3,281) |
| TTS first byte | 1,187 (2,482) |
| Model calls per turn | 5 (7) |

The model calls are not streamed because Mantle streams only into a TTS
engine that accepts streaming text, and this Speechmatics engine takes one
utterance per request. The first audio was a Mantle filler in 35 of 39
turns.

**With a streaming TTS.** The variant in
[`../variants/rasa-deepgram-tts.integrations.yml`](../variants/rasa-deepgram-tts.integrations.yml)
changes only the two `tts:` blocks to Rasa's built-in Deepgram engine, whose
`streaming_input` is `True`. It is run with `make spec-rasa-variant
VARIANT=deepgram-tts` from the tutorial folder, which copies this folder and
leaves it unchanged. Mantle then streamed 141 of 173 model calls (all but
fact discovery). End of speech to first audio fell from 4,971 to 3,170 ms at
p50, agent processing from 2,295 to 965 ms and TTS first byte from 1,187 to
274 ms. Speech-to-text was unchanged (1,632 ms). With Deepgram both ways
(`VARIANT=deepgram`, no custom engine at all) it was 2,104 ms. See
[`../COMPARISON.md`](../COMPARISON.md#rasa-with-a-streaming-tts).

**Where the 178 model calls go**, labelled by the Mantle function that made
each one (`../shared/spec/rasa_call_purposes.py`,
`python3 ../shared/spec/rasa_call_breakdown.py ../results/rasa/2026-10-01-speechmatics-live-shared-prompt`):

| Purpose | During caller turns | After the hangup | USD |
|---|---|---|---|
| Orchestrator iteration | 108 | 17 | 1.49 |
| Fact discovery (after a skill switch, off the reply path) | 17 | 17 | 0.28 |
| Response rephrasing | 2 | 17 | 0.12 |

The model returned one tool call per orchestrator iteration. 49 of the 125
iterations were engine tools (`activate` 17, `complete_skill` 14,
`resolve_tool_confirmation` 13, `cancel_skill` 3, `cannot_help` 2), against
51 for the clinic's tools. The 51 calls after hangups are Mantle's
`/session_end` turn, which nobody hears. LangGraph made 86 calls and Strands
73 for the same 17 calls; see [`../COMPARISON.md`](../COMPARISON.md).

**Speech-to-text**, headline run: word error rate 0.009, no caller turn
split, every medicine name heard (17 of 17), names 29 of 30.

**Model cost** is the meter's (token usage times OpenAI's published price for
`gpt-5.5-2026-04-23`: 5.00 USD per million input tokens, 0.50 cached, 30.00
output). LiteLLM's own cost, logged inside the agent, was identical in both
Speechmatics full runs (1.887398 USD over 178 calls in the headline). Speech-to-text is
priced at 0.43 USD per hour (Speechmatics realtime enhanced, as recorded by
the Northgate dispute build on 2026-09-29); TTS is in free preview with no
published price, so it is not priced.

**No tuned run.** This release has no setting to turn off fact discovery or
the `/session_end` turn, and model streaming needs a TTS engine that accepts
streaming text (a built-in one, as measured above, or custom code); see [`../COMPARISON.md`](../COMPARISON.md#why-there-is-no-tuned-rasa-run).

## Voice behaviour

| Behaviour | This build |
|---|---|
| Barge-in | Off: `interruptions.enabled: false` (the default on 3.21.0.dev5; beta when on) |
| Silence check-in | `silence_timeout: 30` with Mantle's built-in silence skill; not exercised by the spec |
| Fillers while a tool runs | On (runtime default); first audio of 35 of 39 turns in the headline run |
| Turn splitting | Speechmatics' `EndOfUtterance` joins segments in the engine; 0 of 39 turns split |
| Work after the hangup | One `/session_end` turn: 3 model calls per call |
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
