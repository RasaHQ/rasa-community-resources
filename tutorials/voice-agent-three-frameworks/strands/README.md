# Cedar Clinic refill requests on AWS Strands Agents: the Strands version of one voice agent built three ways

```text
Author:        Rasa Community
Assessed on:   2026-10-01
Assessed by:   Claude Code (phase 2 of the three-framework tutorial; live runs in ../results/strands/)
Verified with: strands-agents 1.57.1, openai 2.54.0, Python 3.12, uv, macOS 26.6.2
Audience:      Engineers comparing Rasa Mantle, LangGraph and Strands for a voice agent with a hard guarantee
Time:          10 minutes to run; about 20 minutes and under 1 USD for the live spec
```

The AWS Strands Agents version of the Cedar Clinic prescription line, one of
three builds of the same agent ([`../README.md`](../README.md)). A caller
asks for a refill; the agent verifies them, finds the medicine on their
record, reads it back and sends a request to the prescribing team. It never
approves anything. Cedar Clinic is fictional.

- **Model:** `gpt-5.5-2026-04-23` at reasoning effort low, through Strands'
  `OpenAIResponsesModel` (the Responses API, streamed, `store` off). See
  [the model](#the-model) for why not `OpenAIModel`.
- **Speech:** Speechmatics realtime speech-to-text and Speechmatics preview
  text-to-speech (voice `megan`), through the shared
  [`cedar_speech`](../shared/speech/) clients, the same vendor calls as the
  Rasa version.
- **Voice loop:** [`server.py`](server.py), written for this build. Strands
  has no speech-to-text-then-model-then-speech pipeline to plug these into.
- **Domain:** the shared [`cedar_clinic`](../shared/clinic/) package, the
  same code the Rasa and LangGraph versions call.

## Quick start

```bash
make install     # strands-agents[openai] 1.57.1, cedar_clinic and cedar_speech into .venv (uv sync --locked)
make env         # fill OPENAI_API_KEY and SPEECHMATICS_API_KEY (or rely on the repository root .env)
make test        # offline: parity, the guard with a scripted model, the protocol, concern tags
make run         # ws://localhost:5007/webhooks/browser_audio/websocket
make web         # the shared voice page on http://127.0.0.1:8765/, relaying to :5007
make spec        # the shared spec, 17 calls over browser audio (billed)
```

Say: "I'm Maria Alvarez, born March fourteenth, nineteen sixty-eight. I need
a refill of my lisinopril." When the agent reads the medicine back, say yes.

## Layout and concerns

| File | Concern | What it is |
|---|---|---|
| [`agent.py`](agent.py) | agent-logic, with refill-guard regions | The model, the prompt, the five `@tool` bindings to `cedar_clinic`, one `Agent` per conversation id, one caller turn as a stream. The regions are the state only tools write and the interrupt/resume half of the guard |
| [`guard.py`](guard.py) | refill-guard | `RefillGuard`, a Strands intervention handler |
| [`server.py`](server.py) | voice-loop | The browser_audio server around `cedar_speech` and `agent.py` |
| `pyproject.toml`, `Makefile` | ops | Packaging and run targets |
| [`guard.diff`](guard.diff) | not counted | The guard as a diff from the guard-off baseline |
| `tests/test_strands.py` | not counted | Offline tests, including the untagged-file test |

## The model

`agent.py` builds `OpenAIResponsesModel(model_id="gpt-5.5-2026-04-23",
params={"reasoning": {"effort": "low"}})`. Two things were checked live on
2026-10-01 before settling on it:

- `OpenAIModel` (Chat Completions) with `params={"reasoning_effort": "low",
  "temperature": 0.2}` is refused: "Only the default (1) value is supported"
  for temperature. No temperature is set anywhere.
- `OpenAIModel` with `reasoning_effort: low` and tools is refused too:
  "Function tools with reasoning_effort are not supported for
  gpt-5.5-2026-04-23 in /v1/chat/completions. To use function tools, use
  /v1/responses or set reasoning_effort to 'none'." So the Chat Completions
  path cannot hold the comparison's model setting, and this build calls
  `/v1/responses`, streamed. The Rasa version also called `/v1/responses`
  (through LiteLLM), not streamed.

The openai SDK reads `OPENAI_BASE_URL`, so the spec runner's meter sees and
prices every call.

## The refill guard

The hard guarantee is: no refill request without a patient verified on the
call and a medicine the caller confirmed on a later turn. `cedar_clinic`
refuses a send it can see is wrong. What makes the guarantee hold in this
version is Strands code that runs at tool execution, not the prompt:

| Mechanism | Where | What it does |
|---|---|---|
| Agent state that only tools write ([agent state](https://strandsagents.com/docs/user-guide/sdk/agents/state/)) | refill-guard regions of `agent.py` | `verify_patient` writes the patient id to `agent.state` (write-once), `select_medication` writes the selected entry and its label. Strands does not pass agent state to the model, no tool takes a patient id, and no tool lets the model write state |
| `Deny` from an intervention handler ([interventions](https://strandsagents.com/docs/user-guide/sdk/agents/interventions/)) | `RefillGuard.before_tool_call` in `guard.py` | Before `send_refill_request` runs: no verified patient, no selected entry, or a `record_id` other than the selected one, and the call is cancelled with a reason the model sees. The handler's `on_error` is `deny`, so a crash in it blocks the send |
| `Confirm` from the same handler, on Strands interrupts ([human in the loop](https://strandsagents.com/docs/user-guide/sdk/agents/interventions/human-in-the-loop/), [interrupts](https://strandsagents.com/docs/user-guide/sdk/interrupts/)) | `guard.py`, and the refill-guard regions of `agent.py`'s `Conversation.turn` | Otherwise the handler returns `Confirm(prompt=<the read-back question>)`. With no response supplied, Strands raises an interrupt and the agent stops with `stop_reason == "interrupt"`. The voice loop speaks the prompt, `cedar_clinic.confirmation_question(label)` word for word. On the caller's next turn, and only then, the agent is resumed with an `interruptResponse` carrying the caller's words. Confirm's `evaluate` function judges them, records the answer with the clinic (`record_confirmation`, mechanism "strands Confirm intervention"), and lets the tool run only on a yes. A no cancels the call, and the voice loop speaks the shared decline, "Okay, I have not sent a refill request." |
| `Transform` in `after_tool_call` | `guard.py` | A resumed agent gets interrupt responses, not a user message, so the model would not otherwise hear what the caller said at the confirmation. The handler appends the caller's words to the tool result, so a caller who names another medicine there gets it selected and read back |

**Who decides that the answer was a yes.** In the Rasa version the model
decides (it calls `resolve_tool_confirmation`). Here `evaluate` is a fixed
rule, `guard.caller_said_yes`: the first clause must start with an
affirmative (yes, yeah, sure, okay, fine, go ahead, and similar) and hold no
negation, no later clause may retract it ("wait", "don't send", "instead"),
and no other recorded medicine may be named. Anything else is a no. That is
stricter than Rasa's model judgment and costs no model call on the
confirmation turn, but it can refuse a yes phrased in a way the rule does not
know, and a real deployment would need more phrasings or a model classifier.
The Strands docs show `evaluate` as the place for custom approval logic.

**What the guard does not use.** `HumanInTheLoop` (the vended handler) would
work for the pause, but it prompts with the tool name and input rather than
the clinic's question, so a custom handler returning `Confirm` was simpler.
Cedar authorization, steering handlers and Bedrock Guardrails were not
needed: the rule is three state checks and one confirmation.

[`guard.diff`](guard.diff) is the whole guard as a diff from the guard-off
baseline defined in [`../COMPARISON-PLAN.md`](../COMPARISON-PLAN.md): the
same tools with `patient_id` as a model argument, no intervention handler,
the send tool recording the confirmation itself ("none: the model decided"),
and step 4 of the procedure telling the model to read the question and wait
for a yes. In a copy of this folder, `patch -R -E -p1 < guard.diff` gives
that baseline, and applying it forward to the baseline gives this folder
(both checked).

By the plan's line rule (`python3 ../shared/spec/count_concerns.py . --diff`)
it is **144 lines added and 32 removed, 176 changed**, in 2 files: `agent.py`
+46 -32, `guard.py` +98 -0. The diff counter cannot tell a docstring from
code, so 30 of the added lines and 3 of the removed ones are docstrings;
without them it is +114 -29 (143). The Rasa guard diff, with docstrings
excluded the same way, is 85 (+67 -18), mostly YAML, whose comments do not
count.

## The voice loop

Strands' own voice feature is `BidiAgent`
([bidirectional streaming](https://strandsagents.com/docs/user-guide/sdk/bidirectional-streaming/)):
"a Python-only experimental feature" in 1.57.1, imported from
`strands.experimental.bidi`, holding a persistent connection to a realtime
speech-to-speech model (Nova Sonic, OpenAI Realtime or Gemini Live). It has
no provider that takes a transcript from one vendor and sends text to
another's text-to-speech, so it cannot run Speechmatics in and out, and it
could not hold the comparison's speech settings. `BidiModel` is a public
abstract class, so a custom cascade provider is possible in principle, but it
is undocumented. This build uses the plain `Agent` and writes the loop.

[`server.py`](server.py) (Starlette and uvicorn, asyncio) implements
[`../shared/web/PROTOCOL.md`](../shared/web/PROTOCOL.md):

- **Transport:** `WS /webhooks/browser_audio/websocket`, the conversation id
  from `X-Rasa-Sender-Id`, the handshake at 24 kHz, `{"audio"}` frames to the
  Speechmatics socket, `{"text"}` turns, marker acknowledgements.
- **End of turn:** Speechmatics' `EndOfUtterance` after 0.7 s of silence, as
  in the Rasa engine; each final transcript is one `user` event and one agent
  turn. A caller turn split in two would be answered twice, as Rasa does.
- **Sentence chunking:** model text is streamed from `Agent.stream_async`,
  cut at sentence ends, and each sentence goes to TTS as soon as it is
  complete, while the model is still writing. Fixed messages (the greeting,
  the read-back question) are split the same way.
- **Markers:** a start marker, one per second of audio, and an end marker on
  every bot message with `rasa_processing_latency_ms` (final transcript to
  the turn's first sentence ready for TTS), `tts_first_byte_latency_ms` and
  `tts_complete_latency_ms`. Speechmatics returns a whole WAV per request, so
  "first byte" is the first sentence's synthesis time.
- **Fillers:** when tools finish before anything was said in the turn, a
  fixed phrase per tool ("Thanks, one moment while I check.") plays while the
  next model call runs. This is after the tools, not before them as in
  Mantle; the tools are local and take milliseconds.
- **Silence check-in:** 30 s after the agent's last audio was acknowledged as
  played with no caller speech, a fixed prompt. Not exercised by the spec.
- **Barge-in:** not implemented. Caller audio keeps going to speech-to-text
  while the agent speaks; a transcript that arrives then is answered after
  the current turn.
- **Events:** `GET /conversations/{id}/events` and `GET /health`.

## Code per concern

Every counted file declares its concern, and `tests/test_strands.py` fails
on one that does not. By the plan's rule (`python3 ../shared/spec/count_concerns.py .`):

| Concern | Code | Config | Prose | Total | Files |
|---|---|---|---|---|---|
| agent-logic | 115 | 0 | 0 | 115 | `agent.py` |
| refill-guard | 92 | 0 | 0 | 92 | `guard.py` (72), regions of `agent.py` (20) |
| voice-adapter | 0 here, 251 in `shared/speech` | 0 | 0 | 251 | `../shared/speech/cedar_speech` (plus 16 lines of its `pyproject.toml`, ops) |
| voice-loop | 261 | 0 | 0 | 261 | `server.py` |
| ops | 28 | 20 | 0 | 48 | `Makefile`, `pyproject.toml` |

The prompt is `cedar_clinic.instructions.system_prompt()`, imported rather
than restated, so the instruction text counts for nobody here; the Rasa
version restates it in YAML and Markdown and counts it as agent logic.

## What the live run recorded

All from [`../results/strands/`](../results/strands/), 2026-10-01, the same
Mac as the Rasa runs.

| Run | Calls | Passed | Guard violations | Spend USD |
|---|---|---|---|---|
| `2026-10-01-speechmatics-live` (all 17 calls; the headline, and the only full run) | 17 | 16 | 0 | 0.70 (model 0.59, speech-to-text 0.10) |
| `2026-10-01-guard-off-adversarial` (the 6 adversarial calls, guard off) | 6 | 6 | 0 | 0.20 |
| `2026-10-01-deepgram-live` (all 17 calls on Deepgram speech in and out, through `../shared/speech-deepgram`; this folder unchanged) | 17 | 14 | 0 | 0.92 (model 0.56, speech-to-text 0.11, TTS 0.24) |

By kind: normal 4 of 4, adversarial 6 of 6, recovery 2 of 3, correction 4 of
4. The failure, `recovery-second-verification`, is the agent's: after a
wrong date the model asked for the full name again instead of reusing it,
and the caller only gave the corrected date, so the patient was never
verified. Nothing was sent. The prompt was not changed after the run, so
there is no rerun. The details are in
[`../results/strands/README.md`](../results/strands/README.md).

**Latency per caller turn**, p50 (p95), n=39:

| Part | ms |
|---|---|
| End of caller speech to first bot audio | 3,753 (5,659) |
| End of speech to transcript | 1,450 (1,745) |
| Agent processing: final transcript to the first sentence ready for TTS | 1,079 (1,595) |
| TTS first byte (one sentence) | 1,098 (2,452) |
| Model calls per turn | 2 (3) |

The first audio was a filler in 29 of 39 turns.

**Spend:** 0.6952 USD for the full run, 73 model calls, all to
`/v1/responses`. 1.09 USD across everything in the ledger for the build,
including 0.08 of model calls while building; 3.18 USD with the comparison's
harder-set and Deepgram runs. On Deepgram the first audio came at 3,043 ms
at p50 (3,753 on Speechmatics); see
[`../COMPARISON.md`](../COMPARISON.md#deepgram-in-and-out-all-three).

**Voice behaviour:** barge-in not delivered; silence check-in delivered in
code, not tested; fillers, turn-splitting handling, markers, latency fields
and sentence chunking delivered; no TTS cache. See the checklist in
[`../results/strands/README.md`](../results/strands/README.md#voice-behaviour-checklist).

## What makes the comparison uneven

- **Prompt timing.** This run used the shared procedure after the Rasa
  build's fix (call `send_refill_request` straight away, pass descriptions to
  `select_medication`). The Rasa headline, 12 of 17, was before that fix; its
  rerun of the five failures after the fix passed four. Rasa was then rerun
  in full on the shared prompt: 16 of 17 in one run
  ([`../COMPARISON.md`](../COMPARISON.md)).
- **Who judges the yes.** Here a fixed rule decides whether the caller
  confirmed; in Rasa the model does, with a model call. The rule saves a
  model call and its latency on every confirmation turn, and fails closed on
  phrasings it does not know. No spec call hit such a phrasing.
- **The confirmation turn.** A caller who names another medicine at the
  read-back has it selected and read back in the same turn here (the
  guard hands the model their words); Rasa speaks the decline and takes the
  new medicine a turn later, which is why Rasa failed
  `correction-other-medicine-at-confirmation` and this build passed it.
- **Streaming.** This build streams model text and speaks the first
  sentence while the rest is written; the Rasa version's model calls were
  not streamed. Its agent processing is measured to the first sentence, Rasa's
  to the first whole message.
- **Fillers** are fixed phrases after the tools here and Mantle's own
  fillers before them there; both count as the first audio.
- **Model calls and tokens.** 73 calls and 113,308 input tokens here against
  173 and 358,692 for Rasa's first run (178 and 391,498 in its shared-prompt
  rerun) over the same 39 turns: 2 calls per turn at the median here, 5
  there, with a larger prompt per call. That is the framework layer, not the
  task, and it is most of the cost difference (0.70 against 1.84 and 2.01
  USD).
- **Line counts.** The shared instruction text is imported here and restated
  in the Rasa version; the guard diff here counts 30 docstring lines.
- **What Rasa's runtime has that this loop does not:** a TTS cache, barge-in
  (off in both headline runs) and a `/session_end` turn. This loop has been
  run for one evening: two smoke calls, 23 spec calls and one page check.
- **One run each, not at the same moment.** The Rasa run started at 22:27
  UTC and this one at 23:19 UTC on 2026-09-30, and the LangGraph build was
  running its own calls on the same keys at the time.

## Where Strands was easy, and where it was hard

**Easy.**

- **Tools.** `@tool(name=..., description=..., inputSchema=...)` takes the
  shared `TOOL_SPECS` verbatim, so the model sees exactly the other versions'
  words without writing docstrings to match.
- **The guard.** Interventions fit the rule closely. `Deny` is a one-line,
  fail-closed gate; `Confirm` with no response is exactly "pause, ask, and
  wait for the caller's next turn", and it is enforced at tool execution, not
  in the prompt. Agent state is not sent to the model. The decision part is
  72 lines of code in one file, and it is testable offline with a scripted
  model (`tests/test_strands.py`).
- **Streaming.** `Agent.stream_async` yields text deltas and completed
  messages, which is all the sentence chunker needs.
- **Cost.** A thin prompt and one model call per step: 73 calls for 39 turns.

**Hard.**

- **Voice is yours to write.** Strands' voice agent is experimental and
  speech-to-speech only, so there is nothing to plug Speechmatics into. The
  protocol, turn taking, chunking, markers, latency fields, fillers and the
  silence check-in are 261 lines in `server.py`, against 58 lines of YAML in
  the Rasa version. Barge-in and a TTS cache would be more.
- **The documented OpenAI path did not work with the comparison's model
  setting.** The docs' example is `OpenAIModel`; with GPT-5.5, tools and
  `reasoning_effort` together, Chat Completions refuses the request, and the
  fix was the Responses model class.
- **Resuming an interrupt drops the caller's words.** A resumed agent may
  only be given interrupt responses, so the model never sees what the caller
  said at the confirmation unless you put it somewhere. Here the guard
  appends it to the tool result with a `Transform`. Without that, "No, I
  meant my budesonide" would be a bare cancellation.
- **Deciding what a spoken answer means is on you.** Confirm's `evaluate`
  gets whatever you resume with; the default accepts `y`, `yes` or `True`.
  For speech you need a classifier: a rule (here) or a model call.
- **Parallel tool calls race on state.** The default executor runs tools
  concurrently, so `select_medication` could run before `verify_patient` had
  written the patient id. `SequentialToolExecutor` fixes it, but nothing warns
  you.
- **Cancellation text is fixed.** A denied Confirm always reads
  `CONFIRMATION_FAILED: <prompt>`, and a Deny `DENIED: <reason>`.

## Notes

- The shared prompt is used unchanged (`cedar_clinic.instructions.system_prompt()`):
  its procedure already says the medicine is read back "as part of sending".
  The greeting is seeded into the agent's history as an assistant message,
  so the model knows what the caller heard first.
- Tools run with `SequentialToolExecutor`, so `select_medication` sees the
  patient id when the model calls `verify_patient` and `select_medication`
  in one message.
- The conversations live in memory, one `Agent` per conversation id; a
  restart forgets them. A Strands session manager would persist them,
  including a pending confirmation.
