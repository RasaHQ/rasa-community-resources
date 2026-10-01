# Cedar Clinic refill requests on Rasa Mantle: the Rasa version of one voice agent built three ways

```text
Author:        Rasa Community
Assessed on:   2026-10-01
Assessed by:   Claude Code (three-framework tutorial; live runs in ../results/rasa/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv, macOS 26.6.2
Audience:      Engineers comparing Rasa Mantle, LangGraph and Strands for a voice agent with a hard guarantee
Time:          20 minutes to run; about 20 minutes for the scripted calls (17 calls, billed)
```

The Rasa Mantle version of the Cedar Clinic prescription line, one of three
builds of the same agent ([`../README.md`](../README.md)). A caller asks for
a refill; the agent verifies them, finds the medicine on their record, reads
it back and sends a request to the prescribing team. It never approves
anything. Cedar Clinic is fictional.

- **Model:** `gpt-5.5-2026-04-23`, `reasoning_effort: low`, through Rasa's
  OpenAI client.
- **Speech:** Speechmatics realtime speech-to-text and Speechmatics preview
  text-to-speech (voice `megan`), loaded as custom engine classes by dotted
  path from [`engines/speechmatics.py`](engines/speechmatics.py), a copy of
  the companion's live-tested `voicerouter` adapters. With a vendor Rasa
  ships, such as Deepgram, the engines are named in `integrations.yml` and
  no adapter code is needed
  ([`../variants/rasa-deepgram.integrations.yml`](../variants/rasa-deepgram.integrations.yml)).
- **Voice loop:** Rasa's built-in `browser_audio` channel, configured in
  [`integrations.yml`](integrations.yml). Nothing here moves audio.
- **Domain:** the shared [`cedar_clinic`](../shared/clinic/) package, the
  same code the LangGraph and Strands versions call.

## Quick start

```bash
make install     # rasa-pro and cedar_clinic into .venv (uv sync --prerelease=allow --locked)
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

**The fix, opt-in.** Like the other two builds, this one answers caller
transcripts in the order they arrive, so a "Yes, please." spoken before
the read-back has finished playing can be taken as the answer if its
transcript arrives late (`../COMPARISON.md`). [`fix.diff`](fix.diff) adds a browser_audio
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

## Streaming and the TTS

Mantle streams the model's text into the TTS when the TTS engine accepts
streamed text (its `streaming_input`). Rasa's built-in engines (Azure,
Cartesia, Deepgram, Rime) do, so the first words can play while the model is
still writing. The Speechmatics preview TTS used here takes one utterance
per request, so each message is spoken once it is complete. To stream,
change the `tts:` blocks to a built-in engine: the variant in
[`../variants/rasa-deepgram-tts.integrations.yml`](../variants/rasa-deepgram-tts.integrations.yml)
does that, and `make spec-rasa-variant VARIANT=deepgram-tts` from the
tutorial folder runs the scripted calls on it without changing this folder.

## Recorded runs

The scripted calls are recorded in [`../results/rasa/`](../results/rasa/).
On the headline run this version passed 16 of 17 calls, and the guard held
in all of them. Two behaviours worth knowing from those calls:

- **A caller who corrects only their date of birth** is verified with the
  name already given: "Sorry, I meant March 14th, 1968." is followed by
  the read-back.
- **A caller who names another medicine at the read-back** gets the
  decline ("Okay, I have not sent a refill request.") in that turn, and
  the new medicine read back on the next turn.

`python3 ../shared/spec/rasa_call_breakdown.py <run>` lists a run's model
calls by the Mantle function that made them.

## Voice behaviour

| Behaviour | This build |
|---|---|
| Barge-in | In the runtime; off for these runs (`interruptions.enabled: false`) |
| Silence check-in | `silence_timeout: 30` with Mantle's built-in silence skill; not exercised by the spec |
| Fillers while a tool runs | On (runtime default) |
| Turn splitting | Speechmatics' `EndOfUtterance` joins segments in the engine |
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
