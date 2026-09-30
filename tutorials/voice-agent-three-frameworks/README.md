# One voice agent, three frameworks: Rasa Mantle, LangGraph and AWS Strands Agents

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (phase 1: shared parts and the Rasa version; live run in results/rasa/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv, macOS 26.6.2
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

This is phase 1: the shared parts and the Rasa Mantle version. The LangGraph
and Strands versions are built next, against the same shared parts, by the
rules in [`COMPARISON-PLAN.md`](COMPARISON-PLAN.md).

## Layout

```text
voice-agent-three-frameworks/
  COMPARISON-PLAN.md   what is measured, and how, for all three
  shared/
    clinic/            cedar_clinic: records, rules, audited tool functions, instruction text (no framework)
    spec/              17 scripted calls with caller audio, the runner, the checks, the LLM meter, the line counter
    speech/            cedar_speech: Speechmatics ASR and TTS clients for the LangGraph and Strands servers
    web/               one browser voice page for all three, its relay, PROTOCOL.md
  rasa/                the Rasa Mantle version
  langgraph/           (phase 2)
  strands/             (phase 2)
  results/<framework>/ recorded runs of the shared spec
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
python3 shared/spec/run_spec.py rasa --label <run> --budget-usd 4    # billed: GPT-5.5 and Speechmatics
make test                                                            # offline tests of the shared parts
make count                                                           # lines per concern, guard diffs
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

## The Rasa version so far

From [`results/rasa/`](results/rasa/), 2026-09-30:

- **12 of 17** calls passed in the first full run over browser audio; **0**
  guard violations. Four failures were the model asking its own confirmation
  question or asking which medicine instead of selecting by description; the
  shared procedure was changed and those four passed on rerun. The fifth is
  Mantle taking the corrected medicine one turn after a decline, later than
  the script allows.
- **4.6 s** p50 from the end of the caller's speech to the first bot audio
  (7.6 s p95): about 1.5 s to the transcript, 1.9 s of agent processing
  (almost all of it the first model call), 1.2 s to Speechmatics TTS's first
  byte. In 34 of 39 turns that first audio was a Mantle filler.
- **Lines per concern:** agent logic 137, refill guard 47, voice adapter 213
  (Speechmatics as Rasa engines), voice loop 58 (YAML only). The guard as a
  diff from the guard-off baseline: 89 counted lines.
- **Spend:** 1.84 USD for the full run, 2.71 USD recorded across all runs.

## Where the comparison lives

- [`COMPARISON-PLAN.md`](COMPARISON-PLAN.md): the six measures (pass counts,
  latency breakdown, code per concern, the guard diff, adversarial calls
  against the guard, voice plumbing written) and the behaviour checklist.
- [`results/rasa/`](results/rasa/): the Rasa version's runs.
- [`rasa/README.md`](rasa/README.md): the Rasa version, its guard and its
  figures.

## Scope

- **Synthetic.** Cedar Clinic, Maria Alvarez, Theo Lindqvist and their
  records are invented. Nothing here is medical advice.
- **Synthetic callers.** The caller audio is AI-generated speech (Deepgram
  Aura-2), replayed byte for byte. No person's voice is recorded here.
- **Not on-device.** Speech goes to Speechmatics and the model call to
  OpenAI.
- **One model, one machine, one day.** A different model, release, vendor
  setting or day can behave differently.
