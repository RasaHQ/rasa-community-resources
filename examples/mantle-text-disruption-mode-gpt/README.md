# Horizon Travel disruption mode on GPT-5.5: a seat is promised only as a hold

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of customers during a mass disruption
Time:          15 minutes to run the agent; about 10 minutes and 2 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`disruption-mode`](../../tutorials/rasa-ai-team-casebook/examples/disruption-mode.json),
on OpenAI's `gpt-5.5-2026-04-23` with `reasoning_effort: low`, in web chat.

The first live run is recorded in `case-build/results/2026-09-30-gpt-5.5-low/`.
Its write-up follows in the next commit.
