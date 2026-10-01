# Cedar Clinic refill requests on LangGraph: the LangGraph version of one voice agent built three ways

```text
Author:        Rasa Community
Assessed on:   2026-10-01
Assessed by:   Claude Code (phase 2 of the three-framework tutorial; live runs in ../results/langgraph/)
Verified with: langgraph 1.2.12, langchain 1.4.3, langchain-openai 1.6.7, Python 3.12, uv, macOS 26.6.2
Audience:      Engineers comparing Rasa Mantle, LangGraph and Strands for a voice agent with a hard guarantee
Time:          10 minutes to run; about 20 minutes and under 1 USD for the live spec
```

The LangGraph version of the Cedar Clinic prescription line, one of three
builds of the same agent ([`../README.md`](../README.md)). A caller asks for
a refill; the agent verifies them, finds the medicine on their record, reads
it back and sends a request to the prescribing team. It never approves
anything. Cedar Clinic is fictional.

- **Agent:** LangChain's `create_agent` (which compiles to a LangGraph graph)
  with an `InMemorySaver` checkpointer; the `thread_id` is the conversation
  id from `X-Rasa-Sender-Id`. `create_react_agent` is deprecated and not used.
- **Model:** `ChatOpenAI(model="gpt-5.5-2026-04-23", reasoning_effort="low",
  use_responses_api=True)`, streamed. The meter logged every call as
  `POST /v1/responses`, the same API Rasa's LiteLLM client called (Rasa's
  calls were not streamed; these are).
- **Speech:** Speechmatics realtime speech-to-text and preview
  text-to-speech (voice `megan`) through the shared
  [`cedar_speech`](../shared/speech/) clients, the same vendor calls as the
  Rasa version's engines.
- **Voice loop:** written here, in [`voice_loop.py`](voice_loop.py) and
  [`server.py`](server.py): asyncio, Starlette and uvicorn. LangGraph and
  LangChain have no audio components.
- **Domain:** the shared [`cedar_clinic`](../shared/clinic/) package, the
  same code the Rasa and Strands versions call.

## Quick start

```bash
make install     # uv sync --locked: langgraph, langchain, langchain-openai, starlette, uvicorn, cedar_clinic, cedar_speech
make env         # fill OPENAI_API_KEY and SPEECHMATICS_API_KEY (or use the repository-root .env)
make test        # offline: scripted model, fake TTS, no network
make run         # ws://localhost:5006/webhooks/browser_audio/websocket, /conversations/<id>/events, /health
make web         # in another shell: the shared voice page on http://127.0.0.1:8765/
make spec        # the shared spec, 17 calls over browser audio (billed)
```

Say: "I'm Maria Alvarez, born March fourteenth, nineteen sixty-eight. I need
a refill of my lisinopril." Then answer the read-back question.

## Required secrets

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | GPT-5.5 (`agent.py`) |
| `SPEECHMATICS_API_KEY` | Speech in and out, read by `cedar_speech` when a call starts |

## The refill guard

The hard guarantee is: no refill request without a patient verified on the
call and a medicine the caller confirmed on a later turn. `cedar_clinic`
refuses a send it can see is wrong. What makes the guarantee hold in this
version is enforced at execution, with LangChain and LangGraph mechanisms,
not by the prompt:

