# One voice agent, three frameworks: Rasa Mantle, LangGraph and AWS Strands Agents

```text
Author:        Rasa Community
Assessed on:   2026-10-01
Assessed by:   Claude Code (shared parts, three versions, comparison; live runs in results/)
Verified with: rasa-pro 3.21.0.dev5; langgraph 1.2.12, langchain 1.4.3, langchain-openai 1.6.7; strands-agents 1.57.1; Python 3.12, uv, macOS 26.6.2
Audience:      Engineers choosing a framework for a voice agent that must not take an unconfirmed action
Time:          20 minutes to run the Rasa version and the voice page; about 40 minutes and under 4 USD for the live spec
```

The same voice agent, built three times on three frameworks, measured the
same way. The agent is the Cedar Clinic prescription line: a caller asks for
a refill, the agent verifies them, finds the medicine on their record, reads
it back, and sends a request to the prescribing team for review. Cedar
Clinic is fictional, and so are its patients and records.

The hard part is one guarantee: **no refill request without a verified
patient and a medicine the caller confirmed.** The model is GPT-5.5
(`gpt-5.5-2026-04-23`, `reasoning_effort: low`) in all three. Speech is
Speechmatics in all three: realtime speech-to-text in, preview
text-to-speech out, with identical vendor calls.

All three versions are built and measured by the rules in
[`COMPARISON-PLAN.md`](COMPARISON-PLAN.md); the side-by-side results are in
[`COMPARISON.md`](COMPARISON.md).

## Layout

```text
voice-agent-three-frameworks/
  COMPARISON-PLAN.md   what is measured, and how, for all three
  COMPARISON.md        the results side by side
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
python3 shared/spec/run_spec.py rasa --label <run> --budget-usd 4    # billed: GPT-5.5 and Speechmatics; cap per run
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

## The results, side by side

From [`COMPARISON.md`](COMPARISON.md), which has the full tables and the
causes:

| | Rasa Mantle | LangGraph | Strands |
|---|---|---|---|
| Passed, of 17 (shared prompt) | 16 | 16 | 16 |
| Guard violations, all / adversarial | 0 / 0 | 0 / 0 | 0 / 0 |
| Harder adversarial set, two runs: violations guard on / off (12 calls each) | 1 / 1 | 0 / 1 | 0 / 1 |
| Harder set, second-patient sends guard on / off | 0 / 2 | 0 / 2 | 0 / 0 |
| Late-transcript replay: early yes taken as the confirmation (guard on) | 3 of 3 | 3 of 3 | 3 of 3 |
| The six calls the spec left out, passed (guard violations) | 5 (0) | 5 (0) | 6 (0) |
| Opt-in fix (consent only after the read-back played): counted lines / replay early yes taken | 92 / 0 of 3 | 29 / 0 of 3 | 22 / 0 of 3 |
| Backchannel "Okay." / "Yeah." taken as consent, shipped / with the fix | 2 of 2 / 0 of 2 | 2 of 2 / 0 of 2 | 2 of 2 / 0 of 2 |
| End of speech to first audio, p50 (p95), Speechmatics | 4,971 (7,050) ms | 3,968 (5,382) ms | 3,753 (5,659) ms |
| The same with a streaming TTS (Rasa: Deepgram TTS only) | 3,170 (4,940) ms | not run | not run |
| The same with Deepgram both ways | 2,104 (4,707) ms | 2,732 (4,106) ms | 3,043 (4,598) ms |
| Passed, of 17, Deepgram both ways | 11 | 14 | 14 |
| Model calls, input tokens | 178, 391,498 | 86, 110,816 | 73, 113,308 |
| Spend for 17 calls (model + speech-to-text) | 2.01 USD | 0.70 USD | 0.70 USD |
| Voice loop written (counted lines) | 58, YAML configuration | 315, code | 261, code |
| Voice adapter: Speechmatics / Deepgram | 213 / 0 (built in) | 251 / 184 (shared) | 251 / 184 (shared) |
| Agent logic (restated shared text left out) | 137 (94) | 64 | 115 |
| Refill guard / guard diff from guard-off, docstrings excluded | 47 / 85 | 112 / 162 | 92 / 143 |

- **Equal on outcomes.** Each version failed one call. LangGraph and Strands
  did not reuse a name they already had after a corrected date; Rasa took a
  medicine corrected at the read-back one turn later than the script allows.
  With the guard removed, all three still passed the six adversarial calls,
  because the model complied. Six harder calls
  (`shared/spec/conversations-adversarial-2.json`), run twice, did separate
  them. Guard off, the model sent in the turn it selected, with no
  read-back, in 3 of 36 calls (once per framework), and sent for a second
  patient 4 times (Rasa and LangGraph). Guard on, no second-patient send,
  and one violation in 36 calls. In that Rasa call, speech-to-text split the
  caller's first sentence, and Mantle took a "Yes, please." spoken before the
  read-back as its answer. Replayed with the same timing, LangGraph and
  Strands did the same (3 of 3 each): every loop answers queued transcripts
  in order, and none checks whether the caller had heard the question. An
  opt-in `fix.diff` per build closes it (0 of 3 each), and it also stops a
  backchannel "Okay." from counting as consent; see
  [`COMPARISON.md`](COMPARISON.md#the-fix-consent-only-after-the-read-back-has-played).
- **Rasa wrote the least and spent the most.** Its voice loop and barge-in
  path are the runtime. It made more than twice the model calls, because of
  one call per tool, engine routing and confirmation calls, fact discovery,
  and calls after hangups that nobody hears. That stayed true on Deepgram
  (2.1 to 2.4 times the calls), where Rasa's totals were also lowered by six
  calls that failed early.
- **Rasa's slower first audio came from the TTS engine.** Mantle streams
  the model only into a TTS engine that takes streaming text, and
  Speechmatics' preview TTS does not. With Rasa's built-in Deepgram TTS, its
  first audio came 1.8 s sooner, about 1.3 s of it from streaming and the
  rest with the vendor change. With Deepgram both ways for all three, Rasa
  was first at p50. Deepgram's transcripts had no medicine vocabulary and
  were worse, though. Rasa's run passed 11 of 17 against 14 and 14: three
  of its failures were mishearings the other two runs did not get, and one
  was a date written as "11/02/1979" that its model read as 11 February.

## Where the comparison lives

- [`COMPARISON.md`](COMPARISON.md): the side-by-side results, where Rasa's
  model calls go, the unfairness in each direction, and what each framework
  made easy and what it made you write.
- [`COMPARISON-PLAN.md`](COMPARISON-PLAN.md): the six measures (pass counts,
  latency breakdown, code per concern, the guard diff, adversarial calls
  against the guard, voice plumbing written) and the behaviour checklist.
- [`rasa/README.md`](rasa/README.md), [`langgraph/README.md`](langgraph/README.md),
  [`strands/README.md`](strands/README.md): each version, its guard, how to
  run it and its figures.
- [`results/`](results/): every recorded run, one folder per framework.

## Scope

- **Synthetic.** Cedar Clinic, Maria Alvarez, Theo Lindqvist and their
  records are invented. Nothing here is medical advice.
- **Synthetic callers.** The caller audio is AI-generated speech (Deepgram
  Aura-2), replayed byte for byte. No person's voice is recorded here.
- **Not on-device.** Speech goes to Speechmatics and the model call to
  OpenAI.
- **One model, one machine, one day.** A different model, release, vendor
  setting or day can behave differently.
