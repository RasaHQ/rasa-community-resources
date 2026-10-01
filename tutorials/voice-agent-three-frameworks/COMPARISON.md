# One voice agent on Rasa Mantle, LangGraph and AWS Strands Agents: the comparison

The same Cedar Clinic prescription line was built on three frameworks.
Everything else was held equal: the clinic code and its audit log, the tool
descriptions, the instruction text, the model (GPT-5.5 at reasoning effort
low, `/v1/responses`), the Speechmatics calls, the browser_audio protocol and
17 scripted calls with recorded caller audio. The rules are in
[`COMPARISON-PLAN.md`](COMPARISON-PLAN.md). Every number below comes from a
file in [`results/`](results/) or from a command in that plan. All runs were
made on one Mac between 22:27 UTC on 2026-09-30 and 00:30 UTC on
2026-10-01.

**In short.** All three passed 16 of 17 calls on the shared prompt, and no
version broke the guard: no refill request went out without a verified
patient and a caller's confirmation on a later turn. Rasa needed the least
code by far. Its voice loop is 58 lines of YAML; LangGraph and Strands had
to write 315 and 261 lines of server code, and still have no barge-in or TTS
cache. Rasa was also the most expensive and the slowest. It made 178 model
calls against 86 and 73, cost 2.01 USD against 0.70, and took about 1.0 to
1.2 s longer at the median from the end of the caller's speech to the first
audio. Most of the extra calls are engine overhead: one main-loop call per
tool, routing and completion calls, fact discovery, and a turn after every
hangup that nobody hears. The six adversarial calls could not tell the three
guards apart. With the guard removed, every version still passed all six,
because GPT-5.5 followed the prompt.

## The headline runs

| | Rasa Mantle | LangGraph | Strands |
|---|---|---|---|
| Run (`results/<framework>/…`) | `2026-10-01-speechmatics-live-shared-prompt` | `2026-10-01-speechmatics-live` | `2026-10-01-speechmatics-live` |
| Started (UTC) | 2026-09-30 23:56 | 2026-09-30 23:28 | 2026-09-30 23:19 |
| **Passed, of 17** | **16** | **16** | **16** |
| normal / adversarial / recovery / correction | 4/4 · 6/6 · 3/3 · 3/4 | 4/4 · 6/6 · 2/3 · 4/4 | 4/4 · 6/6 · 2/3 · 4/4 |
| Guard violations, all calls / adversarial | 0 / 0 | 0 / 0 | 0 / 0 |
| Refill requests with effect | 11 | 11 | 11 |
| Bot messages with approval wording | 0 of 77 | 0 of 71 | 0 of 70 |

Rasa's first full run (`results/rasa/2026-09-30-speechmatics-live`) used the
procedure before it was changed and passed 12 of 17. It is kept as history.
The other two versions were only ever run on the changed, shared procedure.

**Failures, and whose they are.** Every run had one failure, and each was
read from the version's own conversation record.

| Call | Rasa | LangGraph | Strands | Cause |
|---|---|---|---|---|
| `recovery-second-verification` | pass | **fail** | **fail** | After a wrong date, the caller gives only the corrected date. LangGraph and Strands asked for the name and date together again, instead of calling `verify_patient` with the name they already had. Speech-to-text heard the turn correctly, and LangGraph failed again on a repeat with nothing changed. **Agent logic**: the model reading the shared procedure's "ask once more for both details" literally |
| `correction-other-medicine-at-confirmation` | **fail** (both runs) | pass | pass | At the read-back the caller says "No, wait, not that one. I meant my budesonide inhaler." Mantle's decline path speaks the decline and ends the turn, so the budesonide is selected and read back one turn later, after the script has run out. The other two guards hand the caller's words back to the model in the same turn. **Framework behaviour plus script length**: the outcome is correct, but one turn late |

## Latency per caller turn

p50 (p95), n=39 turns in each run, in ms. The definitions are in the plan.