| Mechanism | Where | What it does | Docs |
|---|---|---|---|
| Custom agent state, private | `RefillState` in [`guard.py`](guard.py), declared as the middleware's `state_schema` | `patient_id`, `selected_record_id` and `selected_label` are graph state annotated `PrivateStateAttr`, so they are not in the graph's input or output schema: a test passes them in the input and they are ignored | [Custom middleware: custom state schema](https://docs.langchain.com/oss/python/langchain/middleware/custom). `PrivateStateAttr` is in `langchain.agents.middleware.types` (LangChain uses it for its own `jump_to`); the docs page does not mention it (checked 2026-10-01) |
| Tools write that state with `Command` | refill-guard regions of [`agent.py`](agent.py) | `verify_patient` and `select_medication` return `Command(update=...)` with the id and the `ToolMessage`; tools read it through `ToolRuntime`. No tool takes a patient id from the model, and `verify_patient` removes it from what the model sees | [Tools: ToolRuntime, Command](https://docs.langchain.com/oss/python/langchain/tools) |
| `wrap_model_call` tool filter | `RefillGuard.awrap_model_call` | `send_refill_request` is left out of the tools offered to the model until a record entry is selected | [Custom middleware: wrap_model_call](https://docs.langchain.com/oss/python/langchain/middleware/custom) |
| `wrap_tool_call` gate | `RefillGuard.awrap_tool_call` | A send whose record id is not the selected entry is refused before the tool runs (fails closed) | same |
| `interrupt()` for the read-back | same | The guard calls `interrupt()` with `confirmation_question(label)` built from state. The run stops; the voice loop speaks the question and ends the turn. The next caller turn is sent as `Command(resume=...)`, the only way the run continues, so the answer is always from a later turn. A model call with structured output judges yes or no, `record_confirmation` is written with the caller's words, and only a yes runs the tool. A no speaks the shared `DECLINED_TEXT` and returns the caller's words to the model, so a named medicine can be selected in the same turn | [Interrupts: interrupts in tools, rules of interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) |

Like Rasa, the model still decides whether the caller's answer was a yes;
here that is a separate structured-output call inside the guard (the
`CallerAnswer` schema), where Rasa's orchestrator calls its own
`resolve_tool_confirmation` tool. The guard guarantees the pause, the fixed
read-back from state, the later turn and the audit record.

Why not `HumanInTheLoopMiddleware`: it pauses after the model proposes a
tool call and resumes with `approve`, `edit` or `reject` decisions from a
reviewer ([Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)).
A voice caller answers in words, so something still has to turn the words
into a decision, and the question must read back the medicine from state
and the caller's words must reach the clinic's audit log. The interrupts
page shows `interrupt()` inside a tool for exactly this approval shape, and
the same call inside `wrap_tool_call` keeps the tool body free of it.

The rules of interrupts matter here. On resume LangGraph re-runs the whole
node from the start, so everything before `interrupt()` in the guard is
free of side effects. `create_agent` dispatches each tool call as its own
`Send` task (`langchain/agents/factory.py`), so a tool that ran beside the
paused send in the same model turn is not run again.

[`guard.diff`](guard.diff) is the whole guard as a diff from the guard-off
baseline in [`../COMPARISON-PLAN.md`](../COMPARISON-PLAN.md): the same
tools with a `patient_id` parameter the model fills in, verify's result with
the patient id shown to the model, the procedure's step 4 telling the model
to read the question and wait for a yes, and the send tool recording the
confirmation itself (`mechanism: "none: the model decided"`). In a copy of
this folder, `patch -R -E -p1 < guard.diff` gives the baseline, which
imports and runs (checked with the scripted model: it sends on the model's
say-so). By the plan's line rule (`python3 ../shared/spec/count_concerns.py . --diff`)
it is **161 lines added and 32 removed** in 3 files: `guard.py` +110,
`agent.py` +33 -32, `voice_loop.py` +18. The diff counter cannot tell a
docstring from code; without the docstring lines it adds (29) and removes
(2), it is +132 -30.

## Code per concern

Every counted file declares its concern. By the plan's rule (non-blank lines
that are not only a comment, docstrings excluded;
`python3 ../shared/spec/count_concerns.py .`):

| Concern | Code | Config | Total | Files |
|---|---|---|---|---|
| agent-logic | 64 | 0 | 64 | `agent.py` |
| refill-guard | 112 | 0 | 112 | `guard.py` (84), the state regions of `agent.py` (11), the resume and guard lines of `voice_loop.py` (17) |
| voice-adapter | 251 | 0 | 251 | `../shared/speech` (`cedar_speech`), shared with Strands; nothing in this folder |
| voice-loop | 315 | 0 | 315 | `voice_loop.py` (263), `server.py` (52) |
| ops | 27 | 20 | 47 | `Makefile`, `pyproject.toml` |

## What the live run recorded

All from [`../results/langgraph/`](../results/langgraph/), 2026-10-01, the
same Mac as the Rasa runs.

| Run | Calls | Passed | Guard violations | Spend USD |
|---|---|---|---|---|
| `2026-10-01-speechmatics-live` (all 17 calls; the headline, first and only full run) | 17 | 16 | 0 | 0.70 (model 0.59, speech-to-text 0.11) |
| `2026-10-01-speechmatics-repeat-no-change` (the failed call again, nothing changed) | 1 | 0 | 0 | 0.04 |

All runs, smoke tests and checks together: 0.91 USD in
`../results/langgraph/spend-ledger.json`.

- **The failure** was `recovery-second-verification`: after a wrong date,
  the caller corrected only the date, and GPT-5.5 asked for the name and
  date together instead of calling `verify_patient` with the name it
  already had. It did the same in the repeat, where speech-to-text heard
  every word right. That is agent logic (the shared procedure says "ask
  once more for both details"), and the Rasa version passed the same call.
  The shared procedure was not changed, so there is no second full run.
- **The call Rasa failed and this version passed** was
  `correction-other-medicine-at-confirmation`: "No, wait, not that one. I
  meant my budesonide inhaler." The guard records the decline, speaks the
  shared decline line and hands the caller's words back to the model in the
  same run, so it selects the budesonide and asks its question on that turn.
  Mantle took the new medicine one turn later.
- **Latency per caller turn**, p50 (p95), n=39: 3,968 (5,382) ms from the
  end of the caller's speech to the first bot audio: 1,585 (1,845) to the
  transcript, 1,093 (2,171) of agent processing, 1,146 (2,084) to
  Speechmatics TTS's first byte. The first audio was a filler in 30 of 39
  turns. 2 model calls per turn at p50 (3 at p95).
- **Model use:** 86 calls and 110,816 input tokens for 17 calls, 0.59 USD.
  Rasa's first run made 173 calls with 358,692 input tokens (1.73 USD) for
  the same calls, and its rerun on the shared prompt 178 calls with 391,498
  (1.89 USD; where they go is in [`../COMPARISON.md`](../COMPARISON.md)). 13
  of the 86 are the guard's yes/no judgement.

The full breakdown, with speech-to-text accuracy and the behaviour checklist,
is in [`../results/langgraph/README.md`](../results/langgraph/README.md).

## Voice behaviour

| Behaviour | This build |
|---|---|
| Barge-in | Not implemented; off for the headline run. See below |
| Silence check-in | 30 s after the last bot audio was acknowledged, with no caller speech (`SILENCE_TIMEOUT_S`, Rasa's `silence_timeout: 30`); exercised in a separate live call, not by the spec |
| Fillers while a tool runs | A fixed phrase per tool when the streamed model output begins a tool call and nothing has been said in the turn, and one when a caller's yes is accepted; first audio in 30 of 39 turns |
| Turn splitting | Speechmatics' `EndOfUtterance` joins segments; turns are queued and answered in order; 0 of 39 split |
| Playback markers, latency fields | Start, one per second, end with the three latency fields, on every sentence |
| Sentence chunking | Streamed model text is cut at sentence ends; each sentence is synthesised while the model keeps streaming and played in order |
| TTS cache | None |

**Barge-in and "double texting".** Cancelling a run that is in flight, or
interrupting it with new input, is a LangSmith Deployment feature: "Double
texting is a feature of LangSmith Deployment. It is not available in the
LangGraph open source framework"
([double texting](https://docs.langchain.com/langsmith/double-texting)).
So barge-in on open-source LangGraph means cancelling the asyncio task that
runs `astream` yourself, stopping the audio, and deciding what the
checkpoint holds: a cancelled run keeps the last completed step, so a
half-spoken reply or a tool that already ran stays in the history unless you
remove it. None of that is written here; barge-in is off in all three
headline runs.

## What had to be built, and where it was easy or hard

**Easy.**

- The tools. Five thin bindings from `TOOL_SPECS` (names, descriptions and
  parameter schemas generated, not copied), and the shared prompt used
  verbatim. `create_agent` with a checkpointer gave a multi-turn agent in a
  few lines.
- The guard's pieces exist and compose: private state, `Command` updates
  from tools, a tool filter and a tool gate in one middleware class, and
  `interrupt()`. The offline tests drive the real graph with a scripted
  model, so every guard rule is tested without a model call.
- The confirmation step handles a correction in the same turn, which the
  spec's hardest correction call needed.

**Hard, or at least work.**

- **The voice loop is all yours.** 315 counted lines of asyncio and
  Starlette for what Rasa configures in 58 lines of YAML: the protocol,
  forwarding audio, turn queueing, streaming the graph and chunking
  sentences, parallel synthesis with in-order playback, markers and latency,
  fillers, the silence check-in, the events endpoint and hangup. It has no
  barge-in, no TTS cache, no reconnects and no telephony.
- **The guard touches the voice loop.** The run pauses in `interrupt()`, so
  the loop must know to speak the question from the interrupt, and to send
  the next caller turn as `Command(resume=...)` instead of a new message.
  Those 17 lines are counted as refill-guard.
- **`PrivateStateAttr` is not on the docs pages.** The custom-middleware
  page shows custom state, not how to keep a field out of the graph's input;
  the annotation had to be found in `langchain.agents.middleware.types`.
- **The API default failed.** `ChatOpenAI` sends Chat Completions unless told
  otherwise, and OpenAI refused function tools with `reasoning_effort` for
  `gpt-5.5-2026-04-23` there (HTTP 400, `2026-10-01-smoke-text/`).
  `use_responses_api=True` fixed it.
- **Interrupt semantics need care.** The node re-runs from the top on
  resume, so the guard keeps side effects after `interrupt()`, and a test
  checks that a tool called beside the paused send is not run twice.
- **Who judges the yes.** The resume value is the caller's words, so a
  model call has to judge them (as in Rasa); the guard makes a separate
  structured-output call for it, about 1.5 s on each confirmation turn.

## What makes the comparison uneven

In LangGraph's favour:

- **Instruction text is not counted here.** The prompt is built from
  `cedar_clinic.instructions` at import. Rasa copies the persona, rules,
  procedure and responses into its YAML and skill files, where they count as
  agent logic (137 lines there, 64 here; 94 there without the 43 lines
  that restate the shared text).
- **Streaming.** This version streams the Responses API, so a filler starts
  when the first tool-call chunk arrives. Rasa's model calls were not
  streamed. That lowers agent processing here (1,093 ms against 2,295 ms at
  p50 in Rasa's shared-prompt run).
- **The prompt fix came first.** This run used the shared procedure after
  the change Rasa's first run led to ("do not ask for confirmation
  yourself"). Rasa's four prompt failures passed only in its rerun.
- **Smaller prompts.** About a third of Rasa's input tokens, so lower cost
  and faster first bytes; Mantle's prompt carries its own skill and memory
  machinery.
- **Built by an AI coding agent** with PROTOCOL.md, the spec runner and the
  Rasa version to test against. The line counts say how much had to be
  written, not how long it would take someone starting from LangChain's
  voice tutorial.

Against LangGraph:

- **An extra model call per confirmation** for the yes/no judgement, where
  Rasa's orchestrator does it in its own turn.
- **No TTS cache and no barge-in path**, both in Rasa's runtime.
- **Parallel load.** The Strands build ran at the same time on the same keys.

Also different: the run was a day after Rasa's (2026-10-01 against
2026-09-30), on the same machine.

## Also checked

- The shared voice page, served by `../shared/web/serve.py` and driven by
  headless Chromium (`../shared/web/check_page.py`), completed a call:
  handshake at 24 kHz, the greeting with its markers acknowledged, a spoken
  caller turn from the fake microphone, and a typed "Yes, please send it."
  that sent the request (`../results/langgraph/2026-10-01-web-page-check/`).
  Its model calls went through the meter (0.03 USD).
- `make test`: 22 offline tests (parity with `TOOL_SPECS` and the shared
  instructions, every guard rule with a scripted model, the server end to end
  with a fake TTS, the untagged-file check).
