# Amber Grid budget plans on GPT-5.5: an estimate that never touches the balance

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of billing support options
Time:          15 minutes to run the agent; the live conversation suite is billed (see below)
```

A Rasa Mantle text agent for one casebook case,
[`utilities-budget-plan`](../../tutorials/rasa-ai-team-casebook/examples/utilities-budget-plan.json):
explain or request a budget plan for a signed-in customer of Amber Grid, a
fictional energy supplier, in web chat, or refer them to the hardship team.
It runs on OpenAI's `gpt-5.5-2026-04-23` with `reasoning_effort: low` and
serves the REST and socket.io channels. The matrix channel for this case is
web chat, so the build runs in the channel it targets.

The case's failure is one sentence: *the agent treated an estimated budget
instalment as a waiver of the customer's outstanding balance.* In this
project a budget amount, the usage estimate behind it and the outstanding
balance are three separate things in every tool result, in the confirmation
question and in the receipt. No tool takes an amount or a balance, and no
option changes the balance.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE and OPENAI_API_KEY in .env
make proof      # offline guard tests: no licence, model or network
make validate
make train
make inspect    # chat in the Inspector
make run        # REST at /webhooks/rest/webhook and socket.io, port 5005
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | GPT-5.5, referenced as `api_key: ${OPENAI_API_KEY}` in `integrations.yml` |

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