| Part | Rasa Mantle | LangGraph | Strands |
|---|---|---|---|
| **End of caller speech to first bot audio** | **4,971 (7,050)** | **3,968 (5,382)** | **3,753 (5,659)** |
| End of speech to transcript (Speechmatics' 0.7 s end of utterance, finalisation, network) | 1,574 (1,750) | 1,585 (1,845) | 1,451 (1,745) |
| Agent processing: final transcript to first message ready for TTS | 2,295 (3,731) | 1,093 (2,171) | 1,079 (1,595) |
| TTS first byte (Speechmatics returns a whole WAV per request) | 1,187 (2,482) | 1,146 (2,084) | 1,098 (2,452) |
| Time to first byte of the turn's first model call | 2,193 (3,281) | 461 (1,098) | 509 (1,394) |
| Model calls per turn | 5 (7) | 2 (3) | 2 (3) |
| First audio was a filler | 35 of 39 turns | 30 of 39 | 29 of 39 |

The speech parts are the same within about 0.1 s. The gap is in agent
processing, and it comes from two things:

- **Rasa's model calls are not streamed.** Mantle streams the model only when
  the channel's TTS engine accepts streaming text
  (`VoiceOutputChannel.supports_streaming` returns
  `tts_engine.streaming_input`, in `rasa/core/channels/voice_stream/voice_channel.py`).
  Every built-in TTS engine sets it; the base class default is `False`. The
  Speechmatics engine here synthesises one utterance per HTTP request, so
  Rasa waits for the whole first model response (2.2 s at p50) before its
  filler can be spoken. LangGraph and Strands stream, and have a first byte
  in about 0.5 s.
- **Mantle's prompt is twice the size.** An orchestrator call carries about
  2,580 input tokens on average (278,429 over 108 in-turn calls), against
  about 1,290 for LangGraph and 1,550 for Strands.

## Model calls, tokens and cost

| Run | Model calls | Input tokens (cached) | Output (reasoning) | Model USD | Speech-to-text USD | Total USD |
|---|---|---|---|---|---|---|
| Rasa, shared prompt (headline) | 178 | 391,498 (68,096) | 7,878 (758) | 1.887 | 0.123 | **2.010** |
| Rasa, first run (history) | 173 | 358,692 (65,536) | 7,576 (681) | 1.726 | 0.117 | 1.843 |
| LangGraph | 86 | 110,816 (10,752) | 2,730 (355) | 0.588 | 0.112 | **0.699** |
| Strands | 73 | 113,308 (10,752) | 2,505 (289) | 0.593 | 0.102 | **0.695** |

Model cost is the meter's: token usage times OpenAI's published price for
`gpt-5.5-2026-04-23`. For both Rasa runs, LiteLLM's own cost, logged inside
the agent, agreed with the meter. Speech-to-text is priced at 0.43 USD per
hour streamed. TTS is in Speechmatics' free preview and has no published
price, so it is not priced.

### Where Rasa's 178 calls go

The rerun was started through
[`shared/spec/rasa_call_purposes.py`](shared/spec/rasa_call_purposes.py),
which labels each model call with the Mantle function that made it. It
changes no request. `python3 shared/spec/rasa_call_breakdown.py results/rasa/2026-10-01-speechmatics-live-shared-prompt`
gives:

| Purpose (Mantle function) | During caller turns | After the hangup | Input tokens | USD |
|---|---|---|---|---|
| Orchestrator iteration (`Orchestrator._call_main_llm_with_empty_retry`) | 108 | 17 | 335,688 | 1.493 |
| Fact discovery (`ContextExtractor.discover_facts`, after a skill switch, off the reply path) | 17 | 17 | 33,800 | 0.278 |
| Response rephrasing (`Orchestrator._rephrase_and_send`) | 2 | 17 | 22,010 | 0.117 |
| **Total** | **127** | **51** | 391,498 | 1.887 |

- **51 calls (29%, 0.42 USD) come after the caller hangs up.** Mantle runs one
  more turn on `/session_end` for each call. It is an orchestrator call, a
  rephrased "Can I help with anything else?", and a fact discovery. Nobody
  hears any of it. The other two versions do nothing after a hangup.
- **One orchestrator call per tool.** The model returned one tool call per
  iteration. Of the 125 iterations, 17 returned `activate` (entering the
  skill), 14 `complete_skill`, 13 `resolve_tool_confirmation`, 3
  `cancel_skill` and 2 `cannot_help`. That makes 49 iterations for engine
  tools, against 51 for the clinic's tools (`verify_patient` 17,
  `select_medication` 16, `send_refill_request` 14, `route_clinical_question`
  3, `check_request_status` 1), 23 that returned text, and 2 empty ones
  retried. LangGraph and Strands call the clinic's tools directly, often two
  in one model response, and judge the confirmation with a structured call
  (LangGraph, 13 calls) or a fixed rule (Strands, no call).
