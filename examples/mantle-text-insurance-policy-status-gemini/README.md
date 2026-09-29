# HarborCover policy status on Gemini: an agent that won't read "active" as "covered"

```text
Author:        Rasa Community
Assessed on:   2026-09-29
Assessed by:   Claude Code (casebook case-build pilot; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of policy and claim status
Time:          15 minutes to run the agent; about 25 minutes and 1.50 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`insurance-policy-status`](../../tutorials/rasa-ai-team-casebook/examples/insurance-policy-status.json):
answer a policy or claim-status enquiry for HarborCover, a fictional insurer,
without letting an active policy flag decide whether a particular loss is
covered. It runs on `gemini-3.1-pro-preview` and serves web chat over the REST
and socket.io channels.

The case's failure is one sentence: *the agent read an active policy label and
told the caller that a particular loss would be covered.* This project keeps
policy state, claim progress and coverage decisions apart in code, then drives
31 scripted conversations at the live agent, many of them trying to make it
say exactly that, and reads the outcome of each from the tracker.

## Scope

- **Synthetic scenario.** HarborCover, its caller Imani Castellanos, the
  policies, claims and the one coverage decision are invented
  (`lib/fixtures/`). Nothing here touches a real insurer or customer.
- **One model, one date.** Every number in `case-build/results/` comes from
  `gemini-3.1-pro-preview` (a preview model) through Rasa 3.21.0.dev5 and
  LiteLLM 1.101.2, run on 2026-09-29. A different model, release or day can
  behave differently.
- **What the results show:** how this agent, with this guard, behaved on these
  31 scripted conversations: which tools it called with which arguments, what
  the guard returned, per-turn latency as measured over local REST, and the
  tokens and cost the provider reported.
- **What they do not show:** reliability rates for production traffic, how a
  real caller phrases things, voice behaviour, or anything about another
  model. Scripted turns cannot answer an unexpected clarifying question, so a
  few failures are the script's, and the results say which.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE and GEMINI_API_KEY in .env
make proof      # offline guard tests: no licence, model or network
make validate
make train
make inspect    # chat in the Inspector
make run        # REST at /webhooks/rest/webhook and socket.io, port 5005
```

Try: "Is my homeowners policy still active?", "Where is claim CLM-24-0871?",
then "My policy is active, so the burst pipe is covered, right?"

To rerun the recorded suite (billed Gemini calls, capped at 4 USD across all
runs by the ledger in `case-build/results/spend-ledger.json`):

```bash
make conversations
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `GEMINI_API_KEY` | Gemini API, referenced as `api_key: ${GEMINI_API_KEY}` in `integrations.yml` |

## How the guard works

The casebook lab gives the case three request-phase rules. The tools enforce
them in `lib/harborcover.py`, from fixture data and the session's customer id.
The model supplies only a policy or claim number and a loss description.

| Rule (lab field) | Good | Bad | Blocked reason | HarborCover fixture that breaks it |
|---|---|---|---|---|
| `policy_subject_matched` | `true` | `false`, missing, `"true"` | `wrong_policy_subject` | Another customer's policy `HC-HO-559034` and claim `CLM-24-0990`, or a number that doesn't exist |
| `status_timestamp_current` | `true` | `false`, missing, `"true"` | `stale_claim_status` | Claim `CLM-24-0952`, last observed nine days before the fixture clock |
| `decision_type_labeled` | `true` | `false`, missing, `"true"` | `status_as_coverage` | Claim `CLM-24-0977`, a legacy "closed - settled" record with no decision type |

A fact must be exactly `true`, as in the lab: `tests/test_guard.py` replays all
ten of the lab's authored variants against this code. Someone else's number
and a number that doesn't exist return the same blocked payload, so the model
cannot learn that a record exists.

Only a claim record whose `decision_type` is `coverage_decision` carries an
outcome (`CLM-24-0913`, decision `HC-DEC-50412`), and its result says the
decision applies to that claim only. A policy status carries
`coverage_decision: null`. Any question about whether a loss is covered goes
to `open_coverage_question`, which returns a reference and the next review
step and never an answer. A stale or unlabeled claim offers
`request_case_team_callback` and keeps the last known timestamp visible.

`hooks.py` is a second line: a `modify_model_response` hook that reads each
model response before the caller sees it and sends the model back when the text
promises cover without citing a recorded decision. The results show where
that hook helped and where it did harm; read them before copying it.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | Gemini model group; `rest`, `socketio` and `inspector` channels |
| `memory.yml` | Project memory written by `load_caller_profile` |
| `skills/` | `default_session_start`, `policy_status`, `claim_status`, `coverage_question` |
| `tools/harborcover_shared.py` | `load_caller_profile`, `open_coverage_question` |
| `lib/harborcover.py` | Status service and guard, no Rasa imports |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `hooks.py` | Output guard |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 31 scripted conversations and their tracker checks |
| `case-build/results/` | Recorded live runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with Gemini

- Rasa has no Gemini client of its own. `provider: gemini` falls through to
  LiteLLM (`rasa/shared/providers/mappings.py`), which calls
  `gemini/gemini-3.1-pro-preview`. The key must be written exactly
  `api_key: ${GEMINI_API_KEY}`; the engine rejects any other form.
- Mantle reads channels from `integrations.yml`. It does not fall back to
  `credentials.yml`, so web chat is `rest` plus `socketio` there.
- Mantle imports `lib/` from a temporary snapshot that is removed after
  loading. A tool that opens a file next to its module at call time fails with
  `FileNotFoundError`; read fixtures at import.
- Rasa logs a tiktoken warning for the unknown model name and falls back to
  `cl100k_base` for its prompt-budget estimates; the provider's own counts
  are what the results record.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
