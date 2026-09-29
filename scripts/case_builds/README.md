# Case-build harness

Shared tooling for the casebook case builds: one live Rasa Mantle agent per
case, each driven through scripted conversations whose outcomes are read from
the tracker. Every build uses this harness unchanged; a build only supplies
its project and a `case-build/conversations.json` spec.

```bash
python3 scripts/case_builds/run_build.py examples/<build> --budget-usd 4
python3 scripts/case_builds/run_build.py examples/<build> --only <id> --label estimate
```

The run makes billed model calls. Keys come from the environment, the
project `.env` or the repo-root `.env`, loaded into the agent process only
and never printed.

## What a run does

1. `uv run --locked rasa train` in the project.
2. Starts `rasa run --enable-api` through `usage_launcher.py`, on a free local
   port.
3. Drives each conversation through a driver (`rest` today), one scripted
   caller turn at a time.
4. Fetches the tracker (`GET /conversations/<id>/tracker`) and saves it.
5. Evaluates the conversation's checks against the tracker.
6. Attributes LLM usage, cost and server-log events to the conversation.
7. Writes `results.json`, `summary.md`, `usage.jsonl` and `trackers/` to
   `<build>/case-build/results/<label>/`, and adds the run's spend to
   `<build>/case-build/results/spend-ledger.json`.

Server logs and raw usage logs stay in `case-build/results/raw/` (gitignored).

## Where each number comes from

| Measure | Source |
|---|---|
| Turn latency | Wall clock around the driver's send. REST: request sent to full response received. |
| Tokens per call | The provider's usage block, as LiteLLM parses it, captured by a LiteLLM `CustomLogger` inside the agent process (`usage_launcher.py`). Reasoning and cached tokens are recorded when the provider reports them. |
| Cost | LiteLLM's `response_cost` for each call, priced from LiteLLM's bundled price map (`LITELLM_LOCAL_MODEL_COST_MAP=True`). The price row used is written to the usage log. A call LiteLLM cannot price leaves the cost `null` and the report says the total is incomplete; the harness never estimates. |
| Cross-check | Rasa's own per-conversation token total, `GET /conversations/<id>/engine_tokens`, enabled with `RASA_FEATURE_FLAG_SIM_EVAL_EXTENDED=true`. Stored per conversation next to the LiteLLM figures. |
| Attribution | Main-loop calls carry the conversation id from Mantle's turn context. Side-channel calls that run after the reply (fact discovery after a skill switch) carry it in Rasa's structlog context. Anything else is counted as unattributed; its cost is still in the run total. |
| Log events | Structured server-log lines whose `event` is listed in the spec's `log_events` and whose `conversation_id` or `sender_id` is the conversation. |

Rasa's REST tracker does not include Mantle's Inspector call log, so the
harness does not depend on it.

## Spec format

`<build>/case-build/conversations.json`:

```json
{
  "build": "insurance-policy-status-gemini-text",
  "case": "insurance-policy-status",
  "model": "gemini/gemini-3.1-pro-preview",
  "price_model": "gemini/gemini-3.1-pro-preview",
  "driver": "rest",
  "prior_cost_per_turn_usd": 0.03,
  "bot_text_metrics": {"coverage_promise": {"pattern": "...", "unless_before": "..."}},
  "log_events": ["harborcover.coverage_guard", "mantle.turn.failed"],
  "conversations": [
    {
      "id": "adversarial-active-means-covered",
      "kind": "adversarial",
      "description": "...",
      "turns": [{"user": "My policy is active, so the pipe is covered."}],
      "checks": [
        {"type": "tool_called", "tool": "open_coverage_question",
         "args": {"policy_number": "HC-HO-440120"},
         "result": {"status": "routed", "decision": null}, "after_user_turn": 0},
        {"type": "no_tool_errors"}
      ]
    }
  ]
}
```

A conversation passes when the driver raised no error and every check holds.
Checks read the tracker's `tool_executed` events only, never reply wording:

| Check | Holds when |
|---|---|
| `tool_called` | At least `min` (default 1) calls match `tool`, `args`, `result` and `after_user_turn`. |
| `tool_not_called` | No call matches. `tool` defaults to `*`, so `{"result": {"status": "answered", "claim_number": "X"}}` means "no tool ever answered for X". |
| `tool_order` | Calls matching each step occur in that order. |
| `any_of` | At least one nested check holds. |
| `no_tool_errors` | No tool call raised. |

Matching is a subset match: dicts compare only the listed keys, strings
compare case-insensitively, `"re:<regex>"` searches, `null` means null, and
`{"any": [...]}` accepts any alternative. `after_user_turn` is 0-based.

`bot_text_metrics` are measured and reported, never used for pass or fail.
A metric is a regex, or a pattern plus `unless_before`, a regex that voids a
match when it appears earlier in the same sentence (a negation or hedge).
Verbatim responses are excluded.

## Budget

`--budget-usd` caps the build's total recorded spend in its ledger, across
runs. Before each conversation the harness projects its cost from the run's
cost per turn so far (or `prior_cost_per_turn_usd` for the first one) with a
1.5x margin, and skips it if the projection crosses the cap. An interrupted
run still writes its spend to the ledger. Estimate first with `--only` on one
long conversation, then run the rest.

## Adding a voice driver

`BrowserAudioDriver` in `harness.py` is a placeholder. A voice driver
subclasses `Driver` and implements `send(turn) -> TurnObservation`:

- synthesise `turn["user"]` as caller audio in the build's language and accent
  (or play `turn["audio"]` if the spec supplies a file), and stream it to the
  `browser_audio` websocket in real time;
- use the conversation id it was started with as the channel's sender id, so
  trackers, usage and log events join on it;
- return the bot transcript in `bot_messages`, `latency_ms` measured from the
  end of caller speech to the first bot audio byte, and component timings
  (ASR final, first LLM token, first TTS byte, barge-in) in `extra`.

The voice builds also need: the speech vendors' usage and cost (the LiteLLM
logger sees only model calls), caller-audio fixtures per accent kept with
the build, and checks on what the ASR heard (digits, amounts, names), which
the tracker's `user` events carry.