- **Fact discovery: 34 calls, 0.28 USD.** No completion-judge calls were
  made.

For the first run, which had no labels, the LiteLLM log and the trackers give
the same picture: 35 fact-discovery calls (one per
`mantle.processor.discover_facts.completed` event), 20 rephrased messages
(one call each) and 118 other in-turn calls.

### Why there is no "tuned" Rasa run

The plan allowed one extra run with documented settings. The 3.21.0.dev5
wheel has no setting for the largest items above:

- Fact discovery runs whenever a turn switches skill
  (`MantleMessageProcessor._maybe_discover_facts` in `rasa/mantle/processor.py`),
  with no switch.
- The `/session_end` turn has no switch either.
- The `orchestrator:` block of `agent.yml` holds only preconditions
  (`OrchestratorConfig` in `rasa/mantle/config/agent_spec.py`).
- Streaming would need a Speechmatics engine that accepts streaming text,
  which is code, not a setting.

Two things are settings:

- `metadata.rephrase` is per response (`rasa/mantle/content/responses.py`). The
  rephrased message is `utter_ask_wants_to_continue`, a response of Mantle's
  own default skill, and overriding it from the project was not verified.
- `prompts.ack_enabled` would turn off the fillers. Fillers come inside the
  main call, so turning them off saves no call and delays the first audio.

The phase's budget left about 0.20 USD in any case. So the comparison
reports Rasa as shipped only.

## Code per concern

The rule is the plan's (`shared/spec/count_concerns.py`): non-blank lines that
are not only comments, with docstrings excluded, grouped by each file's
declared concern.

| Concern | Rasa Mantle | LangGraph | Strands |
|---|---|---|---|
| Agent logic, as counted | 137 (46 code, 59 config, 32 prose) | 64 code | 115 code |
| Agent logic, restated shared instruction text left out | **94** | **64** | **115** |
| Refill guard (restated text left out) | 47: 21 code, 26 config (44) | 112 code | 92 code |
| **Voice adapter**: the Speechmatics clients | 213 code (`rasa/engines/`, custom Rasa engine classes) | 251 code (`shared/speech`, counted for each) | 251 code (`shared/speech`, counted for each) |
| **Voice loop**: everything else that moves audio or runs the call | **58 config** (the `channels` block) | **315 code** | **261 code** |
| Ops | 49 | 47 | 48 |

About instruction text. LangGraph and Strands import the prompt from
`cedar_clinic.instructions`, so it counts for nobody. Rasa restates it in
`agent.yml`, `responses.yml` and the skill's Markdown, which Mantle reads.
Of those lines, 46 match the shared text word for word: 43 agent logic and 3
refill guard (`count_concerns.py rasa --shared-text`; 0 for the other two).
The second row leaves them out, so all three are counted without shared
prompt text.

## The guard

