# One voice agent, three frameworks: Rasa Mantle, LangGraph and AWS Strands Agents

```text
Author:        Rasa Community
Assessed on:   2026-10-01
Assessed by:   Claude Code (shared parts, three versions, comparison; live runs in results/)
Verified with: rasa-pro 3.21.0.dev5; langgraph 1.2.12, langchain 1.4.3, langchain-openai 1.6.7; strands-agents 1.57.1; Python 3.12, uv, macOS 26.6.2
Audience:      Engineers choosing a framework for a voice agent that must not take an unconfirmed action
Time:          20 minutes to run the Rasa version and the voice page; about 40 minutes for the scripted calls (billed)
```

The same voice agent, built three times on three frameworks, so you can see
what each one asks you to write. The agent is the Cedar Clinic prescription line: a caller asks for
a refill, the agent verifies them, finds the medicine on their record, reads
it back, and sends a request to the prescribing team for review. Cedar
Clinic is fictional, and so are its patients and records.

The hard part is one guarantee: **no refill request without a verified
patient and a medicine the caller confirmed.** The model is GPT-5.5
(`gpt-5.5-2026-04-23`, `reasoning_effort: low`) in all three. Speech is
Speechmatics in all three: realtime speech-to-text in, preview
text-to-speech out, with identical vendor calls. Deepgram variants, built
into Rasa and added as a shared client for the other two, run the same
calls without changing the shipped folders.

[`COMPARISON.md`](COMPARISON.md) walks through the three builds side by
side; [`COMPARISON-PLAN.md`](COMPARISON-PLAN.md) has the rules all three
follow.

## Layout

```text
voice-agent-three-frameworks/
  COMPARISON-PLAN.md   the shared rules: what is held equal, how lines and calls are checked
  COMPARISON.md        the three builds side by side
  shared/
    clinic/            cedar_clinic: records, rules, audited tool functions, instruction text (no framework)
    spec/              17 scripted calls with caller audio, the runner, the checks, the LLM meter, the line counter
    speech/            cedar_speech: Speechmatics ASR and TTS clients for the LangGraph and Strands servers
    speech-deepgram/   cedar_speech_deepgram: Deepgram clients behind the same interface, and a launcher (variant only)
    web/               one browser voice page for all three, its relay, PROTOCOL.md
  rasa/                the Rasa Mantle version
  langgraph/           the LangGraph version (LangChain create_agent, written voice loop)
  strands/             the AWS Strands Agents version (interventions, written voice loop)
  variants/            Rasa integrations.yml files for the Deepgram runs (not the shipped build)
  results/<framework>/ recorded runs of the shared spec; results/RUNS.md, how the follow-up runs were launched
```

Everything framework-specific is inside its framework's folder, and every
file there declares its concern (agent logic, refill guard, voice adapter,
voice loop, ops) so the code per concern can be counted by one rule.

## Run the Rasa version

```bash
cd rasa
make install            # rasa-pro 3.21.0.dev5 and the shared cedar_clinic package
make env                # fill RASA_LICENSE, OPENAI_API_KEY, SPEECHMATICS_API_KEY
make test               # offline: parity with the shared parts, guard config, Speechmatics message parity
make train
make run                # browser_audio at ws://localhost:5005/webhooks/browser_audio/websocket
make web                # in another shell: the voice page on http://127.0.0.1:8765/
```

Say: "I'm Maria Alvarez, born March fourteenth, nineteen sixty-eight. I need
a refill of my lisinopril." Then ask whether it is approved.

## Run the shared spec

```bash
python3 shared/spec/run_spec.py rasa --label <run> --budget-usd 4    # billed: GPT-5.5 and speech; --budget-usd caps the run
make test                                                            # offline tests of the shared parts
make count                                                           # lines per concern, guard diffs
```

The same calls on Deepgram, without changing the shipped folders (billed;
`DEEPGRAM_API_KEY` in `.env`):

```bash
make spec-rasa-variant VARIANT=deepgram-tts LABEL=<run>   # Rasa: Speechmatics in, built-in Deepgram TTS out
make spec-rasa-variant VARIANT=deepgram LABEL=<run>       # Rasa: built-in Deepgram both ways
make spec-deepgram FW=langgraph LABEL=<run>               # LangGraph or Strands through shared/speech-deepgram
```

