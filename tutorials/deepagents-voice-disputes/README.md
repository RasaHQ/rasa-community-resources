# Investigate a card charge with Mantle voice and Deep Agents

A caller does not recognise a payment on their bank statement. A research agent
can explain a merchant descriptor, but that explanation is not consent to file
a dispute. This tutorial keeps the investigation and the submission apart.

Mantle handles the voice conversation. One Mantle tool calls Deep Agents in a
separate local process. That worker can read evidence for the selected charge;
it cannot submit a review, decide fraud or promise a refund.

Northgate Bank, its customers, codes, merchants and charges are fictional.
This is an in-memory developer demo, not production banking software. Do not
use real customer data. The published demo codes are selectors, not authentication.

## What you build

```text
Microphone → Deepgram ASR → Mantle conversation → Rime speech → speaker
                              │
                              ├─ research_charge → Deep Agents worker
                              │                       └─ selected evidence only
                              │
                              └─ prepare_review → Mantle confirmation
                                                       └─ submit_review
                                                          (demo record only)
```

Deep Agents is a tool behind the conversation, not a second voice agent. No A2A
service, shell execution, background job or external subagent is involved.
The process boundary separates dependency versions and available callables;
it is not an operating-system security sandbox.

## Install only these two environments

Requirements: Python 3.12, uv, an OpenAI key and a Rasa Pro licence. To speak to
the agent, also set Deepgram and Rime keys. The example pins Rasa Pro
3.21.0.dev5 (experimental), Deep Agents 0.7.23 and langchain-openai 1.7.0.
Each lockfile records its own exact transitive dependencies.

The pinned Mantle and LangChain packages need incompatible OpenAI SDK versions.
Do not combine their environments or override the resolver. From the repo root:

```bash
python3 scripts/workspace.py start tutorials/deepagents-voice-disputes/worker --owner northgate-worker
python3 scripts/workspace.py start tutorials/deepagents-voice-disputes/mantle --owner northgate-mantle
cd tutorials/deepagents-voice-disputes
export BANK_RESEARCH_PYTHON="$PWD/worker/.venv/bin/python"
```

Set OPENAI_API_KEY, RASA_PRO_LICENSE, DEEPGRAM_API_KEY and RIME_API_KEY in that
terminal. Never commit their values. The template is `mantle/.env.example`;
copying it does not load it. There is no credential search in other repositories.
The Mantle runtime may load its own local dotenv file; this worker bridge reads
only explicit environment values.

## Test before calling a provider

From the tutorial directory:

```bash
mantle/.venv/bin/python -B -m unittest discover -s tests -p test_casework.py -v
mantle/.venv/bin/python -B -m unittest discover -s tests -p test_bridge.py -v
mantle/.venv/bin/python -B -m unittest discover -s tests -p test_mantle_native.py -v
worker/.venv/bin/python -B -m unittest discover -s tests -p test_worker_native.py -v
cd mantle
make validate
make train
```

The first two suites check application state and the subprocess contract.
The native suites run the actual Deep Agents graph with controlled model
responses and the actual Mantle confirmation gate/invoker with a controlled
tracker. They make no provider requests. They do not measure speech accuracy,
model judgement, production authentication or a full caller conversation.

## Why the proposal check matters

The native correction control resumes a pending TX-101 call after TX-102 becomes
current. The guarded application records nothing. A separate mutation test removes
only the two refusal checks from the actual submit method and resumes the same
pending call through Mantle. It records TX-102 from arguments that still read back
TX-101 and 49 pounds. This is an intentionally unsafe test-only variant, not a
service configuration or a product defect. It shows why consent and current
case binding are separate requirements. `verification.json` records both outputs.

## Speak to the agent

From `mantle/`, run:

```bash
make inspect
```

Use the local Inspector URL printed by the CLI. Select its voice interface and
allow microphone access. REST is enabled for text debugging; `make run` starts
the runtime without Inspector. Keep the service local. Both voice channels use
Deepgram Nova-3 for recognition and Rime Mist v3 for synthesis. The selected
Rime speaker is ironwood. These are configuration choices, not a vendor ranking.

Use the published fixture code 111111, then TX-101. Ask it to explain the
49-pound PINE*ANNUAL payment. If you still want staff review, ask to record it,
then answer Mantle's separate confirmation. A record is a demo staff-review
request, never a fraud finding or a refund. Stopping the server clears records.

Try again and decline confirmation. Then try correcting TX-101 to TX-102
before approval. An old proposal cannot submit the new charge. A repeated
submission of the same current proposal returns the same reference.

## Follow the source

| File | What to change or inspect |
| --- | --- |
| `mantle/skills/charge_review/tools.py` | Mantle bindings and stale-research check |
| `shared/bank_research/bridge.py` | Worker interpreter, deadline and environment allowlist |
| `shared/bank_research/researcher.py` | Deep Agents graph, excluded tools and evidence references |
| `shared/bank_research/casework.py` | Ownership, proposal invalidation and idempotency |
| `mantle/skills/charge_review/skill.md` | Runtime confirmation and voice procedure |
| `mantle/integrations.yml` | Voice models, speaker and local channels |

The worker receives a copy of the selected transaction, descriptor evidence and
review policy. It gets no owner id, customer directory or submit function.
It returns evidence references. We return the original facts behind those
references and discard model-authored conclusions. The parent checks that
returned facts are unchanged. A timeout, invalid reference or missing worker
produces an error, not a fabricated answer.

Confirmation is enforced by Mantle's tool constraint. The Python submit function
checks current proposal and readback fields; calling it directly bypasses the
voice consent step. Tests keep those two responsibilities separate. Neither is
a substitute for production identity, consent records or access control.

## Diagnose a failure

| Symptom | Check |
| --- | --- |
| Research is not configured | Absolute BANK_RESEARCH_PYTHON path and explicitly exported OpenAI key |
| Research is unavailable | Worker lock, provider account, timeout or non-JSON model output; offer staff review without inventing findings |
| Proposal changed or missing | Re-select and prepare after any correction; do not approve an older proposal |
| Readback changed | Pass the prepared merchant, amount, currency and date unchanged |
| Voice cannot connect | Speech keys, microphone permission, local Inspector and channel configuration |
| No record after restart | Expected: demo state is process-local, not a durable banking queue |

Before production, replace demo selectors with trusted authentication, move case
state into a durable service, expire sessions and proposals, audit consent, and
set provider concurrency and retention policies. Review voice handling with
real recordings, including corrections and interruptions; interruptions are
disabled here. Do not treat these offline tests as acoustic qualification.

## Retire the experiment

Stop your own runtime and finish saving any unique local notes. From the repo root:

```bash
python3 scripts/workspace.py retire tutorials/deepagents-voice-disputes/worker --owner northgate-worker --inactive
python3 scripts/workspace.py retire tutorials/deepagents-voice-disputes/mantle --owner northgate-mantle --inactive
```

Keep both manifests and lockfiles. Do not copy installed environments into
worktrees or backups. Isolation is necessary here; retaining completed installs is not.