| | Rasa Mantle | LangGraph | Strands |
|---|---|---|---|
| Identity and selection | Memory only tools write (not `llm_settable`) | `PrivateStateAttr` graph state written by tools through `Command` | `agent.state`, written by tools and not sent to the model |
| Send blocked until a medicine is selected | `requires` tool gate: hidden from the model and refused at dispatch, failing closed | `wrap_model_call` filter plus `wrap_tool_call` gate | `Deny` from an intervention handler (`on_error: deny`) |
| Read-back and later-turn confirmation | `requires_confirmation`: the engine pauses the call and speaks the fixed question; the tool runs only after a later turn is resolved as yes | `interrupt()` in `wrap_tool_call`; the next turn resumes it with `Command(resume=...)` | `Confirm` intervention on a Strands interrupt; the next turn resumes it with the caller's words |
| Who decides the answer was yes | The orchestrator model, by calling `resolve_tool_confirmation` | A separate structured-output model call | A fixed rule (`caller_said_yes`); no model call, and it refuses phrasings it does not know |
| Enforced at execution, not in the prompt | Yes | Yes | Yes |
| Guard diff from the guard-off baseline, docstrings excluded | **+67 −18 (85)**, mostly YAML, in 5 files | **+132 −30 (162)** in 3 files, 18 lines of them in the voice loop | **+114 −29 (143)** in 2 files |
| Guard-off baseline, 6 adversarial calls | 6/6 passed, 0 violations, 0.48 USD | 6/6 passed, 0 violations, 0.21 USD | 6/6 passed, 0 violations, 0.20 USD |

The guard diffs are counted by `count_concerns.py <framework> --diff`. It now
skips docstring lines on both sides: the shipped file for added lines, and
the guard-off copy (the diff reversed) for removed lines.

**The guard-off result.** In all three baselines the model passes the patient
id and records the confirmation itself. In the two adversarial calls where a
request was sent, GPT-5.5 read the question on the first turn and sent on the
second, after the caller's yes. So these six prompts did not get past the
model, and they cannot show what the guards add. What the guards guarantee
is that the rule still holds when the model does not follow the prompt. A
stronger adversarial set would be needed to measure that.

## Voice behaviour checklist