The runner starts the agent, places 17 calls on its browser_audio socket with
recorded caller audio, and judges each call from the clinic's own audit log,
never from a framework's tracker: see [`shared/spec/README.md`](shared/spec/README.md).

## The shared parts

| Part | Interface | Details |
|---|---|---|
| [`shared/clinic`](shared/clinic/) | `cedar_clinic.tools.verify_patient / select_medication / send_refill_request / check_request_status / route_clinical_question(conversation_id, <framework state>, <model args>)`, plus `record_confirmation(...)` called from the framework's confirmation step; `TOOL_SPECS`; `instructions` | Every call is written to `CEDAR_AUDIT_LOG` |
| [`shared/spec`](shared/spec/) | `run_spec.py <framework>`; `checks.py`; `llm_meter.py`; `count_concerns.py` | The runner reuses the case-build harness's voice driver |
| [`shared/speech`](shared/speech/) | `cedar_speech.SpeechmaticsASR` (async: `send_audio`, `events()` of partial/final transcripts), `SpeechmaticsTTS.synthesize(text) -> 24 kHz PCM` | Same messages as the Rasa engines, checked by a test |
| [`shared/web`](shared/web/) | `serve.py <framework>` serves the page and relays with the conversation id; `check_page.py` drives it headlessly | [`PROTOCOL.md`](shared/web/PROTOCOL.md) is the contract every server meets |

## The three builds at a glance

From [`COMPARISON.md`](COMPARISON.md):

| What you write | Rasa Mantle | LangGraph | Strands |
|---|---|---|---|
| Voice loop | 58 lines of YAML configuration; the runtime runs the loop | 315 lines of Python | 261 lines of Python |
| Speech adapter | Deepgram built in (no adapter, a 34-line loop config); Speechmatics as a custom engine (213 lines) | Shared clients: Speechmatics 251 lines, Deepgram 184 | The same shared clients |
| Refill guard | A 7-line `tool_constraints` block enforced by the engine, with memory the model cannot set (47 counted lines in all) | Middleware and `interrupt()` with private graph state (112 lines) | An intervention handler with `Deny` and `Confirm` (92 lines) |
| Read-back pause and resume | `requires_confirmation`: the engine pauses and speaks the question | `interrupt()`, resumed with `Command(resume=...)` | `Confirm` interrupt, resumed with an `interruptResponse` |
| Fillers, silence check-in, playback markers, TTS cache | Runtime | Written in the loop | Written in the loop |

- **All three** passed 16 of the 17 scripted calls, and the guard held in
  every one of them.
- **Streaming:** Rasa streams the model's text into a TTS that accepts
  streamed text, which its built-in engines do; pair it with one.
- **Confirmation timing:** one lesson applies to all three. A caller's
  "yes" spoken before the read-back has finished playing can, if its
  transcript arrives late, be taken as the confirmation. Each build has an
  opt-in `fix.diff` that counts consent only after the read-back has
  played; see
  [`COMPARISON.md`](COMPARISON.md#confirmation-timing-a-voice-design-lesson-for-all-three).

## Where to read more

- [`COMPARISON.md`](COMPARISON.md): the voice loop, speech engines, state
  and guard, the read-back confirmation, the timing lesson with each fix,
  and how to run each build.
- [`COMPARISON-PLAN.md`](COMPARISON-PLAN.md): what is held equal and the
  line-counting rule.
- [`rasa/README.md`](rasa/README.md), [`langgraph/README.md`](langgraph/README.md),
  [`strands/README.md`](strands/README.md): each version, its guard and how
  to run it.
- [`results/`](results/): every recorded run, one folder per framework.

## Scope

- **Synthetic.** Cedar Clinic, Maria Alvarez, Theo Lindqvist and their
  records are invented. Nothing here is medical advice.
- **Synthetic callers.** The caller audio is AI-generated speech (Deepgram
  Aura-2), replayed byte for byte. No person's voice is recorded here.
- **Not on-device.** Speech goes to Speechmatics (or Deepgram in the
  variants) and the model call to OpenAI.
- **One model, one machine, one day.** A different model, release, vendor
  setting or day can behave differently.
