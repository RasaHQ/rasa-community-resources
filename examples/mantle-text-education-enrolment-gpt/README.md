# Pine University enrolment and aid enquiries on GPT-5.5: a web-chat agent that never reads a receipt as an award

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of admissions and financial-aid questions
Time:          15 minutes to run the agent; about 10 minutes and a few US dollars for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`education-enrolment`](../../tutorials/rasa-ai-team-casebook/examples/education-enrolment.json):
record an enrolment or financial-aid enquiry for a signed-in applicant of
Pine University, a fictional university, in web chat. It runs on OpenAI's
`gpt-5.5-2026-04-23` with `reasoning_effort: low` and serves the REST and
socket.io channels.

The case's failure is one sentence: *the assistant treated a submitted aid
form as an award decision and told the applicant that funding was secured.*
In this project a received form is a stage, never a decision. The records
decide what the agent may say: `decision` is `null` unless the responsible
team issued one, and when two sources disagree about a form there is no stage
and no decision at all.

The live results are not recorded yet.

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