| Behaviour | Rasa Mantle | LangGraph | Strands |
|---|---|---|---|
| Barge-in | In the runtime; **off** (`interruptions.enabled: false`, the default on 3.21.0.dev5, beta when on); not tested | Not implemented; off | Not implemented; caller audio keeps going to speech-to-text while the agent speaks |
| Silence check-in after 30 s | Runtime (`silence_timeout: 30` with Mantle's silence skill); configured, not tested | Written; exercised in a separate live call | Written; not tested |
| Fillers while a tool runs | Runtime (Mantle's, before tools); 35 of 39 turns | Written (fixed phrase when a tool call starts streaming); 30 of 39 | Written (fixed phrase after tools); 29 of 39 |
| Turn-splitting handling | Speechmatics `EndOfUtterance` in the engine; 0 of 39 split | Same, via `cedar_speech`; 0 of 39 | Same; 0 of 39 |
| Playback markers and latency fields | Runtime | Written | Written |
| Sentence chunking for TTS | Per bot message (no streaming with this engine) | Streamed text cut at sentence ends | Streamed text cut at sentence ends |
| TTS cache | Runtime | None | None |
| Work after the hangup | One `/session_end` turn (3 model calls) | None | None |

## Spend in this comparison

| Ledger (`results/<framework>/spend-ledger.json`) | Recorded USD |
|---|---|
| Rasa (smoke runs, first run, rerun of failures, headline rerun, guard-off) | 5.310, plus 0.25 estimated for an unmetered page check |
| LangGraph (including its guard-off run) | 1.117 |
| Strands | 1.086 |

This phase spent 2.81 USD of its 3 USD budget: a one-call smoke run (0.11),
the Rasa headline (2.01), Rasa guard-off (0.48) and LangGraph guard-off
(0.21). No call hit `insufficient_quota`.

## Where the comparison is uneven

**In Rasa's favour:**

- **The voice loop is the runtime.** Fifty-eight lines of YAML stand against
  315 and 261 lines of code, and the runtime also brings a TTS cache, a
  barge-in path and playback tracking. The other two loops have run for one
  evening each.
- **Its voice adapter is in its own folder and is smaller** (213 lines
  against 251), but it is a copy of adapters the companion had already
  written and tested.
- **The guard diff is mostly declarative.** It counts YAML lines, and YAML
  comments explain the rest.
- **It passed the call both others failed.** On
  `recovery-second-verification`, with the same procedure text, Mantle's
  model called `verify_patient` again with the name it already had and the
  corrected date.

**Against Rasa:**

- **The vendor choice costs Rasa streaming.** Speechmatics' preview TTS takes
  a whole utterance per request, and Mantle streams the model only into a TTS
  engine that accepts streaming text. With a built-in engine that streams
  (Deepgram, Cartesia, Rime, Azure) the first audio would come sooner. That
  was not measured here.
- **The prompt is longer, and the instruction text is counted.** The first
  is Mantle's own machinery. The second is shown both ways above.
- **Rasa was rerun.** It has two full runs, and the first used the procedure
  before it was changed. The headline is the rerun on the shared text. The
  other two had one full run each, after the change.
- **The decline turn.** Mantle's decline path cost one turn. The script
  allows no extra turn; a real caller would get the right result one turn
  later.

**In LangGraph's and Strands' favour:**

- **Streaming,** which the Rasa build could not use with this TTS. It is
  covered above.
- **Strands judges the yes with a rule,** which saves a call and its latency
  on every confirmation turn, but would refuse a yes phrased in a way the
  rule does not know.
- **They were built after the Rasa version,** against a finished protocol, a
  finished spec runner and a working reference.

**Against LangGraph and Strands:**

- **They had to write the voice loop, and it is incomplete.** There is no
  barge-in. LangGraph's own docs say interrupting a run in flight is a
  LangSmith Deployment feature, not open-source LangGraph. There is no TTS
  cache. Strands' voice agent (`BidiAgent`) is experimental and
  speech-to-speech only, so it could not run Speechmatics.
- **The documented OpenAI path failed.** Both had to move from Chat
  Completions to the Responses API, because Chat Completions refuses function
  tools with `reasoning_effort` for this model.
- **Framework sharp edges.** LangGraph re-runs a node on resume, and its
  `PrivateStateAttr` is not on the docs pages. A resumed Strands interrupt
  drops the caller's words, and its default parallel tool executor races on
  state.

**For all three:** one run each, on one Mac, within about two hours, and
sharing the OpenAI and Speechmatics keys while the builds overlapped.

## What each framework made easy, and what it made you write

**Rasa Mantle.**
- *Easy:* the voice loop, which is configuration. The hard guard is a
  declarative block that is enforced at execution (`requires`,
  `requires_confirmation`). So are fillers, the silence check-in, playback
  tracking, the TTS cache and barge-in (when switched on), all in the
  runtime.
- *Had to write:* a custom engine class for a speech vendor Rasa does not
  ship (213 lines), and the instruction text again in Mantle's files.
- *Cost:* 2 to 3 times the model calls and tokens of the other two, about
  1 s more to the first audio with this TTS, and work after every hangup.
  There are no settings in this release to turn the largest overheads off.

**LangGraph (with LangChain's `create_agent`).**
- *Easy:* the agent and the tools, in a few lines. The guard pieces compose:
  private state, `Command` updates, a middleware tool filter and gate, and
  `interrupt()`. All of it is testable offline with a scripted model.
- *Had to write:* the whole voice loop (315 lines). The guard also reaches
  into it: the loop must speak the interrupt's question and resume with the
  next turn. A model call judges the yes.
- *Cost:* the cheapest model use, with fast first bytes from streaming. Still
  missing barge-in and a TTS cache.

**AWS Strands Agents.**
- *Easy:* tools straight from `TOOL_SPECS`. Interventions fit the guard
  closely: `Deny` is a one-line gate that fails closed, and `Confirm` is
  "pause and wait for the next turn". The fewest model calls, 73.
- *Had to write:* the whole voice loop (261 lines), a rule to judge a spoken
  yes, a `Transform` to give the model the caller's words after a resume, and
  a switch to the sequential tool executor.
- *Cost:* the lowest latency at the median and the same price as LangGraph.
  Still missing barge-in and a TTS cache.
