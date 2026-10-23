"""Run the eval scenarios against a live Rasa server and print a summary.

Usage:
    python scripts/run_eval.py [--run-count N] [--scenario FOO.yml ...]

Uses the same code path as the MCP evaluate_agent tool (run_scenario).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rasa.builder.copilot.mcp_server.tools.eval_config import (
    EvalConfigError,
    build_llm_client,
    load_conftest,
)
from rasa.builder.copilot.mcp_server.tools.evaluate_agent import run_scenario
from rasa.builder.copilot.mcp_server.tools.scenario import load_scenario
from rasa.builder.copilot.mcp_server.tools import llm_judge, text_simulation

PROJECT_ROOT = Path(r"C:\Users\ADMIN\Desktop\raaaa")
SCENARIO_DIR = PROJECT_ROOT / "eval" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "eval" / "results"
RASA_SERVER_URL = "http://127.0.0.1:5006"

# DeepSeek's json_object/json_schema structured-output modes return empty
# content on the simulator's long prompts, while prompt_only mode returns
# valid JSON reliably. Force Rasa's structured-output probes off so the
# harness uses the prompt_only fallback (documented-safe in llm.py).
text_simulation.supports_response_schema = lambda _client: False
text_simulation.supports_json_response_format = lambda _client: False
llm_judge.supports_json_response_format = lambda _client: False


# DeepSeek freely alternates between JSON and plain-text output in prompt_only
# mode. The harness resends bit-identical payloads on retry, so a failed
# attempt re-returns the exact same non-JSON reply. Patch the retry loop to
# escalate a "reply must be JSON" nudge and jitter temperature on each attempt
# so a retry produces a genuinely new completion.
_NUDGE = (
    ' IMPORTANT: Reply with exactly one JSON object containing only '
    '"message" and "done". No prose, no code fences.'
)


async def _simulate_with_jitter(
    llm_client,
    messages,
    completion_kwargs=None,
    *,
    conversation_id,
    max_attempts=3,
):
    import asyncio
    from rasa.builder.copilot.mcp_server.tools.text_simulation import (
        _parse_simulator_response,
    )

    extras = dict(completion_kwargs or {})
    last_error = None
    for attempt in range(1, max_attempts + 1):
        extra = dict(extras)
        extra["temperature"] = 0.6 + 0.2 * attempt
        msgs = list(messages)
        if attempt > 1:
            msgs = msgs + [{"role": "user", "content": _NUDGE * attempt}]
        try:
            response = await llm_client.acompletion(msgs, **extra)
            raw = response.choices[0].strip()
            parsed = _parse_simulator_response(raw)
            if parsed is not None:
                return parsed
            last_error = f"could not parse simulator reply: {raw!r}"
        except Exception as exc:
            last_error = repr(exc)
        if attempt < max_attempts:
            await asyncio.sleep(0.5 * attempt)
    raise RuntimeError(
        f"user simulator failed after {max_attempts} attempts: {last_error}"
    )


text_simulation._generate_user_message = _simulate_with_jitter


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-count", type=int, default=1)
    parser.add_argument("--scenario", action="append", default=None)
    parser.add_argument("--show-tracker-events", action="store_true")
    parser.add_argument("--evaluate-tool-calls", action="store_true")
    parser.add_argument("--skip-criteria", action="store_true")
    args = parser.parse_args()

    try:
        conftest = load_conftest(PROJECT_ROOT)
        simulation_client = build_llm_client(conftest.simulation.llm)
        eval_client = build_llm_client(conftest.evaluation.llm)
    except EvalConfigError as exc:
        print(f"conftest error: {exc}", flush=True)
        return

    if args.scenario:
        files = [SCENARIO_DIR / name for name in args.scenario]
    else:
        files = sorted(SCENARIO_DIR.glob("*.yml"))

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    print(f"experiment {timestamp}  server={RASA_SERVER_URL}", flush=True)

    for path in files:
        scenario = load_scenario(path)
        print(f"\n=== {scenario.slug} : {scenario.name} (runs={args.run_count}) ===", flush=True)
        criteria = [] if args.skip_criteria else scenario.goals.criteria
        summary = await run_scenario(
            scenario,
            project_path=PROJECT_ROOT,
            experiment_timestamp=timestamp,
            run_count=args.run_count,
            rasa_server_url=RASA_SERVER_URL,
            simulation_llm_client=simulation_client,
            eval_llm_client=eval_client,
            eval_llm_config=conftest.evaluation.llm,
            criteria_judge_prompt=conftest.evaluation.criteria_judge_prompt,
            metrics_judge_prompt=conftest.evaluation.metrics_judge_prompt,
            show_tracker_events=args.show_tracker_events,
            evaluate_tool_calls=args.evaluate_tool_calls,
        )
        print(
            f"RESULT {scenario.slug}: {summary.runs_passed}/{summary.runs_total} passed "
            f"({summary.duration_s:.1f}s)",
            flush=True,
        )

    print(f"\nreports: {RESULTS_DIR / timestamp}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())